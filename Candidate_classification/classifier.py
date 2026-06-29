import re
import numpy as np
import pandas as pd
from models import (embedding_model, POSITIVE_VECTORS, NEGATIVE_VECTORS,
                    QUANTITY_VECTORS, TAX_VECTORS, CURRENCY_PATTERN,
                    NUMBER_PATTERN, xgb_model, nli_classifier)
from config import FEEDBACK_CSV


def _parse_number(num_str: str) -> float | None:
    s = num_str.replace(' ', '')
    try:
        for sep in '.,:':
            if sep in s:
                parts = s.split(sep)
                last = parts[-1]
                if len(last) == 2:
                    main = ''.join(parts[:-1]).replace('.', '').replace(',', '')
                    return float(f"{main}.{last}")
                return float(s.replace('.', '').replace(',', '').replace(':', ''))
        return float(s)
    except ValueError:
        return None


def _semantic_sim_from_vec(vec, text: str) -> float:
    HAS_LETTERS = re.compile(
        r'[a-zA-ZÀ-ỹ'              # Latin + Vietnamese
        r'\u4E00-\u9FFF'            # Chinese (CJK Unified)
        r'\u3040-\u30FF'            # Japanese (Hiragana + Katakana)
        r'\uAC00-\uD7AF]')          # Korean (Hangul)
    if not HAS_LETTERS.search(text):
        return 0.0

    from sklearn.metrics.pairwise import cosine_similarity
    pos_sim = float(np.max(cosine_similarity([vec], POSITIVE_VECTORS)))
    neg_sim = float(np.max(cosine_similarity([vec], NEGATIVE_VECTORS)))
    qty_sim = float(np.max(cosine_similarity([vec], QUANTITY_VECTORS)))
    tax_sim = float(np.max(cosine_similarity([vec], TAX_VECTORS)))

    if pos_sim < 0.15:
        return 0.0
    if neg_sim >= pos_sim:
        return 0.0
    if qty_sim >= pos_sim:
        return 0.0
    if tax_sim >= pos_sim:
        return 0.0

    return pos_sim


