import os
import sys
import json
import re
import cv2
import numpy as np
import pandas as pd
import xgboost as xgb
import subprocess
from dotenv import load_dotenv
from pathlib import Path
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import matplotlib.pyplot as plt
import pytesseract
from ultralytics import YOLO
from pytesseract import Output

# ─────────────────────────────────────────────────────
#  PATH SETUP  (works on any machine, any user)
# ─────────────────────────────────────────────────────
load_dotenv()
CURRENT_DIR  = Path(__file__).resolve().parent          # .../Candidate_classification
PROJECT_ROOT = CURRENT_DIR.parent                       # .../invoice-reader
SEG_MODELS   = PROJECT_ROOT / "Seg_OCR_Tri" / "models"
OUTPUT_DIR   = CURRENT_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

XGB_MODEL_PATH  = CURRENT_DIR / "xgb_total_model.json"
OCR_WORKER      = CURRENT_DIR / "ocr_worker.py"
OCR_TEMP        = CURRENT_DIR / "temp_ocr_results.json"
# ─────────────────────────────────────────────────────
#  GLOBAL MODELS  (loaded once at startup)
# ─────────────────────────────────────────────────────
print("🚀 Đang khởi tạo các mô hình AI... Vui lòng đợi.")

model_detect  = YOLO(str(SEG_MODELS / "best-detect.pt"))
model_segment = YOLO(str(SEG_MODELS / "best-seg.pt"))

embedding_model = SentenceTransformer(
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

xgb_model = xgb.XGBClassifier()
if XGB_MODEL_PATH.exists():
    xgb_model.load_model(str(XGB_MODEL_PATH))
else:
    print(f"❌ Lỗi: Không tìm thấy model {XGB_MODEL_PATH}")
    sys.exit(1)

# Semantic anchor vectors
POSITIVE_VECTOR = embedding_model.encode([
    "order total, total amount to pay, grand total, final total, "
    "tổng cộng, tổng tiền, thành tiền, thanh toán, "
    "amount due, total due, balance due, total-eft, net total"
])[0]
NEGATIVE_VECTOR = embedding_model.encode([
    "tax, transaction ID, reference code, authorization, phone number, "
    "date, time, credit card, subtotal, tax amount, change due, tiền nhận, tiền thừa"
    "item code, sku, barcode"
])[0]

METADATA_BLACKLIST = {
    'tax', 'id', 'code', 'trn', 'auth', 'seq', 'acq',
    'phone', 'tel', 'date', 'time', 'mastercard', 'visa',
    'cashier', 'store', 'register', 'pm', 'am', 'terminal'
}

CURRENCY_PATTERN = re.compile(
    r'[\$€£¥₩₹₽₺₴₦฿₫₱¢]|USD|EUR|VND|JPY|GBP|AUD|CAD|SGD',
    re.IGNORECASE
)

NUMBER_PATTERN = re.compile(r'\b\d+(?:[\.,:]\d+)*\b')


# ─────────────────────────────────────────────────────
#  STEP 1: SEGMENTATION & FLATTEN  (YOLO + Tesseract)
# ─────────────────────────────────────────────────────
def _order_points(pts):
    """Sort 4 corner points: [TL, TR, BR, BL]."""
    rect = np.zeros((4, 2), dtype="float32")
    s    = pts.sum(axis=1)
    diff = np.diff(pts, axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def _flatten_receipt(image, pts):
    """Perspective-warp receipt to a top-down view."""
    rect = _order_points(pts)
    tl, tr, br, bl = rect

    width  = max(
        int(np.linalg.norm(br - bl)),
        int(np.linalg.norm(tr - tl))
    )
    height = max(
        int(np.linalg.norm(tr - br)),
        int(np.linalg.norm(tl - bl))
    )

    dst = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype="float32"
    )
    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, M, (width, height))


