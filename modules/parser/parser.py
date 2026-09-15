"""
ARES - Parsing & Cleaning Module
Author: Bhargab
Extracts and cleans text from resume PDFs (handles both text-based and scanned/OCR PDFs).
Validates output against the shared ResumeDocument schema and saves results to disk.
Parallelized across multiple CPU cores for large datasets.
"""

import re
import json
import logging
import uuid
import sys
import hashlib
import time
import os
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

import pdfplumber
from pdf2image import convert_from_path
import pytesseract

# Allow importing from shared/schemas when running this file directly
sys.path.append(str(Path(__file__).resolve().parents[2]))
from shared.schemas.resume import ResumeDocument

logger = logging.getLogger(__name__)

# If Tesseract isn't on PATH, uncomment and point to your install:
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

MIN_TEXT_LENGTH = 50  # below this, treat as "no real text layer" -> use OCR


def setup_logging():
    """Only called once, in the main process - avoids duplicate log handlers across workers."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("parser_run.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


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


def stable_id_for(pdf_path: Path) -> str:
    """Deterministic ID based on file path, so re-runs skip already-parsed files."""
    return hashlib.sha1(str(pdf_path.resolve()).encode("utf-8")).hexdigest()


def parse_resume(pdf_path: str) -> tuple[ResumeDocument, bool]:
    """Parse one resume PDF into a validated ResumeDocument. Returns (document, used_ocr)."""
    native_text = extract_text_native(pdf_path)
    used_ocr = len(native_text.strip()) < MIN_TEXT_LENGTH

    if used_ocr:
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


def save_document(document: ResumeDocument, out_path: Path) -> None:
    """Save one parsed ResumeDocument as JSON."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(document.model_dump(), f, ensure_ascii=False, indent=2)


def process_one(pdf_path_str: str, output_folder_str: str) -> dict:
    """
    Worker function - runs inside a separate process.
    Handles one PDF completely: parse, validate, save. Returns a small result dict
    (not the full document) to keep inter-process communication cheap.
    """
    pdf_path = Path(pdf_path_str)
    output_folder = Path(output_folder_str)
    file_id = stable_id_for(pdf_path)
    out_path = output_folder / f"{file_id}.json"

    if out_path.exists():
        return {"status": "skip", "filename": pdf_path.name}

    try:
        document, used_ocr = parse_resume(str(pdf_path))
        save_document(document, out_path)
        return {"status": "ok", "filename": pdf_path.name, "used_ocr": used_ocr}
    except Exception as e:
        return {"status": "fail", "filename": pdf_path.name, "error": str(e)}


def run_batch_parallel(input_folder: Path, output_folder: Path, max_workers: int = None) -> None:
    """Walk every PDF under input_folder and process them across multiple CPU cores."""
    if not input_folder.exists():
        logger.error(f"Input folder does not exist: {input_folder.resolve()}")
        logger.error("Check the path in the __main__ block at the bottom of this file.")
        return

    pdf_files = sorted(input_folder.rglob("*.pdf"))
    total = len(pdf_files)
    logger.info(f"Found {total} PDFs under {input_folder}")

    if total == 0:
        logger.warning("No PDFs found. Double-check input_folder points to the right place.")
        return

    output_folder.mkdir(parents=True, exist_ok=True)

    if max_workers is None:
        max_workers = max(1, (os.cpu_count() or 4) - 1)  # leave one core free
    logger.info(f"Using {max_workers} parallel worker processes")

    ok_count = 0
    skip_count = 0
    fail_count = 0
    ocr_count = 0
    completed = 0
    start_time = time.time()

    def print_summary():
        logger.info("=" * 60)
        logger.info(
            f"SUMMARY. total={total} ok={ok_count} skipped={skip_count} "
            f"failed={fail_count} used_ocr={ocr_count}"
        )
        logger.info(f"Output saved to: {output_folder.resolve()}")

    try:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(process_one, str(pdf_file), str(output_folder)): pdf_file
                for pdf_file in pdf_files
            }

            for future in as_completed(futures):
                completed += 1
                result = future.result()

                if result["status"] == "skip":
                    skip_count += 1
                elif result["status"] == "ok":
                    ok_count += 1
                    if result.get("used_ocr"):
                        ocr_count += 1
                else:
                    fail_count += 1
                    logger.error(f"[FAIL] {result['filename']}: {result.get('error')}")

                if completed % 25 == 0 or completed == total:
                    elapsed = time.time() - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    remaining = (total - completed) / rate if rate > 0 else 0
                    logger.info(
                        f"Progress: {completed}/{total} | ok={ok_count} skipped={skip_count} "
                        f"failed={fail_count} | ~{remaining/60:.1f} min remaining"
                    )
    except KeyboardInterrupt:
        logger.warning("Interrupted by user (Ctrl+C). Progress so far:")
        print_summary()
        logger.warning("Safe to re-run later - already-parsed files will be skipped.")
        return

    print_summary()


if __name__ == "__main__":
    setup_logging()

    # Point this at wherever the full dataset actually lives
    input_folder = Path("data/raw_resumes")
    output_folder = Path("data/parsed")

    run_batch_parallel(input_folder, output_folder)