def predict_total_with_xgboost(ocr_results: list, img_height: float) -> dict | None:
    candidates = []

    for idx, (bbox, text) in enumerate(ocr_results):
        text_clean = text.strip()

        for match in NUMBER_PATTERN.finditer(text_clean):
            num_str = match.group()
            s_idx, e_idx = match.span()
            raw_digits = re.sub(r'\D', '', num_str)

            if not raw_digits or len(raw_digits) > 12:
                continue

            value = _parse_number(num_str)
            if value is None:
                continue

            left = text_clean[max(0, s_idx - 25):s_idx]
            right = text_clean[e_idx:e_idx + 15]
            prev_line = ''

            if not re.search(r'[a-zA-Z\u00C0-\u024F\u4E00-\u9FFF]', left):
                y_center_current = float(np.mean([p[1] for p in bbox]))
                same_line_texts = []
                for other_bbox, other_text in ocr_results:
                    if other_text == text:
                        continue
                    other_y_center = float(np.mean([p[1] for p in other_bbox]))
                    if abs(other_y_center - y_center_current) < 45:
                        clean_text = re.sub(r'\d+', '', other_text).strip()
                        if len(clean_text) > 2:
                            same_line_texts.append(clean_text)

                if same_line_texts:
                    prev_line = " ".join(same_line_texts)[-40:]
                else:
                    fallback_texts = []
                    for i in range(max(0, idx - 3), idx):
                        clean_fallback = re.sub(r'\d+', '', ocr_results[i][1]).strip()
                        if len(clean_fallback) > 2:
                            fallback_texts.append(clean_fallback)
                    prev_line = " ".join(fallback_texts)[-40:]

            neighbor = f"{prev_line} {left} {right}".strip()
            if not neighbor:
                continue

            neighbor = re.sub(r'^[^\w\u00C0-\u024F\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF]+', '', neighbor)
            neighbor = re.sub(r'[^\w\u00C0-\u024F\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF]+$', '', neighbor).strip()

            real_letters = re.findall(r'[\w\u00C0-\u024F\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF]', neighbor)
            if len(real_letters) < 2:
                continue

            y_center = float(np.mean([p[1] for p in bbox]))
            candidates.append({'value': value, 'normalized_y': y_center / img_height, 'neighbor': neighbor})

    if not candidates:
        print("❌ OCR không tìm thấy bất kỳ con số có context nào.")
        return None

    texts = [c['neighbor'] for c in candidates]
    vectors = embedding_model.encode(texts, batch_size=32, show_progress_bar=False)

    for cand, vec in zip(candidates, vectors):
        match = CURRENCY_PATTERN.search(cand['neighbor'])
        cand['has_currency'] = 1.0 if match else 0.0
        cand['currency'] = match.group().strip() if match else None
        cand['text_length'] = float(len(cand['neighbor']))
        cand['semantic_sim'] = _semantic_sim_from_vec(vec, cand['neighbor'])

    valid = [
        c['value'] for c in candidates
        if c['semantic_sim'] > 0.1
        and not (c['value'].is_integer()
                 and len(str(int(c['value']))) >= 5
                 and c['semantic_sim'] < 0.4)
    ]
    max_bill = max(valid) if valid else max(c['value'] for c in candidates)

    rows = []
    for c in candidates:
        c['is_max'] = 1.0 if c['value'] == max_bill else 0.0
        rows.append({'semantic_sim': c['semantic_sim'], 'normalized_y': c['normalized_y'], 'is_max': c['is_max'], 'text_length': c['text_length'], 'has_currency': c['has_currency']})

    df = pd.DataFrame(rows)
    probs = xgb_model.predict_proba(df[['semantic_sim', 'normalized_y', 'is_max', 'text_length', 'has_currency']])[:, 1]

    for i, c in enumerate(candidates):
        raw_score = float(probs[i])
        if c['semantic_sim'] < 0.05:
            c['xgb_score'] = raw_score * 0.1
        elif c['semantic_sim'] < 0.15:
            c['xgb_score'] = raw_score * 0.75
        elif c['semantic_sim'] >= 0.7:
            c['xgb_score'] = max(raw_score, 0.95)
        elif c['semantic_sim'] >= 0.5:
            c['xgb_score'] = max(raw_score, 0.80)
        else:
            c['xgb_score'] = raw_score * (0.5 + c['semantic_sim'])

    best = max(candidates, key=lambda x: x['xgb_score'])

    print("\n --- BẢNG XẾP HẠNG ỨNG VIÊN TỔNG TIỀN (XGBOOST) ---")
    for c in sorted(candidates, key=lambda x: x['xgb_score'], reverse=True)[:5]:
        print(f"Value: {c['value']:>10.2f} | Score: {c['xgb_score']*100:>5.1f}% | Sem: {c['semantic_sim']:.2f} | is_max: {c['is_max']} | y: {c['normalized_y']:.2f} | Context: '{c['neighbor']}'")

    all_sem_zero = all(c['semantic_sim'] == 0.0 for c in candidates)
    MIN_CONFIDENCE = 0.25 if all_sem_zero else 0.4
    if all_sem_zero:
        print("NLP hoàn toàn thất bại (OCR lỗi / ngôn ngữ chưa hỗ trợ) → dùng structural-only mode (ngưỡng 25%).")

    is_confident = best['xgb_score'] >= MIN_CONFIDENCE

    print("\nKích hoạt NLI Reranker theo thứ tự: Sem > NLI > XGBoost...")
    if all_sem_zero:
        top_5 = sorted(candidates, key=lambda x: x['xgb_score'], reverse=True)[:5]
    else:
        top_5 = sorted(candidates, key=lambda x: (x['semantic_sim'], x['xgb_score']), reverse=True)[:5]

    nli_promoted = None
    nli_best_score = 0.0

    for c in top_5:
        if len(c['neighbor'].strip()) < 3:
            continue
        result = nli_classifier(c['neighbor'], ["total amount to pay", "tax amount", "transaction code or ID", "item quantity or subtotal"])
        best_label = result['labels'][0]
        best_prob = result['scores'][0]
        print(f"   - NLI đọc '{c['neighbor']}' [Sem: {c['semantic_sim']:.2f}]: {best_label} ({best_prob*100:.1f}%)")
        if best_label == "total amount to pay" and best_prob >= 0.40:
            if best_prob > nli_best_score:
                nli_promoted = c
                nli_best_score = best_prob

    if nli_promoted:
        best = nli_promoted
        is_confident = True
        print(f"\nNLI RERANK CHỐT: {best['value']} (NLI Conf: {nli_best_score*100:.1f}%, Sem: {best['semantic_sim']:.2f})")
    elif not is_confident:
        print("\n⚠️ XGBoost & NLI đều không tự tin — cần fallback SLM hoặc user validation.")

    return {'predicted_value': best['value'] if is_confident else None, 'currency': best.get('currency') if is_confident else None, 'confidence': best['xgb_score'], 'candidates': candidates}


def save_feedback(candidates: list, correct_value: float) -> bool:
    rows = []
    matched = False

    for c in candidates:
        is_correct = abs(c['value'] - correct_value) < 0.01
        if is_correct:
            matched = True
        rows.append({'semantic_sim': c['semantic_sim'], 'normalized_y': c['normalized_y'], 'is_max': c.get('is_max', 0.0), 'text_length': c['text_length'], 'has_currency': c['has_currency'], 'label': 1 if is_correct else 0})

    if not matched:
        print(f"Giá trị {correct_value} không khớp với bất kỳ candidate nào.")
        return False

    df_new = pd.DataFrame(rows, columns=['semantic_sim', 'normalized_y', 'is_max', 'text_length', 'has_currency', 'label'])

    if FEEDBACK_CSV.exists():
        df_old = pd.read_csv(FEEDBACK_CSV)
        df_all = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_all = df_new

    df_all.to_csv(FEEDBACK_CSV, index=False)
    print(f"✅ Đã lưu {len(rows)} dòng feedback vào {FEEDBACK_CSV}")
    return True