def img_scanner(img_path: str) -> str | None:
    """
    Detect → Segment → Flatten → Rotate → Threshold.
    Returns path to the cleaned image ready for OCR.
    """
    img_original = cv2.imread(img_path)
    if img_original is None:
        raise ValueError(f"Không thể đọc ảnh: {img_path}")

    # --- Detect ---
    det_results = model_detect(img_original)
    if not det_results[0].boxes:
        print("❌ Không detect được vùng chứa hóa đơn.")
        return None

    best_idx = int(det_results[0].boxes.conf.argmax())
    x1, y1, x2, y2 = map(int, det_results[0].boxes[best_idx].xyxy[0].tolist())
    cropped = img_original[y1:y2, x1:x2]

    # --- Segment ---
    seg_results = model_segment(cropped)
    if seg_results[0].masks is None:
        print("⚠️ Không tìm thấy mặt nạ đa giác.")
        return None

    polygon = seg_results[0].masks.xy[0]
    contour = np.array(polygon, dtype=np.int32)

    peri   = cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, 0.02 * peri, True)

    pts = approx.reshape(4, 2) if len(approx) == 4 else cv2.boxPoints(
        cv2.minAreaRect(contour)
    ).astype(int)

    # --- Flatten ---
    flat = _flatten_receipt(cropped, pts)

    # --- Rotate (Tesseract OSD) ---
    pytesseract.pytesseract.tesseract_cmd = (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )
    try:
        osd        = pytesseract.image_to_osd(flat, output_type=Output.DICT)
        angle      = osd["rotate"]
        confidence = osd["orientation_conf"]
        print(f"🔍 OSD dự đoán {angle}° | confidence: {confidence:.2f}")
        if confidence >= 4.0:
            ROTATE_MAP = {
                90:  cv2.ROTATE_90_CLOCKWISE,
                180: cv2.ROTATE_180,
                270: cv2.ROTATE_90_COUNTERCLOCKWISE,
            }
            if angle in ROTATE_MAP and angle not in [90, 270]:  # guard portrait
                flat = cv2.rotate(flat, ROTATE_MAP[angle])
        else:
            print("⚠️ OSD confidence quá thấp, bỏ qua xoay.")
    except Exception as e:
        print(f"⚠️ Lỗi OSD: {e}")

    # --- Adaptive threshold (CamScanner-style) ---
    gray     = cv2.cvtColor(flat, cv2.COLOR_BGR2GRAY)
    cleaned  = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 81, 21
    )

    # --- Save ---
    output_path = OUTPUT_DIR / "CAMSCANNER_RESULT.jpg"
    cv2.imwrite(str(output_path), cleaned)
    print(f"✅ Ảnh đã xuất tại: {output_path}")
    return str(output_path)


