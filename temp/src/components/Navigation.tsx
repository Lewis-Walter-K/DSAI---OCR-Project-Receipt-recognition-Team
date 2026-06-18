import React, { useState } from 'react';
import { Camera, PieChart, BarChart, Clock, Globe } from 'lucide-react';

interface TopBarProps {
  region: string;
  onRegionChange: (region: string, currency: string) => void;
}

export const TopBar: React.FC<TopBarProps> = ({ region, onRegionChange }) => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const regions = [
    { label: 'VN', currency: 'VND' },
    { label: 'AMER', currency: 'USD' },
    { label: 'EU', currency: 'EUR' },
  ];

  return (
    <div className="w-full h-16 shrink-0 bg-white border-b flex items-center justify-between px-6 z-50 relative">
      <h1 className="text-xl font-bold tracking-tight text-slate-800">WO IST MEIN GELD</h1>
      
      <div className="relative">
        <button 
          onClick={() => setIsMenuOpen(!isMenuOpen)}
          className="flex items-center gap-1.5 bg-slate-100 px-4 py-2 rounded-full text-sm font-semibold text-slate-700 active:bg-slate-200 transition-colors"
        >
          <Globe size={16} />
          {region}
        </button>

        {isMenuOpen && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setIsMenuOpen(false)} />
            <div className="absolute right-0 top-full mt-2 w-40 bg-white rounded-2xl shadow-xl border border-slate-100 overflow-hidden z-50 animate-slide-up origin-top-right">
              <div className="py-2">
                {regions.map((r) => (
                  <button
                    key={r.label}
                    onClick={() => {
                      onRegionChange(r.label, r.currency);
                      setIsMenuOpen(false);
                    }}
                    className={`w-full px-5 py-3 flex items-center justify-between transition-colors ${
                      region === r.label ? 'bg-slate-50 text-black font-bold' : 'text-slate-600 hover:bg-slate-50'
                    }`}
                  >
                    <span>{r.label}</span>
                    <span className="text-xs opacity-60 font-medium">{r.currency}</span>
                  </button>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

interface BottomBarProps {
  currentPage: string;
  onPageChange: (page: any) => void;
}

export const BottomBar: React.FC<BottomBarProps> = ({ currentPage, onPageChange }) => {
  const tabs = [
    { id: 'capture', icon: Camera, label: 'Capture' },
    { id: 'pie', icon: PieChart, label: 'Pie' },
    { id: 'bar', icon: BarChart, label: 'Bar' },
    { id: 'history', icon: Clock, label: 'History' },
  ];

  return (
    <div className="w-full h-20 shrink-0 bg-white/80 backdrop-blur-md border-t border-slate-100 flex items-center justify-around pb-4 z-50">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = currentPage === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => onPageChange(tab.id)}
            className={`flex flex-col items-center gap-1.5 relative transition-all duration-300 ${
              isActive ? 'text-blue-600 scale-110' : 'text-slate-400 hover:text-slate-600'
            }`}
          >
            <Icon size={isActive ? 26 : 24} strokeWidth={isActive ? 2.5 : 2} />
            <span className="text-[10px] font-bold uppercase tracking-wider">{tab.label}</span>
          </button>
        );
      })}
    </div>
  );
};
