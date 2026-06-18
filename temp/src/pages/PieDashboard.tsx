import React, { useMemo } from 'react';
import { PieChart, Pie, Cell, Legend, Tooltip } from 'recharts';
import type { Bill } from '../types/bill_data';

interface PieDashboardProps {
  bills: Bill[];
  baseCurrency: string;
}

const COLORS = ['#3B82F6', '#8B5CF6', '#60A5FA', '#93C5FD', '#BFDBFE', '#DBEAFE'];

const PieDashboard: React.FC<PieDashboardProps> = ({ bills, baseCurrency }) => {
  const data = useMemo(() => {
    const categories: Record<string, number> = {};
    bills.forEach(bill => {
      categories[bill.bill_purpose] = (categories[bill.bill_purpose] || 0) + bill.total_bill_value;
    });

    return Object.entries(categories).map(([name, value]) => ({ name, value }));
  }, [bills]);

  const total = useMemo(() => data.reduce((acc, curr) => acc + curr.value, 0), [data]);
  const mostCategory = useMemo(() => {
    if (data.length === 0) return null;
    return data.reduce((prev, current) => (prev.value > current.value) ? prev : current);
  }, [data]);

  return (
    <div className="p-6 space-y-8 min-h-[calc(100vh-144px)] pb-24">
      <div className="flex justify-between items-end bg-white p-6 rounded-[24px] shadow-sm border border-slate-100/60">
        <div>
          <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Most Category</p>
          <p className="text-xl font-bold text-slate-800">{mostCategory ? mostCategory.name : 'N/A'}</p>
        </div>
        <div className="text-right">
          <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Total</p>
          <p className="text-2xl font-black text-blue-600">{total.toLocaleString()} <span className="text-sm">{baseCurrency}</span></p>
        </div>
      </div>

      <div className="h-[320px] w-full bg-white p-4 rounded-[32px] shadow-sm border border-slate-100/60 flex items-center justify-center overflow-hidden">
        <PieChart width={350} height={280}>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={90}
            paddingAngle={6}
            dataKey="value"
            stroke="none"
          >
            {data.map((_, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip 
            formatter={(
              value: number | string | readonly (number | string)[] | undefined,
              name: string | number | undefined,
            ) => {
              const amount = Array.isArray(value)
                ? Number(value[0]) || 0
                : typeof value === 'number'
                ? value
                : value
                ? Number(value)
                : 0;
              return [`${amount.toLocaleString()} ${baseCurrency}`, name ? String(name) : 'Amount'];
            }}
            contentStyle={{ borderRadius: '16px', border: '1px solid #f1f5f9', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
          />
          <Legend verticalAlign="bottom" height={36} iconType="circle" />
        </PieChart>
      </div>

      <div className="space-y-4">
        <h3 className="font-bold text-lg text-slate-800 tracking-tight px-2">Category Breakdown</h3>
        <div className="grid gap-3">
          {data.map((item, index) => (
            <div key={item.name} className="flex items-center justify-between p-4 bg-white border border-slate-100/60 rounded-[20px] shadow-sm hover:shadow-md transition-shadow">
              <div className="flex items-center gap-4">
                <div className="w-4 h-4 rounded-full shadow-inner" style={{ backgroundColor: COLORS[index % COLORS.length] }} />
                <span className="font-semibold text-slate-700">{item.name}</span>
              </div>
              <div className="text-right">
                <p className="font-bold text-slate-800">{item.value.toLocaleString()} <span className="text-xs text-slate-400">{baseCurrency}</span></p>
                <p className="text-[10px] font-bold text-slate-400 mt-0.5">{((item.value / total) * 100).toFixed(1)}%</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default PieDashboard;