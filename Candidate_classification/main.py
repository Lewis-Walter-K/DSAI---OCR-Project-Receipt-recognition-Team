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
import pytesseract
from ultralytics import YOLO
from pytesseract import Output
from transformers import pipeline

# ─────────────────────────────────────────────────────
#  PATH SETUP  (works on any machine, any user)
# ─────────────────────────────────────────────────────
load_dotenv()
CURRENT_DIR  = Path(__file__).resolve().parent          # .../Candidate_classification
PROJECT_ROOT = CURRENT_DIR.parent                       # .../invoice-reader
SEG_MODELS   = CURRENT_DIR / "models"
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

nli_classifier = pipeline(
    "zero-shot-classification", 
    model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
)

NLI_LABELS = [
    "total amount to pay", 
    "tax amount", 
    "transaction code or ID", 
    "item quantity or subtotal"
]

xgb_model = xgb.XGBClassifier()
if XGB_MODEL_PATH.exists():
    xgb_model.load_model(str(XGB_MODEL_PATH))
else:
    print(f"❌ Lỗi: Không tìm thấy model {XGB_MODEL_PATH}")
    sys.exit(1)

# ── Semantic anchor vectors ─────────────────────────────────────────
# Architecture: 4 anchors covering all major "noise" categories.
# A candidate's context must be CLOSER to POSITIVE than ALL other anchors.
# Adding a new language = add 1 line per anchor. No blacklists ever needed.
def _flatten(prompts):
    return [x.strip() for p in prompts for x in p.split(',') if x.strip()]

