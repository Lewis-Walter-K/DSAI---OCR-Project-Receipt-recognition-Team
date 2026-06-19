import os
import shutil
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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

# Setup CORS for React Frontend (typically running on localhost:5173 or localhost:5174)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.post("/api/llm-parse")
async def llm_parse_invoice(file: UploadFile = File(...)):
    """
    Human-triggered LLM fallback endpoint.
    Called from the Edit page when the user clicks "Ask AI (Gemini)".
    Bypasses XGBoost and sends the image directly to Gemini for structured extraction.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected")

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_path = temp_file.name
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
    finally:
        file.file.close()

    try:
        import google.generativeai as genai
        from PIL import Image

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="GEMINI_API_KEY not set in environment")

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")

        image = Image.open(temp_path)
        prompt = (
            "You are a receipt parser. Extract the following fields from this receipt image and return ONLY valid JSON:\n"
            "{\n"
            '  "total_amount": <number, the final total to pay>,\n'
            '  "currency": "<3-letter ISO currency code, e.g. VND, USD>",\n'
            '  "bill_purpose": "<one of: Eating, Coffee, Shopping, Groceries, Transport, Utilities, Entertainment, Health, Other>",\n'
            '  "bill_date": "<YYYY-MM-DD format, today if unclear>"\n'
            "}\n"
            "Return ONLY the JSON object, no explanation."
        )

        response = model.generate_content([prompt, image])
        raw = response.text.strip().strip("```json").strip("```").strip()

        import json
        parsed = json.loads(raw)

        return {
            "predicted_value": parsed.get("total_amount"),
            "confidence": 1.0,
            "candidates": [],
            "status": "llm_fallback",
            "currency": parsed.get("currency", "VND"),
            "structured_data": {
                "bill_purpose": parsed.get("bill_purpose"),
                "bill_date": parsed.get("bill_date"),
                "currency": parsed.get("currency"),
                "total_amount": parsed.get("total_amount"),
            }
        }

    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Gemini returned non-JSON response. Try again.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Parse Error: {e}")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
