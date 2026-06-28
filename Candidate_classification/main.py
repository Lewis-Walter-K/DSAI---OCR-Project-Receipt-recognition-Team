import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Setup paths
load_dotenv()
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import refactored modules
from config import OUTPUT_DIR, OCR_WORKER, OCR_TEMP
from segmentation import img_scanner
from ocr import run_ocr
from classifier import predict_total_with_xgboost, save_feedback

# Optional SLM fallback (Gemini / Google Generative API)
try:
    from SLM.slm_api import process_ocr_with_gemini
    _SLM_AVAILABLE = True
except Exception:
    _SLM_AVAILABLE = False


def process_invoice(raw_image_path: str) -> dict:
    """Thin orchestrator: segmentation -> OCR -> classification."""
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
    print("\n[1/3] Segmentation...")
    try:
        flat_path = img_scanner(raw_image_path)
    except Exception as e:
        print(f"Lỗi Segmentation: {e}")
        return result

    if not flat_path or not os.path.exists(flat_path):
        print("Không thể xuất ảnh nắn phẳng.")
        return result

    result['flat_image_path'] = flat_path

    # Step 2: OCR
    print("\n[2/3] OCR (PaddleOCR subprocess)...")
    try:
        ocr_data, img_height = run_ocr(flat_path)
    except subprocess.CalledProcessError as e:
        print(f"OCR subprocess crash! Code: {e.returncode}")
        return result
    except Exception as e:
        print(f"OCR error: {e}")
        return result

    if not ocr_data:
        print("Không đọc được chữ nào trên hóa đơn.")
        return result

    result['ocr_text'] = '\n'.join(text for _, text in ocr_data)

    # Step 3: Classification
    print("\n[3/3] Candidate classification...")
    xgb_result = predict_total_with_xgboost(ocr_data, img_height)
    if xgb_result is None:
        return result

    result['predicted_value'] = xgb_result['predicted_value']
    result['currency']        = xgb_result.get('currency')
    result['confidence']      = xgb_result['confidence']
    result['candidates']      = xgb_result['candidates']
    result['status']          = 'success' if xgb_result['predicted_value'] else 'low_confidence'
    # If XGBoost/NLI are not confident, try SLM fallback (if available)
    if (result['predicted_value'] is None or (result['confidence'] and result['confidence'] < 0.4)) and _SLM_AVAILABLE:
        print("\n🤖 Fallback: calling SLM to extract from raw OCR text...")
        try:
            slm_out = process_ocr_with_gemini(result['ocr_text'])
            if getattr(slm_out, 'total_amount', 0.0):
                result['predicted_value'] = float(slm_out.total_amount)
                result['currency'] = getattr(slm_out, 'currency', result['currency'])
                result['confidence'] = 0.5  # mark as medium confidence
                result['status'] = 'slm_fallback'
                print(f"✅ SLM fallback returned: {result['predicted_value']} {result['currency']}")
            else:
                print("SLM fallback did not return a valid total.")
        except Exception as e:
            print(f"SLM fallback error: {e}")

    print(f"\n{'='*50}")
    if result['predicted_value']:
        print(f"🎯 KẾT QUẢ CUỐI CÙNG: {result['predicted_value']}")
    else:
        print("⚠️ XGBoost & NLI không tự tin — (SLM FALLBACK IS TEMPORARILY DISABLED)")
    print(f"{'='*50}\n")

    return result


if __name__ == '__main__':
    import argparse
    import subprocess

    parser = argparse.ArgumentParser()
    parser.add_argument('image_or_cmd', nargs='?', default=str(CURRENT_DIR / 'input' / 'test1.jpg'))
    parser.add_argument('--feedback', action='store_true')
    parser.add_argument('--candidates', type=str)
    parser.add_argument('--correct_value', type=float)
    args = parser.parse_args()

    if args.feedback:
        if args.candidates and args.correct_value is not None:
            candidates = json.loads(args.candidates)
            save_feedback(candidates, args.correct_value)
            print('===RESULT_JSON_START===')
            print(json.dumps({'status': 'success'}))
            print('===RESULT_JSON_END===')
        else:
            print('===RESULT_JSON_START===')
            print(json.dumps({'status': 'error', 'message': 'Missing candidates or correct_value'}))
            print('===RESULT_JSON_END===')
        sys.exit(0)

    img_path = args.image_or_cmd
    if not os.path.exists(img_path):
        print('===RESULT_JSON_START===')
        print(json.dumps({'status': 'error', 'message': f'File not found: {img_path}'}))
        print('===RESULT_JSON_END===')
        sys.exit(1)
    
    result = process_invoice(img_path)

    # DEBUGGING 
    # print('===RESULT_JSON_START===')
    # print(json.dumps(result))
    # print('===RESULT_JSON_END===')
