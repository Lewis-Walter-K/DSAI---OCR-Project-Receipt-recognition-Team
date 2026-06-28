import subprocess
import sys
import json
from config import OCR_WORKER, OCR_TEMP


def run_ocr(image_path: str) -> tuple[list, float]:
    subprocess.run([sys.executable, str(OCR_WORKER), image_path, str(OCR_TEMP)], check=True)
    with open(OCR_TEMP, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('ocr_data', []), float(data.get('img_height', 1000))
