import { CheckCircle, Circle, Loader2 } from 'lucide-react';

const STEPS = [
  { key: 'data_collector', label: 'Data Collector', desc: 'Veri toplama' },
  { key: 'data_quality', label: 'Data Quality', desc: 'Kalite kontrolu' },
  { key: 'orchestrator', label: 'Orchestrator', desc: 'Analiz planlama' },
  { key: 'analyst', label: 'Analyst', desc: 'Analiz calistirma' },
  { key: 'rag', label: 'RAG', desc: 'Gecmis rapor arama' },
  { key: 'writer', label: 'Writer', desc: 'Rapor yazimi' },
  { key: 'evaluator', label: 'Evaluator', desc: 'Kalite degerlendirme' },
  { key: 'delivery', label: 'Delivery', desc: 'Teslim' },
  { key: 'feedback', label: 'Feedback', desc: 'Metrik kaydi' },
];

interface PipelineProgressProps {
  status: 'idle' | 'running' | 'completed' | 'error';
  completedSteps?: string[];
  currentStep?: string;
}

export default function PipelineProgress({ status, completedSteps = [], currentStep }: PipelineProgressProps) {
  if (status === 'idle') return null;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-semibold text-gray-700 mb-4">Pipeline Ilerlemesi</h3>
      <div className="space-y-2">
        {STEPS.map(({ key, label, desc }) => {
          const isDone = completedSteps.includes(key) || status === 'completed';
          const isCurrent = key === currentStep && status === 'running';
          return (
            <div key={key} className="flex items-center gap-3">
              {isDone ? (
                <CheckCircle size={18} className="text-green-500 shrink-0" />
              ) : isCurrent ? (
                <Loader2 size={18} className="text-blue-500 animate-spin shrink-0" />
              ) : (
                <Circle size={18} className="text-gray-300 shrink-0" />
              )}
              <div>
                <span className={`text-sm font-medium ${isDone ? 'text-gray-900' : isCurrent ? 'text-blue-600' : 'text-gray-400'}`}>
                  {label}
                </span>
                <span className="text-xs text-gray-400 ml-2">{desc}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
