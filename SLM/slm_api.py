import json
import os
import google.generativeai as genai
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# 1. Schema for structured JSON output
class InvoiceStructuredOutput(BaseModel):
    vendor: str = Field(..., description="Tên nhà cung cấp, nếu có thể trích xuất được")
    date: str = Field(..., description="Ngày tháng trên hóa đơn, nếu có thể trích xuất được")
    total_amount: float = Field(..., description="Tổng số tiền trên hóa đơn, nếu có thể trích xuất được")
    currency: str = Field(..., description="Mã ISO của loại tiền tệ, nếu có thể trích xuất được")

def process_ocr_with_gemini(ocr_text: str) -> InvoiceStructuredOutput:
    load_dotenv()
    MY_API_KEY = os.getenv("GOOGLE_API_KEY")
    if not MY_API_KEY:
        print("⚠️ API Key không tồn tại. Vui lòng thiết lập GOOGLE_API_KEY trong file .env")
        return InvoiceStructuredOutput(vendor="UNKNOWN", date="UNKNOWN", total_amount=0.0, currency="VND")

    genai.configure(api_key=MY_API_KEY)

    system_instruction = (
        "You are an expert financial AI specializing in multilingual invoice parsing (Asia & Europe).\n"
        "Your task is to analyze the raw OCR text and extract structured information strictly fitting the schema.\n\n"
        "DISAMBIGUATION RULES:\n"
        "1. CHINA vs TAIWAN: 400-hotline/0371 = CNY. 統一編號/02-hotline = TWD.\n"
        "2. Tax IDs: 'MST' -> VND | 'VAT Reg' -> GBP/EUR | '納稅人識別號' -> CNY\n"
        "3. If no indicators are found, fallback to 'VND'.\n"
        "OUTPUT FORMAT (STRICT):\n"
        "You must respond ONLY with a valid JSON object. You are FORBIDDEN to use any keys other than the following 4 keys:\n"
        '1. "vendor" (string): The store name, You MUST fix OCR spelling errors, restore missing diacritics, and capitalize properly based on context.\n'
        '2. "date" (string): The date in YYYY-MM-DD format.\n'
        '3. "total_amount" (float): The final paid amount. MUST be a pure number without commas or currency symbols (e.g., 47000 or 47000.5).\n'
        '4. "currency" (string): The ISO currency code.\n'
        "Do not add extra keys like 'merchant_name', 'change_returned', or 'tax'."
    )
    
    try:
        model = genai.GenerativeModel(
            model_name="gemini-3.5-flash",
            system_instruction=system_instruction,
            generation_config={"response_mime_type": "application/json", "temperature": 0.0}
        )
        response = model.generate_content(f"Extract structured data from this OCR text:\n\n{ocr_text}")
        json_string = response.text.strip()
        parsed_data = json.loads(json_string)
        return InvoiceStructuredOutput(**parsed_data) 
    except Exception as e:
        print(f"❌ Error processing OCR with SLM: {e}")
        return InvoiceStructuredOutput(vendor="UNKNOWN", date="UNKNOWN", total_amount=0.0, currency="VND")