_pos_prompts = _flatten([
    "order total, grand total, total amount to pay, amount due, balance due, net total, total-eft",  # EN
    "tổng cộng, tổng tiền, thành tiền, thanh toán, số tiền thanh toán",                             # VI
    "tong cong, tong tien, thanh tien, thanh toan, so tien thanh toan",                             # VI (no accent)
    "消费合计, 合计, 总计, 实付金额, 应付金额, 收款金额, 结账金额",                                          # ZH
    "合計, お会計, 請求金額, 支払合計, お支払い金額",                                                      # JA
    "합계, 총액, 결제금액, 청구금액, 지불합계",                                                          # KO
])
_neg_prompts = _flatten([
    "transaction ID, reference code, authorization code, barcode, serial number, phone number",     # EN
    "mã giao dịch, mã tham chiếu, mã vạch, số điện thoại, mã hóa đơn, tiền thừa, tiền nhận",        # VI
    "ma giao dich, ma tham chieu, ma vach, so dien thoai, ma hoa don, tien thua, tien nhan, thira", # VI (no accent + OCR errors)
    "交易号, 参考号, 条形码, 电话, 授权码, 流水号",                                                        # ZH
    "取引ID, 参照番号, バーコード, 電話番号, シリアル番号",                                                   # JA
])
_qty_prompts = _flatten([
    "number of items, quantity, item count, total pieces, total units",                             # EN
    "số lượng, số món, số cái, tổng số lượng",                                                      # VI
    "so luong, so mon, so cai, tong so luong",                                                      # VI (no accent)
    "数量, 点数, 個数, 件数",                                                                           # ZH/JA
    "수량, 개수, 총수량",                                                                              # KO
])
_tax_prompts = _flatten([
    "tax amount, VAT, consumption tax, sales tax, service tax, tax included",                       # EN
    "tiền thuế, thuế VAT, thuế tiêu thụ đặc biệt, phí dịch vụ",                                   # VI
    "tien thue, thue vat, thue tieu thu dac biet, phi dich vu",                                     # VI (no accent)
    "税额, 增值税, 消费税, 税, 含税",                                                                     # ZH
    "消費税, 内消費税, 税込, 税額, 内税",                                                                 # JA
    "세금, 부가세, 소비세",                                                                            # KO
])
# Store the full matrix of embeddings instead of averaging them!
# Averaging English, Vietnamese, and Chinese together creates a "Frankenstein" vector
# that matches none of them perfectly. By keeping them separate, we can use 
# k-NN (Max Similarity) to match the closest language directly!
POSITIVE_VECTORS = embedding_model.encode(_pos_prompts)  # Shape: (N_pos, 384)
NEGATIVE_VECTORS = embedding_model.encode(_neg_prompts)
QUANTITY_VECTORS = embedding_model.encode(_qty_prompts)
TAX_VECTORS      = embedding_model.encode(_tax_prompts)

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

            # --- BƯỚC 1: LÀM SẠCH DẤU HIỆU ĐẦU/CUỐI ---
            # Strip các ký tự không phải chữ hoặc số ở đầu và cuối
            # Ví dụ: '.竹笙' → '竹笙', '- Total' → 'Total'
            neighbor = re.sub(r'^[^\w\u00C0-\u024F\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF]+', '', neighbor)
            neighbor = re.sub(r'[^\w\u00C0-\u024F\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF]+$', '', neighbor).strip()

            # --- BƯỚC 2: BỘ LỌC CONTEXT CHẤT LƯỢNG ---
            # Yêu cầu ít nhất 2 ký tự chữ thực sự sau khi đã làm sạch
            real_letters = re.findall(r'[\w\u00C0-\u024F\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF]', neighbor)
            if len(real_letters) < 2:
                continue  # context vô nghĩa, bỏ qua

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
        match = CURRENCY_PATTERN.search(cand['neighbor'])
        cand['has_currency'] = 1.0 if match else 0.0
        cand['currency']     = match.group().strip() if match else None
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
        raw_score = float(probs[i])
        # --- ĐIỀU CHỈNH THEO NGỮ NGHĨA (Semantic Reweighting) ---
        # Nếu NLP không tìm thấy bất kỳ sự liên quan nào đến "Tổng tiền",
        # giảm điểm XGBoost xuống 50% để ngăn "tên món ăn" hoặc
        # "số ngẫu nhiên" chiếm Top 1 nhờ vị trí cuối trang.
        if c['semantic_sim'] < 0.05:
            c['xgb_score'] = raw_score * 0.5
        elif c['semantic_sim'] < 0.15:
            c['xgb_score'] = raw_score * 0.75
        else:
            c['xgb_score'] = raw_score

    best = max(candidates, key=lambda x: x['xgb_score'])

    print("\n🔍 --- BẢNG XẾP HẠNG ỨNG VIÊN TỔNG TIỀN (XGBOOST) ---")
    for c in sorted(candidates, key=lambda x: x['xgb_score'], reverse=True)[:5]:
        print(f"Value: {c['value']:>10.2f} | Score: {c['xgb_score']*100:>5.1f}% | Sem: {c['semantic_sim']:.2f} | is_max: {c['is_max']} | y: {c['normalized_y']:.2f} | Context: '{c['neighbor']}'")

    # ── Adaptive confidence threshold ────────────────────────────────────
    # Normal mode: NLP + XGBoost agree → require 40% confidence
    # Degraded mode: ALL semantic_sim = 0 (OCR corruption / unknown script)
    #   → trust XGBoost structural features alone with lower bar (25%)
    all_sem_zero = all(c['semantic_sim'] == 0.0 for c in candidates)
    MIN_CONFIDENCE = 0.25 if all_sem_zero else 0.4
    if all_sem_zero:
        print("⚠️ NLP hoàn toàn thất bại (OCR lỗi / ngôn ngữ chưa hỗ trợ) → dùng structural-only mode (ngưỡng 25%).")

    is_confident = best['xgb_score'] >= MIN_CONFIDENCE

    # ── Hybrid NLI Reranker (Trọng tài Logic) ────────────────────────────
    # We call the heavy NLI model to inspect the Top 5 candidates from XGBoost.
    print("\n🧠 Kích hoạt NLI Reranker trên Top 5 ứng viên...")
    top_5 = sorted(candidates, key=lambda x: x['xgb_score'], reverse=True)[:5]
    nli_promoted = None
    nli_best_score = 0.0

    for c in top_5:
        # We don't bother asking NLI if there's almost no context
        if len(c['neighbor'].strip()) < 3:
            continue

        result = nli_classifier(c['neighbor'], NLI_LABELS)
        best_label = result['labels'][0]
        best_prob = result['scores'][0]

        print(f"   - NLI đọc '{c['neighbor']}': {best_label} ({best_prob*100:.1f}%)")

        # Check if NLI believes this is the total amount
        if best_label == "total amount to pay" and best_prob > 0.50:
            if best_prob > nli_best_score:
                nli_promoted = c
                nli_best_score = best_prob
    
    if nli_promoted:
        best = nli_promoted
        is_confident = True
        print(f"\n🎯 NLI RERANK CHỐT: {best['value']} (NLI Conf: {nli_best_score*100:.1f}%)")
    elif not is_confident:
        print("\n⚠️ XGBoost & NLI đều không tự tin — cần fallback SLM hoặc user validation.")

    return {
        'predicted_value': best['value'] if is_confident else None,
        'currency':        best.get('currency') if is_confident else None,
        'confidence':      best['xgb_score'],
        'candidates':      candidates,  # full list for feedback matching
    }


