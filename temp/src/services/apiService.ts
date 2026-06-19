const API_BASE_URL = 'http://localhost:8000/api';

export const apiService = {
  /**
   * Upload an invoice image to the backend for processing
   */
  async uploadInvoice(file: File): Promise<{
    predicted_value: number | null;
    confidence: number;
    candidates: any[];
    status: string;
    structured_data?: any;
  }> {
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
   * Submit feedback to the backend for XGBoost retraining
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
