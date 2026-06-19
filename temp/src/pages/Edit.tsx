import React, { useState, useEffect, useMemo } from 'react';
import { Check, AlertCircle, ChevronLeft, ReceiptText, Sparkles, Loader2 } from 'lucide-react';
import type { Bill, UserSettings } from '../types/bill_data';

interface EditProps {
  initialData: Partial<Bill>;
  userSettings: UserSettings;
  onConfirm: (finalData: Bill) => void;
  onCancel: () => void;
  /** "success" | "low_confidence" | "llm_fallback" from backend */
  apiStatus: string;
  /** Trigger LLM re-parse from parent */
  onLlmFallback: () => Promise<void>;
  /** The raw captured image file (fallback preview) */
  imageFile: File | null;
  /** URL to backend-served CAMSCANNER_RESULT.jpg (preferred preview) */
  processedImageUrl: string | null;
}

const EXCHANGE_RATES: Record<string, number> = {
  USD: 25450,
  EUR: 27500,
  CHF: 28200,
  GBP: 32500,
  AUD: 17000,
  CAD: 18500,
  SGD: 19000,
  JPY: 165,
  KRW: 18.5,
  CNY: 3500,
  INR: 300,
  VND: 1
};

const Edit: React.FC<EditProps> = ({ initialData, userSettings, onConfirm, onCancel, apiStatus, onLlmFallback, imageFile, processedImageUrl }) => {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLlmLoading, setIsLlmLoading] = useState(false);

  // Create a fallback object URL from the raw captured file
  const rawImageUrl = useMemo(() => {
    if (!imageFile) return null;
    return URL.createObjectURL(imageFile);
  }, [imageFile]);

  // Revoke fallback URL when component unmounts
  useEffect(() => {
    return () => { if (rawImageUrl) URL.revokeObjectURL(rawImageUrl); };
  }, [rawImageUrl]);

  // Prefer processed (CamScanner) image, fall back to raw upload
  const previewUrl = processedImageUrl || rawImageUrl;

  const [formData, setFormData] = useState<Partial<Bill>>({
    bill_purpose: initialData.bill_purpose || '',
    bill_date: initialData.bill_date || new Date().toISOString().split('T')[0],
    original_value: initialData.original_value || 0,
    original_currency: initialData.original_currency || 'USD',
    total_bill_value: initialData.total_bill_value || 0,
    converted: false,
    ...initialData
  });

  const [conversionMessage, setConversionMessage] = useState<string | null>(null);

  useEffect(() => {
    if (formData.original_currency !== userSettings.base_currency) {
      const fromRate = EXCHANGE_RATES[formData.original_currency || 'USD'] || 1;
      const toRate = EXCHANGE_RATES[userSettings.base_currency || 'VND'] || 1;
      const rate = fromRate / toRate;
      const convertedValue = (formData.original_value || 0) * rate;
      
      setFormData(prev => ({ ...prev, total_bill_value: convertedValue, converted: true }));
      setConversionMessage(`Auto-converted ${formData.original_value} ${formData.original_currency} to ${convertedValue.toLocaleString()} ${userSettings.base_currency}`);
    } else {
      setFormData(prev => ({ ...prev, total_bill_value: prev.original_value, converted: false }));
      setConversionMessage(null);
    }
  }, [formData.original_currency, formData.original_value, userSettings.base_currency]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      await onConfirm({ ...formData, timestamp_created: Date.now() } as Bill);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAskLlm = async () => {
    setIsLlmLoading(true);
    try {
      await onLlmFallback();
    } catch (err) {
      console.error('LLM fallback failed:', err);
      alert('AI re-parse failed. Please fill in manually.');
    } finally {
      setIsLlmLoading(false);
    }
  };

  return (
    <div className="flex-1 w-full bg-slate-50 flex flex-col animate-slide-up">
      {/* Header */}
      <div className="bg-white px-6 pt-8 pb-4 rounded-b-[32px] shadow-sm relative z-10 flex items-center justify-between">
        <button onClick={onCancel} className="w-10 h-10 bg-slate-50 rounded-full flex items-center justify-center text-slate-600 hover:bg-slate-100 transition-colors">
          <ChevronLeft size={24} />
        </button>
        <h2 className="text-xl font-bold text-slate-800">Verify Details</h2>
        <div className="w-10"></div> {/* Spacer for centering */}
      </div>

      {/* Human Validation Banner — shown when XGBoost confidence is low */}
      {(apiStatus === 'low_confidence' || apiStatus === 'llm_fallback') && (
        <div style={{
          margin: '12px 16px 0',
          padding: '14px 16px',
          background: '#fffbeb',
          border: '1px solid #fcd34d',
          borderRadius: '16px',
          display: 'flex',
          gap: '12px',
          alignItems: 'flex-start'
        }}>
          <AlertCircle size={20} style={{ color: '#d97706', flexShrink: 0, marginTop: 2 }} />
          <div style={{ flex: 1 }}>
            <p style={{ fontWeight: 700, fontSize: 13, color: '#92400e', marginBottom: 4 }}>
              {apiStatus === 'llm_fallback'
                ? '⚠️ AI Model was unsure — values filled by LLM. Please verify!'
                : '⚠️ Low confidence result — please verify the values below.'}
            </p>
            <p style={{ fontSize: 12, color: '#b45309', marginBottom: 10, lineHeight: 1.5 }}>
              The XGBoost model could not read this bill with high confidence.
              You can ask Gemini AI to re-parse the image, or fill in manually.
            </p>
            <button
              type="button"
              onClick={handleAskLlm}
              disabled={isLlmLoading}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                background: isLlmLoading ? '#d1d5db' : '#7c3aed',
                color: '#fff',
                border: 'none',
                borderRadius: '999px',
                padding: '8px 16px',
                fontSize: 13,
                fontWeight: 700,
                cursor: isLlmLoading ? 'not-allowed' : 'pointer',
              }}
            >
              {isLlmLoading
                ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />
                : <Sparkles size={14} />}
              {isLlmLoading ? 'Asking Gemini AI...' : 'Ask AI (Gemini)'}
            </button>
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto no-scrollbar px-6 pt-6 pb-6">

        {/* Receipt Image Preview (CamScanner processed image preferred) */}
        {previewUrl && (
          <div style={{
            marginBottom: 16,
            borderRadius: 20,
            overflow: 'hidden',
            border: '1px solid #e2e8f0',
            boxShadow: '0 4px 16px rgba(0,0,0,0.06)',
            background: '#f8fafc',
            position: 'relative',
          }}>
            <img
              src={previewUrl}
              alt="Processed receipt"
              style={{
                width: '100%',
                maxHeight: 280,
                objectFit: 'contain',
                display: 'block',
              }}
            />
            <div style={{
              position: 'absolute',
              bottom: 0,
              left: 0,
              right: 0,
              padding: '8px 14px',
              background: 'linear-gradient(to top, rgba(0,0,0,0.45), transparent)',
              color: '#fff',
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: '0.05em',
            }}>
              RECEIPT PREVIEW — verify values below
            </div>
          </div>
        )}

        {/* Data Card */}
        <div className="bg-white rounded-[24px] p-6 shadow-sm border border-slate-100 mb-6">

          {/* Header: Scanned amount + always-visible Re-parse button */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20, paddingBottom: 20, borderBottom: '1px solid #f1f5f9' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ width: 48, height: 48, background: '#eff6ff', color: '#2563eb', borderRadius: 16, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <ReceiptText size={24} />
              </div>
              <div>
                <p style={{ fontSize: 11, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 2 }}>Scanned Amount</p>
                <p style={{ fontSize: 22, fontWeight: 900, color: '#1e293b' }}>
                  {formData.original_value?.toLocaleString()}{' '}
                  <span style={{ fontSize: 13, fontWeight: 700, color: '#94a3b8' }}>{formData.original_currency}</span>
                </p>
              </div>
            </div>

            {/* Always-visible Re-parse button */}
            <button
              type="button"
              onClick={handleAskLlm}
              disabled={isLlmLoading}
              title="Ask Gemini AI to re-read this receipt"
              style={{
                display: 'inline-flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 3,
                background: isLlmLoading ? '#f3f4f6' : '#faf5ff',
                color: isLlmLoading ? '#9ca3af' : '#7c3aed',
                border: `1.5px solid ${isLlmLoading ? '#e5e7eb' : '#ddd6fe'}`,
                borderRadius: 14,
                padding: '8px 10px',
                fontSize: 10,
                fontWeight: 700,
                cursor: isLlmLoading ? 'not-allowed' : 'pointer',
                minWidth: 62,
              }}
            >
              {isLlmLoading
                ? <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }} />
                : <Sparkles size={18} />}
              {isLlmLoading ? 'Asking...' : 'Ask AI'}
            </button>
          </div>

          {/* Low-confidence warning strip (only shown when AI was unsure) */}
          {(apiStatus === 'low_confidence' || apiStatus === 'llm_fallback') && (
            <div style={{ background: '#fffbeb', border: '1px solid #fcd34d', borderRadius: 12, padding: '10px 14px', marginBottom: 16, display: 'flex', gap: 8, alignItems: 'flex-start' }}>
              <AlertCircle size={16} style={{ color: '#d97706', flexShrink: 0, marginTop: 1 }} />
              <p style={{ fontSize: 12, fontWeight: 600, color: '#92400e', lineHeight: 1.5 }}>
                {apiStatus === 'llm_fallback'
                  ? '⚠️ Filled by Gemini AI — values may not be exact. Please verify!'
                  : '⚠️ Low confidence — AI was unsure. Please verify the values below.'}
              </p>
            </div>
          )}

          <form id="bill-form" onSubmit={handleSubmit} className="space-y-5">
            {/* Input Group: Purpose */}
            <div className="bg-slate-50 rounded-[20px] p-4 border border-transparent focus-within:border-blue-200 focus-within:bg-blue-50/30 transition-colors">
              <label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Purpose Category</label>
              <input 
                type="text" 
                value={formData.bill_purpose}
                onChange={e => setFormData({...formData, bill_purpose: e.target.value})}
                className="w-full text-lg font-bold text-slate-800 bg-transparent outline-none placeholder:text-slate-300"
                placeholder="e.g. Coffee, Transport"
                required
              />
            </div>

            {/* Input Group: Date */}
            <div className="bg-slate-50 rounded-[20px] p-4 border border-transparent focus-within:border-blue-200 focus-within:bg-blue-50/30 transition-colors">
              <label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Date</label>
              <input 
                type="date" 
                value={formData.bill_date}
                onChange={e => setFormData({...formData, bill_date: e.target.value})}
                className="w-full text-lg font-bold text-slate-800 bg-transparent outline-none"
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              {/* Input Group: Value */}
              <div className="bg-slate-50 rounded-[20px] p-4 border border-transparent focus-within:border-blue-200 focus-within:bg-blue-50/30 transition-colors">
                <label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Original Value</label>
                <input 
                  type="number" 
                  step="0.01"
                  value={formData.original_value}
                  onChange={e => setFormData({...formData, original_value: parseFloat(e.target.value)})}
                  className="w-full text-lg font-bold text-slate-800 bg-transparent outline-none"
                  required
                />
              </div>

              {/* Input Group: Currency */}
              <div className="bg-slate-50 rounded-[20px] p-4 border border-transparent focus-within:border-blue-200 focus-within:bg-blue-50/30 transition-colors relative">
                <label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Currency</label>
                <select 
                  value={formData.original_currency}
                  onChange={e => setFormData({...formData, original_currency: e.target.value})}
                  className="w-full text-lg font-bold text-slate-800 bg-transparent outline-none appearance-none"
                >
                  <option value="USD">USD ($)</option>
                  <option value="VND">VND (₫)</option>
                  <option value="EUR">EUR (€)</option>
                  <option value="CHF">CHF (₣)</option>
                  <option value="GBP">GBP (£)</option>
                  <option value="JPY">JPY (¥)</option>
                  <option value="KRW">KRW (₩)</option>
                  <option value="CNY">CNY (¥)</option>
                  <option value="SGD">SGD ($)</option>
                  <option value="AUD">AUD ($)</option>
                  <option value="CAD">CAD ($)</option>
                  <option value="INR">INR (₹)</option>
                </select>
                <div className="absolute right-4 top-1/2 mt-1 pointer-events-none text-slate-400">
                  <svg width="12" height="8" viewBox="0 0 12 8" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M1 1.5L6 6.5L11 1.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </div>
              </div>
            </div>
          </form>
        </div>

        {conversionMessage && (
          <div className="bg-blue-50 border border-blue-100/50 p-4 rounded-[20px] flex items-start gap-3 shadow-sm mb-6">
            <AlertCircle size={20} className="text-blue-500 shrink-0 mt-0.5" />
            <p className="text-sm font-medium text-blue-700 leading-relaxed">{conversionMessage}</p>
          </div>
        )}
      </div>

      {/* Static Bottom Action Bar (Flexbox instead of absolute) */}
      <div className="w-full p-6 bg-white border-t border-slate-100 shadow-[0_-10px_30px_rgb(0,0,0,0.03)] shrink-0 z-20">
        <div className="flex items-center justify-between mb-4 px-2">
          <span className="text-sm font-bold text-slate-400 uppercase tracking-wider">Final Total</span>
          <span className="text-3xl font-black text-blue-600">{formData.total_bill_value?.toLocaleString()} <span className="text-sm font-bold text-slate-400">{userSettings.base_currency}</span></span>
        </div>
        <button 
          color='#b71313'
          form="bill-form"
          type="submit"
          className="w-full bg-blue-600 text-white py-4 rounded-full font-bold shadow-lg active:scale-95 transition-all flex items-center justify-center gap-2 hover:bg-blue-700 mt-4"
        >
          {isSubmitting ? (
            <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
          ) : (
            <Check size={22} strokeWidth={3} />
          )}
          {isSubmitting ? 'Saving & Learning...' : 'Confirm & Save Bill'}
        </button>
      </div>
    </div>
  );
};

export default Edit;