def _semantic_sim_from_vec(vec, text: str) -> float:
    """Compute semantic similarity using a pre-computed vector (for batch calls).
    Supports Latin, Vietnamese, Chinese, Japanese, Korean scripts.
    """
    # Skip if text has no real letters at all (pure numbers/symbols)
    HAS_LETTERS = re.compile(
        r'[a-zA-ZÀ-ỹ'              # Latin + Vietnamese
        r'\u4E00-\u9FFF'            # Chinese (CJK Unified)
        r'\u3040-\u30FF'            # Japanese (Hiragana + Katakana)
        r'\uAC00-\uD7AF]'           # Korean (Hangul)
    )
    if not HAS_LETTERS.search(text):
        return 0.0

    # ── k-NN (Max Similarity) matching ───────────────────────────────────
    # Instead of comparing to an averaged centroid, compare to ALL language
    # prompts in the category and pick the MAXIMUM similarity.
    # This prevents vector dilution and fixes the "unaccented OCR" problem natively.
    pos_sim = float(np.max(cosine_similarity([vec], POSITIVE_VECTORS)))
    neg_sim = float(np.max(cosine_similarity([vec], NEGATIVE_VECTORS)))
    qty_sim = float(np.max(cosine_similarity([vec], QUANTITY_VECTORS)))
    tax_sim = float(np.max(cosine_similarity([vec], TAX_VECTORS)))

    # ── 4-way semantic gate (no blacklists, works for any language) ──────
    # Rule: context must be CLOSER to POSITIVE than every other anchor.
    # If any anchor beats POSITIVE → this number is NOT a total amount.
    if pos_sim < 0.15:          return 0.0   # too weak overall
    if neg_sim >= pos_sim:      return 0.0   # closer to IDs/barcodes
    if qty_sim >= pos_sim:      return 0.0   # closer to item count
    if tax_sim >= pos_sim:      return 0.0   # closer to tax amount

    return pos_sim


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
        print(f"Giá trị {correct_value} không khớp với bất kỳ candidate nào.")
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
        'currency':        None,
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
    result['currency']        = xgb_result.get('currency')
    result['confidence']      = xgb_result['confidence']
    result['candidates']      = xgb_result['candidates']
    result['status']          = 'success' if xgb_result['predicted_value'] else 'low_confidence'

    print(f"\n{'='*50}")
    if result['predicted_value']:
        print(f"🎯 KẾT QUẢ CUỐI CÙNG: {result['predicted_value']}")
    else:
        print("⚠️ XGBoost & NLI không tự tin — KÍCH HOẠT SLM FALLBACK...")
        import sys
        slm_path = str(CURRENT_DIR.parent / "SLM")
        if slm_path not in sys.path:
            sys.path.append(slm_path)
        from slm_api import process_ocr_with_gemini
        
        slm_result = process_ocr_with_gemini(result['ocr_text'])
        print(f"🧠 SLM JSON OUTPUT:\n{slm_result.model_dump_json(indent=2)}")
        
        # Update pipeline result with SLM fallback data
        result['predicted_value'] = slm_result.total_amount
        result['status'] = 'slm_fallback'
        # Pass the full JSON structure back to the frontend/database
        result['structured_data'] = slm_result.model_dump()
        
    print(f"{'='*50}\n")

    return result


# ─────────────────────────────────────────────────────
#  ENTRY POINT  (for terminal testing)
# ─────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("image_or_cmd", nargs='?', default=str(CURRENT_DIR / "input" / "test1.jpg"))
    parser.add_argument("--feedback", action="store_true", help="Submit feedback")
    parser.add_argument("--candidates", type=str, help="JSON string of candidates")
    parser.add_argument("--correct_value", type=float, help="Correct value for feedback")
    args = parser.parse_args()

    if args.feedback:
        if args.candidates and args.correct_value is not None:
            candidates = json.loads(args.candidates)
            save_feedback(candidates, args.correct_value)
            print("===RESULT_JSON_START===")
            print(json.dumps({"status": "success"}))
            print("===RESULT_JSON_END===")
        else:
            print("===RESULT_JSON_START===")
            print(json.dumps({"status": "error", "message": "Missing candidates or correct_value"}))
            print("===RESULT_JSON_END===")
        sys.exit(0)

    img_path = args.image_or_cmd
    if not os.path.exists(img_path):
        print("===RESULT_JSON_START===")
        print(json.dumps({"status": "error", "message": f"File not found: {img_path}"}))
        print("===RESULT_JSON_END===")
        sys.exit(1)

    result = process_invoice(img_path)
    print("===RESULT_JSON_START===")
    print(json.dumps(result))
    print("===RESULT_JSON_END===")
