import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

interface KPICardProps {
  title: string;
  value: string | number;
  change?: number;
  icon: LucideIcon;
  prefix?: string;
  loading?: boolean;
}

export default function KPICard({ title, value, change, icon: Icon, prefix = '', loading = false }: KPICardProps) {
  const isPositive = change !== undefined && change > 0;
  const isNegative = change !== undefined && change < 0;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-gray-500">{title}</span>
        <div className="p-2 bg-blue-50 rounded-lg">
          <Icon size={18} className="text-blue-600" />
        </div>
      </div>
      {loading ? (
        <div className="h-8 bg-gray-200 rounded animate-pulse" />
      ) : (
        <>
          <div className="text-2xl font-bold text-gray-900">
            {prefix}{typeof value === 'number' ? value.toLocaleString('tr-TR') : value}
          </div>
          {change !== undefined && (
            <div className={`flex items-center gap-1 mt-2 text-sm ${
              isPositive ? 'text-green-600' : isNegative ? 'text-red-600' : 'text-gray-500'
            }`}>
              {isPositive ? <TrendingUp size={14} /> : isNegative ? <TrendingDown size={14} /> : <Minus size={14} />}
              <span>{change > 0 ? '+' : ''}{change.toFixed(1)}%</span>
              <span className="text-gray-400 ml-1">onceki donem</span>
            </div>
          )}
        </>
      )}
    </div>
  );
}
