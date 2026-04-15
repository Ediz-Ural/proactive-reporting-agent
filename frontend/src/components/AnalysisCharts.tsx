import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer,
} from 'recharts';

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
