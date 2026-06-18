import React, { useMemo, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell } from 'recharts';
import type { Bill } from '../types/bill_data';

interface BarDashboardProps {
  bills: Bill[];
  baseCurrency: string;
}

const BarDashboard: React.FC<BarDashboardProps> = ({ bills, baseCurrency }) => {
  const [days, setDays] = useState<7 | 30>(7);

  const data = useMemo(() => {
    const daily: Record<string, number> = {};
    const now = new Date();
    
    // Initialize last N days
    for (let i = 0; i < days; i++) {
      const d = new Date();
      d.setDate(now.getDate() - i);
      const dateStr = d.toISOString().split('T')[0];
      daily[dateStr] = 0;
    }

    bills.forEach(bill => {
      if (daily[bill.bill_date] !== undefined) {
        daily[bill.bill_date] += bill.total_bill_value;
      }
    });

    return Object.entries(daily)
      .map(([date, value]) => ({ 
        date: date.split('-').slice(1).join('/'), 
        value,
        fullDate: date 
      }))
      .reverse();
  }, [bills, days]);

  const mostDay = useMemo(() => {
    if (data.length === 0) return null;
    return data.reduce((prev, current) => (prev.value > current.value) ? prev : current);
  }, [data]);

  return (
    <div className="p-6 space-y-8 min-h-[calc(100vh-144px)] pb-24">
      <div className="flex justify-between items-end bg-white p-6 rounded-[24px] shadow-sm border border-slate-100/60">
        <div>
          <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Busiest Day</p>
          <p className="text-xl font-bold text-slate-800">{mostDay && mostDay.value > 0 ? mostDay.date : 'N/A'}</p>
        </div>
        <div className="flex bg-slate-50 p-1.5 rounded-xl border border-slate-100/60">
          <button 
            onClick={() => setDays(7)}
            className={`px-4 py-1.5 rounded-lg text-sm font-bold transition-all duration-300 ${days === 7 ? 'bg-white shadow-sm text-blue-600' : 'text-slate-400 hover:text-slate-600'}`}
          >
            7D
          </button>
          <button 
            onClick={() => setDays(30)}
            className={`px-4 py-1.5 rounded-lg text-sm font-bold transition-all duration-300 ${days === 30 ? 'bg-white shadow-sm text-blue-600' : 'text-slate-400 hover:text-slate-600'}`}
          >
            30D
          </button>
        </div>
      </div>

      <div className="h-[300px] w-full bg-white p-4 rounded-[32px] shadow-sm border border-slate-100/60 flex items-center justify-center overflow-x-auto no-scrollbar">
        <BarChart data={data} width={350} height={260} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
          <XAxis 
            dataKey="date" 
            axisLine={false} 
            tickLine={false} 
            tick={{ fontSize: 10, fill: '#94a3b8' }}
            interval={days === 30 ? 4 : 0}
            dy={10}
          />
          <YAxis hide />
          <Tooltip 
            cursor={{ fill: '#f8fafc', radius: 8 }}
            content={({ active, payload }) => {
              if (active && payload && payload.length) {
                return (
                  <div className="bg-white text-slate-800 px-4 py-2 rounded-xl text-sm font-bold shadow-lg border border-slate-100">
                    {payload[0].value?.toLocaleString()} {baseCurrency}
                  </div>
                );
              }
              return null;
            }}
          />
          <Bar dataKey="value" radius={[6, 6, 6, 6]}>
            {data.map((entry, index) => (
              <Cell 
                key={`cell-${index}`} 
                fill={entry.fullDate === mostDay?.fullDate && entry.value > 0 ? '#3B82F6' : '#e2e8f0'} 
              />
            ))}
          </Bar>
        </BarChart>
      </div>

      <div className="space-y-4">
        <h3 className="font-bold text-lg text-slate-800 tracking-tight px-2">Daily Activity</h3>
        <div className="grid gap-3">
          {data.slice().reverse().filter(d => d.value > 0).map((item) => (
            <div key={item.fullDate} className="flex items-center justify-between p-4 bg-white border border-slate-100/60 rounded-[20px] shadow-sm hover:shadow-md transition-shadow">
              <span className="font-semibold text-slate-600">{item.fullDate}</span>
              <span className="font-bold text-slate-800">{item.value.toLocaleString()} <span className="text-xs text-slate-400">{baseCurrency}</span></span>
            </div>
          ))}
          {data.every(d => d.value === 0) && (
            <div className="text-center py-12 text-slate-400 font-medium">
              No data for this period
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default BarDashboard;
