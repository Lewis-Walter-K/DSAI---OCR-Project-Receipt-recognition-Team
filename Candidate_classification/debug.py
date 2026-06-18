import json, re
import numpy as np
import pandas as pd
import xgboost as xgb
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

with open('temp_ocr_results.json', 'r', encoding='utf-8') as f:
    ocr_output = json.load(f)

easyocr_results = ocr_output['ocr_data']
img_height = ocr_output['img_height']

xgb_model = xgb.XGBClassifier()
xgb_model.load_model('xgb_total_model.json')

embedding_model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
POSITIVE_VECTOR = embedding_model.encode(['order total, total amount to pay, grand total, final total, total'])[0]
NEGATIVE_VECTOR = embedding_model.encode(['transaction ID, reference code, authorization, phone number, date, time, credit card, subtotal, tax amount, change due, item code, sku, barcode'])[0]

CURRENCY_PATTERN = re.compile(r'[\$€£¥₩₹₽₺₴₦฿₫₱¢]|USD|EUR|VND|JPY|GBP|AUD|CAD|SGD', re.IGNORECASE)
metadata_blacklist = ['id', 'code', 'trn', 'auth', 'seq', 'acq', 'phone', 'tel', 'date', 'time', 'mastercard', 'visa']

candidates = []
all_values = []

for idx, res in enumerate(easyocr_results):
    bbox, text = res
    text_clean = text.strip()
    
    for match in re.finditer(r'\b\d+(?:[\.,:]\d+)*\b', text_clean):
        num_str = match.group()
        start_idx, end_idx = match.span()
        
        raw_digits = re.sub(r'\D', '', num_str)
        if not raw_digits or len(raw_digits) > 12: continue
            
        s = num_str.replace(' ', '')
        if '.' in s or ',' in s or ':' in s:
            sep = '.' if '.' in s else (',' if ',' in s else ':')
            parts = s.split(sep)
            last_part = parts[-1]
            if len(last_part) == 2:
                main_part = ''.join(parts[:-1]).replace('.', '').replace(',', '')
                clean_val = float(f"{main_part}.{last_part}")
            else:
                clean_val = float(s.replace('.', '').replace(',', '').replace(':', ''))
        else:
            clean_val = float(s)
            
        all_values.append(clean_val)
        y_center = np.mean([point[1] for point in bbox])
        normalized_y = y_center / img_height
        
        left_window = text_clean[max(0, start_idx - 25):start_idx]
        right_window = text_clean[end_idx:min(len(text_clean), end_idx + 15)]
        
        has_letters = bool(re.search(r'[a-zA-Z]', left_window))
        has_numbers = bool(re.search(r'\d', left_window))
        
        if not has_letters and not has_numbers and idx > 0:
            potential_prev_line = easyocr_results[idx - 1][1]
            if not re.search(r'\d', potential_prev_line):
                prev_line = potential_prev_line[-25:]
            else:
                prev_line = ''
        else:
            prev_line = ''
            
        neighbor_text = f"{prev_line} {left_window} {right_window}".strip()
        candidates.append({'value': clean_val, 'normalized_y': normalized_y, 'neighbor_text': neighbor_text, 'raw_text': text})

max_bill_value = max(all_values) if all_values else 1
features_list = []

for cand in candidates:
    is_max = 1.0 if cand['value'] == max_bill_value else 0.0
    has_currency = 1.0 if CURRENCY_PATTERN.search(cand['neighbor_text']) else 0.0
    text_length = len(cand['neighbor_text'])
    
    if cand['neighbor_text']:
        if not re.search(r'[a-zA-Z]', cand['neighbor_text']):
            semantic_sim = 0.0
        else:
            cand_vector = embedding_model.encode([cand['neighbor_text']])[0]
            pos_sim = cosine_similarity([cand_vector],[POSITIVE_VECTOR])[0][0]
            neg_sim = cosine_similarity([cand_vector],[NEGATIVE_VECTOR])[0][0]
            if pos_sim < 0.25 or neg_sim > pos_sim:
                semantic_sim = 0.0
            else:
                semantic_sim = pos_sim
            if any(word in cand['neighbor_text'].lower() for word in metadata_blacklist):
                semantic_sim *= 0.1
    else:
        semantic_sim = 0.0
        
    features_list.append({
        'semantic_sim': float(semantic_sim),
        'normalized_y': float(cand['normalized_y']),
        'is_max': float(is_max),
        'text_length': float(text_length),
        'has_currency': float(has_currency),
        'value': cand['value'],
        'neighbor_text': cand['neighbor_text'],
        'raw_text': cand['raw_text']
    })

df_features = pd.DataFrame(features_list)
X_pred = df_features[['semantic_sim', 'normalized_y', 'is_max', 'text_length', 'has_currency']]
probabilities = xgb_model.predict_proba(X_pred)[:, 1]

for i, cand in enumerate(features_list):
    cand['xgb_score'] = float(probabilities[i])

print('=== ALL 97.33 ===')
for c in features_list:
    if c['value'] == 97.33:
        print(c)

print('\n=== ALL CANDIDATES ===')
for c in features_list:
    print(f"{c['value']} | {c['xgb_score']:.3f} | '{c['neighbor_text']}'")
