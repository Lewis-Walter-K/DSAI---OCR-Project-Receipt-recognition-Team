import React, { useState, useEffect } from 'react';
import { TopBar, BottomBar } from './components/Navigation';
import Capture from './pages/Capture';
import Edit from './pages/Edit';
import PieDashboard from './pages/PieDashboard';
import BarDashboard from './pages/BarDashboard';
import History from './pages/History';
import type { Bill, UserSettings } from './types/bill_data';
import { billService } from './services/billService';
import { apiService } from './services/apiService';
import type { UploadResponse } from './services/apiService';

type Page = 'capture' | 'pie' | 'bar' | 'history';

const App: React.FC = () => {
  const [currentPage, setCurrentPage] = useState<Page>('capture');
  const [isEditing, setIsEditing] = useState(false);
  const [pendingBill, setPendingBill] = useState<Partial<Bill> | null>(null);
  const [candidates, setCandidates] = useState<any[]>([]);
  const [bills, setBills] = useState<Bill[]>([]);
  const [settings, setSettings] = useState<UserSettings>({ region: 'VN', base_currency: 'VND' });
  const [loading, setLoading] = useState(false);
  // Track the raw captured file so Edit page can re-call LLM if needed
  const [capturedFile, setCapturedFile] = useState<File | null>(null);
  // URL of the processed CAMSCANNER_RESULT.jpg from backend
  const [processedImageUrl, setProcessedImageUrl] = useState<string | null>(null);
  // Raw OCR text extracted by backend (for LLM fallback)
  const [ocrText, setOcrText] = useState<string | null>(null);
  // "success" | "llm_fallback" | "low_confidence" — drives the banner in Edit page
  const [apiStatus, setApiStatus] = useState<string>('success');

  useEffect(() => {
    const mockBills: Bill[] = [
      {
        bill_purpose: 'Eating',
        bill_date: new Date(Date.now() - 86400000 * 2).toISOString().split('T')[0],
        timestamp_created: Date.now() - 86400000 * 2,
        original_value: 150000,
        original_currency: 'VND',
        total_bill_value: 150000,
        converted: false
      },
      {
        bill_purpose: 'Coffee',
        bill_date: new Date(Date.now() - 86400000 * 1).toISOString().split('T')[0],
        timestamp_created: Date.now() - 86400000 * 1,
        original_value: 5.50,
        original_currency: 'USD',
        total_bill_value: 140000,
        converted: true
      },
      {
        bill_purpose: 'Shopping',
        bill_date: new Date().toISOString().split('T')[0],
        timestamp_created: Date.now(),
        original_value: 1200000,
        original_currency: 'VND',
        total_bill_value: 1200000,
        converted: false
      },
      {
        bill_purpose: 'Groceries',
        bill_date: new Date(Date.now() - 86400000 * 4).toISOString().split('T')[0],
        timestamp_created: Date.now() - 86400000 * 4,
        original_value: 450000,
        original_currency: 'VND',
        total_bill_value: 450000,
        converted: false
      }
    ];

    // Subscribe to settings and bills
    const unsubscribeSettings = billService.getSettings(setSettings);
    const unsubscribeBills = billService.subscribeToBills((fetchedBills) => {
      // Fallback to mock data for UI testing if the database is empty
      if (fetchedBills.length === 0) {
        setBills(mockBills);
      } else {
        setBills(fetchedBills);
      }
    });

    return () => {
      unsubscribeSettings();
      unsubscribeBills();
    };
  }, []);

  /** Helper: map an UploadResponse to a Partial<Bill> */
  const mapResponseToBill = (response: UploadResponse): Partial<Bill> => {
    const bill: Partial<Bill> = {
      bill_purpose: 'Shopping',
      bill_date: new Date().toISOString().split('T')[0],
      original_value: response.predicted_value || 0,
      original_currency: response.currency || settings.base_currency,
    };
    if (response.structured_data) {
      if (response.structured_data.bill_purpose) bill.bill_purpose = response.structured_data.bill_purpose;
      if (response.structured_data.bill_date) bill.bill_date = response.structured_data.bill_date;
      if (response.structured_data.currency) bill.original_currency = response.structured_data.currency;
      if (response.structured_data.total_amount) bill.original_value = response.structured_data.total_amount;
    }
    return bill;
  };

  const handleImageCaptured = async (file: File) => {
    setLoading(true);
    setCapturedFile(file); // Store for potential LLM re-call in Edit page
    console.log('Uploading image to backend:', file.name);

    try {
      const response = await apiService.uploadInvoice(file);
      console.log('Backend response:', response);

      setCandidates(response.candidates || []);
      setApiStatus(response.status || 'success');
      setProcessedImageUrl(response.processed_image_url || null);
      setOcrText(response.ocr_text || null);
      setPendingBill(mapResponseToBill(response));
      setIsEditing(true);
    } catch (error) {
      console.error('Error processing image:', error);
      alert('Failed to process image. Please check the backend server.');
    } finally {
      setLoading(false);
    }
  };

  /** Called from Edit page when user manually triggers LLM re-parse */
  const handleLlmFallback = async (): Promise<void> => {
    if (!ocrText) {
      alert("No OCR text available to run AI on.");
      return;
    }
    const response = await apiService.callLlmFallback(ocrText);
    setCandidates(response.candidates || []);
    setApiStatus(response.status || 'llm_fallback');
    setPendingBill(prev => ({ ...prev, ...mapResponseToBill(response) }));
  };

  const handleConfirmBill = async (finalBill: Bill) => {
    try {
      // 1. Save locally to Firebase/Service
      await billService.saveBill(finalBill);
      
      // 2. Send feedback to AI backend for XGBoost retraining
      apiService.submitFeedback(finalBill.original_value, candidates).catch(err => {
        console.error('Failed to submit feedback to AI:', err);
      });

      setIsEditing(false);
      setPendingBill(null);
      setCandidates([]);
      setCurrentPage('pie');
    } catch (error) {
      console.error('Error saving bill:', error);
      alert('Failed to save bill');
    }
  };

  const handleRegionChange = (region: string, base_currency: string) => {
    const newSettings = { region, base_currency };
    setSettings(newSettings);
    billService.updateSettings(newSettings);
  };

  const renderPage = () => {
    switch (currentPage) {
      case 'capture':
        return <Capture onImageCaptured={handleImageCaptured} />;
      case 'pie':
        return <PieDashboard bills={bills} baseCurrency={settings.base_currency} />;
      case 'bar':
        return <BarDashboard bills={bills} baseCurrency={settings.base_currency} />;
      case 'history':
        return <History bills={bills} baseCurrency={settings.base_currency} />;
      default:
        return <Capture onImageCaptured={handleImageCaptured} />;
    }
  };

  return (
    <div className="h-[100dvh] w-full bg-gray-50 flex justify-center overflow-hidden">
      <div className="w-full max-w-[480px] bg-white h-full relative shadow-2xl flex flex-col overflow-hidden">
        {!isEditing && (
          <TopBar 
            region={settings.region} 
            onRegionChange={handleRegionChange} 
          />
        )}
        
        {!isEditing && (
          <main className="flex-1 overflow-y-auto no-scrollbar relative">
            {renderPage()}
          </main>
        )}

        {loading && (
          <div className="absolute inset-0 bg-white/80 z-[70] flex flex-col items-center justify-center gap-4">
            <div className="w-12 h-12 border-4 border-black border-t-transparent rounded-full animate-spin"></div>
            <p className="font-bold animate-pulse">Scraping Bill...</p>
          </div>
        )}

        {isEditing && pendingBill && (
          <Edit 
            initialData={pendingBill} 
            userSettings={settings}
            onConfirm={handleConfirmBill}
            onCancel={() => setIsEditing(false)}
            apiStatus={apiStatus}
            onLlmFallback={handleLlmFallback}
            imageFile={capturedFile}
            processedImageUrl={processedImageUrl}
          />
        )}

        {!isEditing && (
          <BottomBar 
            currentPage={currentPage} 
            onPageChange={setCurrentPage} 
          />
        )}
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        .animate-spin { animation: spin 1s linear infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .animate-pulse { animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
        @keyframes slideUp { from { transform: translateY(100%); } to { transform: translateY(0); } }
        .animate-slide-up { animation: slideUp 0.3s ease-out; }
      `}</style>
    </div>
  );
};

export default App;
