const API_BASE_URL = 'http://localhost:8000/api';

export interface UploadResponse {
  predicted_value: number | null;
  confidence: number;
  candidates: any[];
  // "success" | "llm_fallback" | "low_confidence"
  status: string;
  currency?: string;
  /** URL to the post-processed CAMSCANNER_RESULT.jpg served by backend */
  processed_image_url?: string;
  /** Raw OCR text extracted by PaddleOCR on the backend */
  ocr_text?: string;
  structured_data?: {
    bill_purpose?: string;
    bill_date?: string;
    currency?: string;
    total_amount?: number;
  };
}

export const apiService = {
  /**
   * Upload an invoice image to the backend for processing.
   * Returns status "success" when XGBoost is confident,
   * or "llm_fallback" / "low_confidence" when it fails.
   */
  async uploadInvoice(file: File): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE_URL}/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`);
    }

    return response.json();
  },

  /**
   * Call the SLM fallback directly using OCR text.
   * Used as a human-triggered fallback when XGBoost result is unreliable.
   */
  async callLlmFallback(ocrText: string): Promise<UploadResponse> {
    const response = await fetch(`${API_BASE_URL}/llm-parse`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ ocr_text: ocrText }),
    });

    if (!response.ok) {
      throw new Error(`LLM Fallback Error: ${response.statusText}`);
    }

    return response.json();
  },

  /**
   * Submit feedback to the backend for XGBoost retraining.
   */
  async submitFeedback(correctValue: number, candidates: any[]): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/feedback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        correct_value: correctValue,
        candidates: candidates,
      }),
    });

    if (!response.ok) {
      throw new Error(`Feedback Error: ${response.statusText}`);
    }
  }
};
