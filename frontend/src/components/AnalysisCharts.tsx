import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  AreaChart, Area, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

interface DailySalesChartProps {
  data: Array<{ order_date: string; total_sales: number; total_profit: number }>;
}

export function DailySalesChart({ data }: DailySalesChartProps) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-semibold text-gray-700 mb-4">Gunluk Satis Trendi</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="order_date" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="total_sales" stroke="#3b82f6" name="Satis" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="total_profit" stroke="#10b981" name="Kar" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

interface CategoryChartProps {
  data: Array<{ category?: string; sub_category?: string; total_sales: number; profit_margin_pct: number }>;
}

export function CategoryChart({ data }: CategoryChartProps) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-semibold text-gray-700 mb-4">Kategori Performansi</h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} layout="vertical" margin={{ left: 80 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis type="number" tick={{ fontSize: 11 }} />
          <YAxis dataKey="sub_category" type="category" tick={{ fontSize: 11 }} width={75} />
          <Tooltip />
          <Bar dataKey="total_sales" name="Satis" radius={[0, 4, 4, 0]}>
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.profit_margin_pct >= 0 ? '#10b981' : '#ef4444'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

interface RFMChartProps {
  data: Array<{ segment_label: string; count: number }>;
}

const RFM_COLORS: Record<string, string> = {
  Champions: '#10b981',
  'Loyal Customers': '#3b82f6',
  'Loyal': '#3b82f6',
  'Potential Loyalists': '#6366f1',
  'At Risk': '#f59e0b',
  'Lost': '#ef4444',
  'Hibernating': '#6b7280',
};

export function RFMChart({ data }: RFMChartProps) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-semibold text-gray-700 mb-4">RFM Segmentasyonu</h3>
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={100}
            dataKey="count"
            nameKey="segment_label"
            label={({ name, value }: { name?: string; value?: number }) => `${name || ''}: ${value || 0}`}
          >
            {data.map((entry, i) => (
              <Cell key={i} fill={RFM_COLORS[entry.segment_label] || COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

interface ForecastChartProps {
  data: Array<{ ds: string; yhat: number; yhat_lower: number; yhat_upper: number }>;
}

export function ForecastChart({ data }: ForecastChartProps) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-semibold text-gray-700 mb-4">Prophet Tahmin</h3>
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="ds" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Area type="monotone" dataKey="yhat_upper" stroke="none" fill="#3b82f6" fillOpacity={0.1} name="Ust Sinir" />
          <Area type="monotone" dataKey="yhat_lower" stroke="none" fill="#ffffff" fillOpacity={1} name="Alt Sinir" />
          <Line type="monotone" dataKey="yhat" stroke="#3b82f6" strokeWidth={2} name="Tahmin" dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

interface EvaluatorRadarProps {
  data: {
    numerical_accuracy?: number;
    completeness?: number;
    readability?: number;
    actionability?: number;
    hallucination_free?: number;
    overall_score?: number;
  };
}

export function EvaluatorRadar({ data }: EvaluatorRadarProps) {
  const radarData = [
    { metric: 'Dogruluk', value: data.numerical_accuracy || 0 },
    { metric: 'Tamlık', value: data.completeness || 0 },
    { metric: 'Okunabilirlik', value: data.readability || 0 },
    { metric: 'Eyleme Donukluk', value: data.actionability || 0 },
    { metric: 'Halucinasyon', value: data.hallucination_free || 0 },
  ];

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-semibold text-gray-700 mb-4">
        Evaluator Skorlari
        {data.overall_score !== undefined && (
          <span className="ml-2 text-blue-600">({(data.overall_score * 100).toFixed(0)}%)</span>
        )}
      </h3>
      <ResponsiveContainer width="100%" height={300}>
        <RadarChart data={radarData}>
          <PolarGrid stroke="#e5e7eb" />
          <PolarAngleAxis dataKey="metric" tick={{ fontSize: 11 }} />
          <PolarRadiusAxis domain={[0, 1]} tick={{ fontSize: 10 }} />
          <Radar name="Skor" dataKey="value" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.3} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

interface AnomalyChartProps {
  data: Array<{ date: string; value: number; method: string; column: string }>;
}

const METHOD_COLORS: Record<string, string> = {
  zscore: '#ef4444',
  iqr: '#f59e0b',
  isolation_forest: '#8b5cf6',
};

export function AnomalyChart({ data }: AnomalyChartProps) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-semibold text-gray-700 mb-4">Anomaliler</h3>
      <ResponsiveContainer width="100%" height={300}>
        <ScatterChart>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} />
          <YAxis dataKey="value" tick={{ fontSize: 11 }} />
          <Tooltip />
          <Legend />
          {['zscore', 'iqr', 'isolation_forest'].map((method) => {
            const filtered = data.filter((d) => d.method === method);
            if (filtered.length === 0) return null;
            return (
              <Scatter
                key={method}
                name={method}
                data={filtered}
                fill={METHOD_COLORS[method] || '#6b7280'}
              />
            );
          })}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
