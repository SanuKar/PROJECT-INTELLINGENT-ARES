import json
import random
from pathlib import Path

parsed_folder = Path("data/parsed")
all_files = list(parsed_folder.glob("*.json"))
sample = random.sample(all_files, 10)

for f in sample:
    with open(f, encoding="utf-8") as file:
        doc = json.load(file)
    print(f"--- {doc['filename']} ---")
    print(doc["cleaned_text"][:250].replace("\n", " "))
    print()