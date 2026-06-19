import React, { useState, useEffect } from 'react';
import { TopBar, BottomBar } from './components/Navigation';
import Capture from './pages/Capture';
import Edit from './pages/Edit';
import PieDashboard from './pages/PieDashboard';
import BarDashboard from './pages/BarDashboard';
import History from './pages/History';
import type { Bill, UserSettings } from './types/bill_data';
import { billService } from './services/billService';

type Page = 'capture' | 'pie' | 'bar' | 'history';

const App: React.FC = () => {
  const [currentPage, setCurrentPage] = useState<Page>('capture');
  const [isEditing, setIsEditing] = useState(false);
  const [pendingBill, setPendingBill] = useState<Partial<Bill> | null>(null);
  const [candidates, setCandidates] = useState<any[]>([]);
  const [bills, setBills] = useState<Bill[]>([]);
  const [settings, setSettings] = useState<UserSettings>({ region: 'VN', base_currency: 'VND' });
  const [loading, setLoading] = useState(false);

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
      // Point 3: Fallback to mock data for UI testing if the database is empty
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

  const handleImageCaptured = async (file: File) => {
    setLoading(true);
    console.log('Uploading image:', file.name);
    
    try {
      const response = await fetch('/api/process-receipt', {
        method: 'POST',
        body: file,
      });

      if (!response.ok) {
        throw new Error(`Failed to process receipt: ${response.statusText}`);
      }

      const result = await response.json();
      console.log('Process result:', result);
      
      setCandidates(result.candidates || []);

      const resultBill: Partial<Bill> = {
        bill_purpose: 'Scanned Bill',
        bill_date: new Date().toISOString().split('T')[0],
        original_value: result.predicted_value || 0,
        original_currency: result.currency || settings.base_currency,
      };
      
      setPendingBill(resultBill);
      setIsEditing(true);
    } catch (error) {
      console.error('Error uploading image:', error);
      alert('Failed to process the receipt. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmBill = async (finalBill: Bill) => {
    try {
      if (candidates && candidates.length > 0) {
        await fetch('/api/feedback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            candidates,
            correct_value: finalBill.original_value
          })
        }).catch(err => console.error("Feedback API error:", err));
      }

      await billService.saveBill(finalBill);
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
        <TopBar 
          region={settings.region} 
          onRegionChange={handleRegionChange} 
        />
        
        <main className="flex-1 overflow-y-auto no-scrollbar relative">
          {renderPage()}
        </main>

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
          />
        )}

        <BottomBar 
          currentPage={currentPage} 
          onPageChange={setCurrentPage} 
        />
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
