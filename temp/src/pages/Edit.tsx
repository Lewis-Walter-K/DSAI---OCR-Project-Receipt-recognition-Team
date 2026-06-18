import React, { useState, useEffect } from 'react';
import { Check, AlertCircle, ChevronLeft, ReceiptText } from 'lucide-react';
import type { Bill, UserSettings } from '../types/bill_data';

interface EditProps {
  initialData: Partial<Bill>;
  userSettings: UserSettings;
  onConfirm: (finalData: Bill) => void;
  onCancel: () => void;
}

const Edit: React.FC<EditProps> = ({ initialData, userSettings, onConfirm, onCancel }) => {
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
      const rate = formData.original_currency === 'USD' && userSettings.base_currency === 'VND' ? 25450 : 1;
      const convertedValue = (formData.original_value || 0) * rate;
      
      setFormData(prev => ({ ...prev, total_bill_value: convertedValue, converted: true }));
      setConversionMessage(`Auto-converted ${formData.original_value} ${formData.original_currency} to ${convertedValue.toLocaleString()} ${userSettings.base_currency}`);
    } else {
      setFormData(prev => ({ ...prev, total_bill_value: prev.original_value, converted: false }));
      setConversionMessage(null);
    }
  }, [formData.original_currency, formData.original_value, userSettings.base_currency]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onConfirm({ ...formData, timestamp_created: Date.now() } as Bill);
  };

  return (
    <div className="absolute inset-0 bg-slate-50 z-[60] flex flex-col animate-slide-up">
      {/* Header */}
      <div className="bg-white px-6 pt-8 pb-4 rounded-b-[32px] shadow-sm relative z-10 flex items-center justify-between">
        <button onClick={onCancel} className="w-10 h-10 bg-slate-50 rounded-full flex items-center justify-center text-slate-600 hover:bg-slate-100 transition-colors">
          <ChevronLeft size={24} />
        </button>
        <h2 className="text-xl font-bold text-slate-800">Verify Details</h2>
        <div className="w-10"></div> {/* Spacer for centering */}
      </div>

      <div className="flex-1 overflow-y-auto no-scrollbar px-6 pt-6 pb-32">
        {/* Modern Receipt Card */}
        <div className="bg-white rounded-[24px] p-6 shadow-sm border border-slate-100 mb-6">
          <div className="flex items-center gap-3 mb-6 pb-6 border-b border-slate-100">
            <div className="w-12 h-12 bg-blue-50 text-blue-600 rounded-2xl flex items-center justify-center">
              <ReceiptText size={24} />
            </div>
            <div>
              <p className="text-sm font-bold text-slate-400 uppercase tracking-wider">Scanned Amount</p>
              <p className="text-2xl font-black text-slate-800">{formData.original_value?.toLocaleString()} <span className="text-sm font-bold text-slate-400">{formData.original_currency}</span></p>
            </div>
          </div>

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

      {/* Sticky Bottom Action Bar */}
      <div className="absolute bottom-0 left-0 right-0 p-6 bg-white border-t border-slate-100 shadow-[0_-10px_30px_rgb(0,0,0,0.03)] z-20">
        <div className="flex items-center justify-between mb-4 px-2">
          <span className="text-sm font-bold text-slate-400 uppercase tracking-wider">Final Total</span>
          <span className="text-3xl font-black text-blue-600">{formData.total_bill_value?.toLocaleString()} <span className="text-sm font-bold text-slate-400">{userSettings.base_currency}</span></span>
        </div>
        <button 
          form="bill-form"
          type="submit"
          className="w-full bg-blue-600 text-white py-4 rounded-full font-bold shadow-[0_8px_20px_rgb(37,99,235,0.25)] active:scale-[0.98] transition-all flex items-center justify-center gap-2 hover:bg-blue-700"
        >
          <Check size={22} strokeWidth={3} />
          Confirm & Save Bill
        </button>
      </div>
    </div>
  );
};

export default Edit;
