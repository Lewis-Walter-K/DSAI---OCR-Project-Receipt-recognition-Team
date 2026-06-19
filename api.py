import os
import shutil
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Any

# Import AI Pipeline modules
import sys
from pathlib import Path
CURRENT_DIR = Path(__file__).resolve().parent
CANDIDATE_DIR = CURRENT_DIR / "Candidate_classification"
if str(CANDIDATE_DIR) not in sys.path:
    sys.path.append(str(CANDIDATE_DIR))

try:
    from Candidate_classification.main import process_invoice, save_feedback
except ImportError as e:
    print(f"Error importing AI pipeline: {e}")
    # Define mocks for testing if imports fail
    def process_invoice(img_path): return {"predicted_value": 0, "candidates": []}
    def save_feedback(candidates, correct_value): return True


app = FastAPI(title="Invoice OCR API")

# CORS must be registered BEFORE any mount() calls
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins during development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve processed images from Candidate_classification/outputs/
OUTPUTS_DIR = CURRENT_DIR / "Candidate_classification" / "outputs"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static/outputs", StaticFiles(directory=str(OUTPUTS_DIR)), name="outputs")


class FeedbackRequest(BaseModel):
    correct_value: float
    candidates: List[Any]


@app.post("/api/upload")
async def upload_invoice(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected")

    # Create a temporary file to store the uploaded image
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_path = temp_file.name
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
    finally:
        file.file.close()

    try:
        # Pass the temporary file path to the AI pipeline
        result = process_invoice(temp_path)
        
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)

        # Inject the processed image URL into the response
        camscanner_path = OUTPUTS_DIR / "CAMSCANNER_RESULT.jpg"
        if camscanner_path.exists():
            # Add cache-busting timestamp so browser always fetches latest
            import time
            result["processed_image_url"] = f"http://localhost:8000/static/outputs/CAMSCANNER_RESULT.jpg?t={int(time.time())}"

        return result
    except Exception as e:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail=f"AI Pipeline Error: {e}")


@app.post("/api/feedback")
async def submit_feedback(data: FeedbackRequest):
    try:
        success = save_feedback(data.candidates, data.correct_value)
        if success:
            return {"status": "success", "message": "Feedback saved successfully"}
        else:
            return {"status": "error", "message": "Failed to save feedback"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Feedback Error: {e}")


import sys
slm_path = str(CURRENT_DIR / "SLM")
if slm_path not in sys.path:
    sys.path.append(slm_path)
from slm_api import process_ocr_with_gemini

class LlmParseRequest(BaseModel):
    ocr_text: str

@app.post("/api/llm-parse")
async def llm_parse_invoice(request: LlmParseRequest):
    """
    Human-triggered LLM fallback endpoint.
    Called from the Edit page when the user clicks "Ask AI (Gemini)".
    Passes the OCR text directly to the SLM API for parsing.
    """
    if not request.ocr_text:
        raise HTTPException(status_code=400, detail="No OCR text provided")

    try:
        slm_result = process_ocr_with_gemini(request.ocr_text)
        
        # Format response to match frontend expectations
        print("Kết quả call LLM: ")
        print(slm_result)
        return {
            "predicted_value": slm_result.total_amount,
            "confidence": 1.0,
            "candidates": [],
            "status": "llm_fallback",
            "currency": slm_result.currency,
            "structured_data": {
                "bill_date": slm_result.date,
                "currency": slm_result.currency,
                "total_amount": slm_result.total_amount
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Processing Error: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
