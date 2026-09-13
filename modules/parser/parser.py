"""
ARES - Parsing & Cleaning Module
Author: Bhargab
Extracts and cleans text from resume PDFs (handles both text-based and scanned/OCR PDFs).
Validates output against the shared ResumeDocument schema and saves results to disk.
"""

import re
import json
import logging
import uuid
import sys
from pathlib import Path

import pdfplumber
from pdf2image import convert_from_path
import pytesseract

# Allow importing from shared/schemas when running this file directly
sys.path.append(str(Path(__file__).resolve().parents[2]))
from shared.schemas.resume import ResumeDocument

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# If Tesseract isn't on PATH, uncomment and point to your install:
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

MIN_TEXT_LENGTH = 50  # below this, treat as "no real text layer" -> use OCR


def extract_text_native(pdf_path: str) -> str:
    """Try extracting text directly using pdfplumber (works for text-based PDFs)."""
    text_parts = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
    except Exception as e:
        logger.warning(f"pdfplumber failed on {pdf_path}: {e}")
    return "\n".join(text_parts)


def extract_text_ocr(pdf_path: str) -> str:
    """Fallback: render PDF pages as images and OCR them (for scanned PDFs)."""
    text_parts = []
    try:
        images = convert_from_path(pdf_path, dpi=300)
        for img in images:
            text_parts.append(pytesseract.image_to_string(img))
    except Exception as e:
        logger.error(f"OCR failed on {pdf_path}: {e}")
    return "\n".join(text_parts)


def clean_text(raw_text: str) -> str:
    """Clean up extracted resume text: normalize whitespace and line breaks."""
    text = raw_text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)      # collapse repeated spaces/tabs
    text = re.sub(r"\n{3,}", "\n\n", text)    # collapse excess blank lines
    text = text.strip()
    return text


def parse_resume(pdf_path: str) -> tuple[ResumeDocument, bool]:
    """
    Parse one resume PDF into a validated ResumeDocument.
    Returns (document, used_ocr) - used_ocr is for your own debugging,
    not part of the shared schema.
    """
    native_text = extract_text_native(pdf_path)
    used_ocr = len(native_text.strip()) < MIN_TEXT_LENGTH

    if used_ocr:
        logger.info(f"No usable text layer in {pdf_path}, falling back to OCR")
        raw_text = extract_text_ocr(pdf_path)
    else:
        raw_text = native_text

    cleaned = clean_text(raw_text)
    path = Path(pdf_path)

    document = ResumeDocument(
        resume_id=str(uuid.uuid4()),
        filename=path.name,
        file_type=path.suffix.lstrip(".").lower(),
        raw_text=raw_text,
        cleaned_text=cleaned,
    )
    return document, used_ocr


def save_document(document: ResumeDocument, output_dir: Path) -> Path:
    """Save one parsed ResumeDocument as JSON, named by its resume_id."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{document.resume_id}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(document.model_dump(), f, ensure_ascii=False, indent=2)
    return out_path


if __name__ == "__main__":
    test_folder = Path("data/parser_test")
    output_folder = Path("data/parsed")
    pdf_files = sorted(test_folder.glob("*.pdf"))

    print(f"Found {len(pdf_files)} PDFs to test\n")

    ok_count = 0
    fail_count = 0
    ocr_count = 0

    for pdf_file in pdf_files:
        try:
            document, used_ocr = parse_resume(str(pdf_file))
            out_path = save_document(document, output_folder)

            preview = document.cleaned_text[:150].replace("\n", " ")
            print(f"[OK] {document.filename} | used_ocr={used_ocr}")
            print(f"     Resume ID: {document.resume_id}")
            print(f"     Saved to: {out_path}")
            print(f"     Preview: {preview}...\n")

            ok_count += 1
            if used_ocr:
                ocr_count += 1
        except Exception as e:
            print(f"[FAIL] {pdf_file.name}: {e}\n")
            fail_count += 1

    print("=" * 50)
    print(f"Summary: {ok_count} succeeded, {fail_count} failed, {ocr_count} used OCR")
    print(f"Parsed documents saved to: {output_folder.resolve()}")