# ─────────────────────────────────────────────────────
#  STEP 2: OCR  (PaddleOCR via subprocess)
# ─────────────────────────────────────────────────────
def run_ocr(image_path: str) -> tuple[list, float]:
    """Run PaddleOCR in a subprocess to avoid GPU memory conflicts."""
    subprocess.run(
        [sys.executable, str(OCR_WORKER), image_path, str(OCR_TEMP)],
        check=True
    )
    with open(OCR_TEMP, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("ocr_data", []), float(data.get("img_height", 1000))


# ─────────────────────────────────────────────────────
#  STEP 3: CANDIDATE CLASSIFICATION  (XGBoost + NLP)
# ─────────────────────────────────────────────────────
def _parse_number(num_str: str) -> float | None:
    """Parse a raw number string (with separators) to float."""
    s = num_str.replace(' ', '')
    try:
        for sep in '.,:':
            if sep in s:
                parts    = s.split(sep)
                last     = parts[-1]
                if len(last) == 2:
                    main = ''.join(parts[:-1]).replace('.', '').replace(',', '')
                    return float(f"{main}.{last}")
                return float(s.replace('.', '').replace(',', '').replace(':', ''))
        return float(s)
    except ValueError:
        return None


def predict_total_with_xgboost(ocr_results: list, img_height: float) -> dict | None:
    """Extract numeric candidates, rank with XGBoost, return rich result.
    
    Returns dict:
        predicted_value: float   — best guess
        confidence:      float   — XGBoost probability (0–1)
        candidates:      list    — all candidates with features + scores
    """
    candidates = []

    for idx, (bbox, text) in enumerate(ocr_results):
        text_clean = text.strip()

        for match in NUMBER_PATTERN.finditer(text_clean):
            num_str   = match.group()
            s_idx, e_idx = match.span()
            raw_digits = re.sub(r'\D', '', num_str)

            if not raw_digits or len(raw_digits) > 12:
                continue

            value = _parse_number(num_str)
            if value is None:
                continue

            # Build neighbor context
            left  = text_clean[max(0, s_idx - 25):s_idx]
            right = text_clean[e_idx:e_idx + 15]

            # Look-back: if no letters/numbers on the left, peek at the previous line
            if not re.search(r'[a-zA-Z\d]', left) and idx > 0:
                prev_text = ocr_results[idx - 1][1]
                prev_line = prev_text[-25:] if not re.search(r'\d', prev_text) else ''
            else:
                prev_line = ''

            neighbor = f"{prev_line} {left} {right}".strip()
            if not neighbor:
                continue  # skip numbers with zero context

            y_center = float(np.mean([p[1] for p in bbox]))
            candidates.append({
                'value':        value,
                'normalized_y': y_center / img_height,
                'neighbor':     neighbor,
            })

    if not candidates:
        print("❌ OCR không tìm thấy bất kỳ con số có context nào.")
        return None

    # Batch-encode all neighbor texts in ONE call (much faster)
    texts        = [c['neighbor'] for c in candidates]
    vectors      = embedding_model.encode(texts, batch_size=32, show_progress_bar=False)

    for cand, vec in zip(candidates, vectors):
        cand['has_currency'] = 1.0 if CURRENCY_PATTERN.search(cand['neighbor']) else 0.0
        cand['text_length']  = float(len(cand['neighbor']))
        cand['semantic_sim'] = _semantic_sim_from_vec(vec, cand['neighbor'])

    # Determine max_bill_value (barcode guard)
    valid = [
        c['value'] for c in candidates
        if c['semantic_sim'] > 0.1
        and not (c['value'].is_integer()
                 and len(str(int(c['value']))) >= 5
                 and c['semantic_sim'] < 0.4)
    ]
    max_bill = max(valid) if valid else max(c['value'] for c in candidates)

    # Build feature matrix
    rows = []
    for c in candidates:
        c['is_max'] = 1.0 if c['value'] == max_bill else 0.0
        rows.append({
            'semantic_sim': c['semantic_sim'],
            'normalized_y': c['normalized_y'],
            'is_max':        c['is_max'],
            'text_length':   c['text_length'],
            'has_currency':  c['has_currency'],
        })

    df      = pd.DataFrame(rows)
    probs   = xgb_model.predict_proba(df[['semantic_sim', 'normalized_y',
                                           'is_max', 'text_length', 'has_currency']])[:, 1]

    for i, c in enumerate(candidates):
        c['xgb_score'] = float(probs[i])

    best = max(candidates, key=lambda x: x['xgb_score'])

    print("\n🔍 --- BẢNG XẾP HẠNG ỨNG VIÊN TỔNG TIỀN (XGBOOST) ---")
    for c in sorted(candidates, key=lambda x: x['xgb_score'], reverse=True)[:5]:
        print(f"Value: {c['value']:>10.2f} | Score: {c['xgb_score']*100:>5.1f}% | Context: '{c['neighbor']}'")

    MIN_CONFIDENCE = 0.4
    is_confident = best['xgb_score'] >= MIN_CONFIDENCE

    if not is_confident:
        print("\n⚠️ XGBoost không đủ tự tin — cần fallback SLM hoặc user validation.")

    return {
        'predicted_value': best['value'] if is_confident else None,
        'confidence':      best['xgb_score'],
        'candidates':      candidates,  # full list for feedback matching
    }


def _semantic_sim_from_vec(vec, text: str) -> float:
    """Like _semantic_sim but uses a pre-computed vector (for batch calls)."""
    if not re.search(r'[a-zA-ZÀ-ỹ]', text):
        return 0.0
    pos_sim = float(cosine_similarity([vec], [POSITIVE_VECTOR])[0][0])
    neg_sim = float(cosine_similarity([vec], [NEGATIVE_VECTOR])[0][0])
    if pos_sim < 0.25 or neg_sim >= pos_sim:
        return 0.0
    penalty = 0.1 if any(w in text.lower() for w in METADATA_BLACKLIST) else 1.0
    return pos_sim * penalty


# ─────────────────────────────────────────────────────
#  STEP 4: FEEDBACK LOOP  (save for retraining)
# ─────────────────────────────────────────────────────
FEEDBACK_CSV = CURRENT_DIR / "feedback_dataset.csv"
FEATURE_COLS = ['semantic_sim', 'normalized_y', 'is_max', 'text_length', 'has_currency', 'label']


def save_feedback(candidates: list, correct_value: float) -> bool:
    """Match correct_value to a candidate, save its features for retraining.
    
    - The candidate matching correct_value gets label=1
    - All other candidates get label=0
    
    Returns True if feedback was saved successfully.
    """
    rows = []
    matched = False

    for c in candidates:
        is_correct = abs(c['value'] - correct_value) < 0.01
        if is_correct:
            matched = True
        rows.append({
            'semantic_sim': c['semantic_sim'],
            'normalized_y': c['normalized_y'],
            'is_max':       c.get('is_max', 0.0),
            'text_length':  c['text_length'],
            'has_currency': c['has_currency'],
            'label':        1 if is_correct else 0,
        })

    if not matched:
        print(f"⚠️ Giá trị {correct_value} không khớp với bất kỳ candidate nào.")
        return False

    df_new = pd.DataFrame(rows, columns=FEATURE_COLS)

    if FEEDBACK_CSV.exists():
        df_old = pd.read_csv(FEEDBACK_CSV)
        df_all = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_all = df_new

    df_all.to_csv(FEEDBACK_CSV, index=False)
    print(f"✅ Đã lưu {len(rows)} dòng feedback vào {FEEDBACK_CSV}")
    return True


# ─────────────────────────────────────────────────────
#  END-TO-END PIPELINE
# ─────────────────────────────────────────────────────
def process_invoice(raw_image_path: str) -> dict:
    """Run full pipeline. Returns a dict for the app to consume:
    
    {
        'predicted_value': float | None,
        'confidence':      float,
        'candidates':      list,       # for feedback matching
        'ocr_text':        str,        # raw OCR for SLM fallback
        'flat_image_path': str | None,
        'status':          str,        # 'success' | 'low_confidence' | 'error'
    }
    """
    result = {
        'predicted_value': None,
        'confidence':      0.0,
        'candidates':      [],
        'ocr_text':        '',
        'flat_image_path': None,
        'status':          'error',
    }

    print(f"\n{'='*50}\nBẮT ĐẦU XỬ LÝ HÓA ĐƠN END-TO-END\n{'='*50}")

    # Step 1: Segmentation
    print("\n[1/3] YOLO Segmentation + Tesseract Rotation...")
    try:
        flat_path = img_scanner(raw_image_path)
    except Exception as e:
        print(f"❌ Lỗi Segmentation: {e}")
        return result

    if not flat_path or not os.path.exists(flat_path):
        print("❌ Không thể xuất ảnh nắn phẳng.")
        return result

    result['flat_image_path'] = flat_path

    # Step 2: OCR
    print("\n[2/3] PaddleOCR (subprocess)...")
    try:
        ocr_data, img_height = run_ocr(flat_path)
    except subprocess.CalledProcessError as e:
        print(f"❌ OCR subprocess crash! Code: {e.returncode}")
        return result

    if not ocr_data:
        print("❌ Không đọc được chữ nào trên hóa đơn.")
        return result

    # Build raw OCR text for SLM fallback
    result['ocr_text'] = '\n'.join(text for _, text in ocr_data)

    # Step 3: XGBoost classification
    print("\n[3/3] XGBoost candidate classification...")
    xgb_result = predict_total_with_xgboost(ocr_data, img_height)

    if xgb_result is None:
        return result

    result['predicted_value'] = xgb_result['predicted_value']
    result['confidence']      = xgb_result['confidence']
    result['candidates']      = xgb_result['candidates']
    result['status']          = 'success' if xgb_result['predicted_value'] else 'low_confidence'

    print(f"\n{'='*50}")
    if result['predicted_value']:
        print(f"💰 KẾT QUẢ CUỐI CÙNG: {result['predicted_value']}")
    else:
        print("⚠️ XGBoost không tự tin — App sẽ gọi SLM để xác nhận.")
    print(f"{'='*50}\n")

    return result


# ─────────────────────────────────────────────────────
#  ENTRY POINT  (for terminal testing)
# ─────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) > 1:
        img_path = sys.argv[1]
    else:
        img_path = str(PROJECT_ROOT / "Seg_OCR_Tri" / "input" / "test6.png")

    if not os.path.exists(img_path):
        print(f"❌ Không tìm thấy file ảnh: {img_path}")
        print("💡 Dùng: python main.py <đường_dẫn_ảnh>")
        sys.exit(1)

    result = process_invoice(img_path)

    # Demo: simulate user validation in terminal
    if result['status'] in ('success', 'low_confidence') and result['candidates']:
        print("\n--- [DEMO] User Validation ---")
        predicted = result['predicted_value']
        if predicted:
            confirm = input(f"Tổng tiền là {predicted}? (y/n): ").strip().lower()
        else:
            confirm = 'n'

        if confirm == 'y':
            save_feedback(result['candidates'], predicted)
            print("✅ Đã xác nhận và lưu feedback.")
        else:
            correct = input("Nhập số tiền đúng (hoặc 'slm' để gọi AI): ").strip()
            if correct.lower() == 'slm':
                print("🤖 Đang gọi SLM (Gemini)...")
                # Import SLM module dynamically to avoid loading it at startup
                sys.path.insert(0, str(PROJECT_ROOT / "SLM"))
                from SML import process_ocr_with_gemini
                slm_result = process_ocr_with_gemini(result['ocr_text'])
                correct_value = slm_result.total_amount
                print(f"🤖 SLM trả về: {correct_value}")
            else:
                correct_value = float(correct)

            saved = save_feedback(result['candidates'], correct_value)
            if not saved:
                print("⚠️ Giá trị từ SLM không khớp candidate nào — không thể lưu feedback.")
