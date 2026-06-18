import sys
import json
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

input_path = sys.argv[1]
output_file = sys.argv[2]

import cv2
from paddleocr import PaddleOCR

def ocr_and_fix_orientation_v2(image_path, ocr_model):
    print(f"Dang xu ly anh {image_path}")
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Không thể đọc ảnh: {image_path}")
        
    best_image = img.copy()
    result = ocr_model.ocr(best_image, cls=False)
    
    final_text_results = []
    if result and result[0] is not None:
        lines = result[0] if isinstance(result[0], list) else result
        for line in lines:
            if line and len(line) == 2:
                bbox = line[0]        
                text = line[1][0]     
                final_text_results.append((bbox, text))

    return final_text_results, best_image.shape[0]

print("Khoi tao PaddleOCR (Doc lap)...")
ocr_model = PaddleOCR(use_angle_cls=False, show_log=False, use_gpu=False)

results = {}

if os.path.isfile(input_path):
    img_files = [input_path]
    is_single_file = True
else:
    img_files = [os.path.join(input_path, f) for f in os.listdir(input_path) if f.endswith(('.jpg', '.png'))]
    is_single_file = False

for count, img_path in enumerate(img_files, 1):
    img_name = os.path.basename(img_path)
    try:
        ocr_data, img_height = ocr_and_fix_orientation_v2(img_path, ocr_model)
        clean_ocr = []
        for bbox, text in ocr_data:
            clean_bbox = [[float(p[0]), float(p[1])] for p in bbox]
            clean_ocr.append([clean_bbox, text])
        
        if is_single_file:
            # If single file, save directly at root level to match extract_text.ipynb logic
            results = {"ocr_data": clean_ocr, "img_height": float(img_height)}
        else:
            results[img_name] = {"ocr_data": clean_ocr, "img_height": float(img_height)}
            
        print(f"[{count}/{len(img_files)}] Da xu ly: {img_name}", flush=True)
    except Exception as e:
        print(f"Loi OCR {img_name}: {e}", flush=True)

with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False)
