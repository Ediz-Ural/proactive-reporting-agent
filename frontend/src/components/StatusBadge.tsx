import { CheckCircle, XCircle, AlertCircle, Loader2 } from 'lucide-react';

type Status = 'ok' | 'error' | 'degraded' | 'loading' | 'completed' | 'started';

interface StatusBadgeProps {
  status: Status;
  label?: string;
}

const config: Record<Status, { color: string; Icon: typeof CheckCircle }> = {
  ok: { color: 'bg-green-100 text-green-700', Icon: CheckCircle },
  completed: { color: 'bg-green-100 text-green-700', Icon: CheckCircle },
  error: { color: 'bg-red-100 text-red-700', Icon: XCircle },
  degraded: { color: 'bg-yellow-100 text-yellow-700', Icon: AlertCircle },
  loading: { color: 'bg-blue-100 text-blue-700', Icon: Loader2 },
  started: { color: 'bg-blue-100 text-blue-700', Icon: Loader2 },
};

export default function StatusBadge({ status, label }: StatusBadgeProps) {
  const { color, Icon } = config[status] || config.error;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${color}`}>
      <Icon size={13} className={status === 'loading' || status === 'started' ? 'animate-spin' : ''} />
      {label || status}
    </span>
  );
}
