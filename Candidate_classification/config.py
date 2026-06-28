from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
SEG_MODELS = CURRENT_DIR / "models"
OUTPUT_DIR = CURRENT_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

XGB_MODEL_PATH = CURRENT_DIR / "xgb_total_model.json"
OCR_WORKER = CURRENT_DIR / "ocr_worker.py"
OCR_TEMP = CURRENT_DIR / "temp_ocr_results.json"
FEEDBACK_CSV = CURRENT_DIR / "feedback_dataset.csv"
