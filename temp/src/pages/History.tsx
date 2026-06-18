import React from 'react';
import type { Bill } from '../types/bill_data';
import { Calendar, Tag, CreditCard, RefreshCw, Clock } from 'lucide-react';

interface HistoryProps {
  bills: Bill[];
  baseCurrency: string;
}

const History: React.FC<HistoryProps> = ({ bills, baseCurrency }) => {
  const sortedBills = [...bills].sort((a, b) => 
    new Date(b.bill_date).getTime() - new Date(a.bill_date).getTime() || b.timestamp_created - a.timestamp_created
  );

  return (
    <div className="p-6 space-y-8 min-h-[calc(100vh-144px)] pb-24">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-slate-800 tracking-tight">History</h2>
        <span className="text-sm font-semibold text-slate-600 bg-slate-100 px-4 py-1.5 rounded-full shadow-sm">
          {bills.length} Bills
        </span>
      </div>

      <div className="space-y-5">
        {sortedBills.map((bill, index) => (
          <div key={bill.id || index} className="bg-white border border-slate-100/60 p-5 rounded-[24px] shadow-sm hover:shadow-md transition-shadow duration-300 space-y-5">
            <div className="flex justify-between items-start">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 bg-gradient-to-br from-slate-50 to-slate-100 rounded-[18px] flex items-center justify-center text-slate-700 shadow-sm border border-slate-50">
                  <Tag size={20} strokeWidth={2} />
                </div>
                <div>
                  <p className="font-bold text-lg text-slate-800">{bill.bill_purpose}</p>
                  <p className="text-xs text-slate-500 font-medium flex items-center gap-1.5 mt-0.5">
                    <Calendar size={12} strokeWidth={2} />
                    {bill.bill_date}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className="font-black text-xl text-slate-800">{bill.total_bill_value.toLocaleString()}</p>
                <p className="text-[10px] text-slate-400 uppercase font-bold tracking-wider">{baseCurrency}</p>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-50 flex items-center justify-between text-xs font-medium text-slate-500">
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-1.5 bg-slate-50 px-2.5 py-1 rounded-lg">
                  <CreditCard size={14} />
                  <span>{bill.original_value} {bill.original_currency}</span>
                </div>
                {bill.converted && (
                  <div className="flex items-center gap-1.5 text-blue-600 bg-blue-50 px-2.5 py-1 rounded-lg">
                    <RefreshCw size={12} />
                    <span>Converted</span>
                  </div>
                )}
              </div>
              <span className="text-slate-300">#{bill.timestamp_created.toString().slice(-6)}</span>
            </div>
          </div>
        ))}

        {bills.length === 0 && (
          <div className="text-center py-24">
            <div className="w-24 h-24 bg-gradient-to-br from-slate-50 to-slate-100 rounded-full flex items-center justify-center mx-auto mb-5 text-slate-300 shadow-sm border border-slate-50">
              <Clock size={36} strokeWidth={1.5} />
            </div>
            <p className="text-slate-500 font-medium text-lg">No history yet</p>
            <p className="text-slate-400 text-sm mt-1">Your uploaded bills will appear here.</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default History;
