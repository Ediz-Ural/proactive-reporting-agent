import { useEffect, useState } from 'react';
import {
  Database, Brain, Clock, Mail, MessageSquare, FileOutput,
  CheckCircle, XCircle, Loader2,
} from 'lucide-react';
import { getHealth, getDbStats, getRagStats } from '../api/client';
import type { HealthStatus, DbStats, RagStats } from '../types';

export default function Settings() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [dbStats, setDbStats] = useState<DbStats | null>(null);
  const [ragStats, setRagStats] = useState<RagStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [healthRes, dbRes, ragRes] = await Promise.allSettled([
          getHealth(),
          getDbStats(),
          getRagStats(),
        ]);

        if (healthRes.status === 'fulfilled') setHealth(healthRes.value.data);
        if (dbRes.status === 'fulfilled') setDbStats(dbRes.value.data);
        if (ragRes.status === 'fulfilled') setRagStats(ragRes.value.data);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-blue-600" size={32} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-gray-900">Ayarlar</h2>

      {/* Database */}
      <SettingsCard icon={Database} title="Veritabani">
        <SettingsRow
          label="Tip"
          value={health?.database.db_type || 'N/A'}
        />
        <SettingsRow
          label="Durum"
          value={health?.database.connected ? 'Bagli' : 'Baglanti Yok'}
          status={health?.database.connected ? 'ok' : 'error'}
        />
        {dbStats && (
          <>
            <SettingsRow
              label="Toplam Kayit"
              value={dbStats.total_orders.toLocaleString()}
            />
            <SettingsRow
              label="Tarih Araligi"
              value={`${dbStats.date_range.min} - ${dbStats.date_range.max}`}
            />
            <SettingsRow
              label="Kategoriler"
              value={dbStats.categories.map(c => `${c.category} (${c.cnt})`).join(', ')}
            />
          </>
        )}
      </SettingsCard>

      {/* RAG */}
      <SettingsCard icon={Brain} title="RAG (ChromaDB)">
        <SettingsRow
          label="Durum"
          value={ragStats?.status === 'ok' ? 'Aktif' : 'Kapalı'}
          status={ragStats?.status === 'ok' ? 'ok' : 'error'}
        />
        {ragStats?.status === 'ok' && (
          <>
            <SettingsRow
              label="Toplam Chunk"
              value={String(ragStats.total_chunks || 0)}
            />
            <SettingsRow
              label="Rapor Sayisi"
              value={String(ragStats.total_reports || 0)}
            />
          </>
        )}
      </SettingsCard>

      {/* Scheduler */}
      <SettingsCard icon={Clock} title="Scheduler">
        <SettingsRow
          label="Durum"
          value={health?.scheduler_enabled ? 'Aktif' : 'Devre Disi'}
          status={health?.scheduler_enabled ? 'ok' : 'error'}
        />
        <SettingsRow
          label="Calisma Zamani"
          value="Her ayin 1'i, 08:00"
        />
      </SettingsCard>

      {/* Delivery */}
      <SettingsCard icon={Mail} title="Teslimat Kanallari">
        <div className="flex items-center gap-2">
          <FileOutput size={14} className="text-gray-400" />
          <span className="text-sm text-gray-600">Dosya:</span>
          <StatusIcon ok={true} />
          <span className="text-xs text-gray-400">data/reports/</span>
        </div>
        <div className="flex items-center gap-2">
          <Mail size={14} className="text-gray-400" />
          <span className="text-sm text-gray-600">E-posta:</span>
          <StatusIcon ok={false} />
          <span className="text-xs text-gray-400">SMTP yapilandirilmamis</span>
        </div>
        <div className="flex items-center gap-2">
          <MessageSquare size={14} className="text-gray-400" />
          <span className="text-sm text-gray-600">WhatsApp:</span>
          <StatusIcon ok={false} />
          <span className="text-xs text-gray-400">Twilio yapilandirilmamis</span>
        </div>
      </SettingsCard>

      {/* Evaluator */}
      <SettingsCard icon={CheckCircle} title="Evaluator">
        <SettingsRow label="Onay Esigi" value="0.70" />
        <SettingsRow label="Max Iterasyon" value="3" />
        <SettingsRow label="Writer Stratejisi" value="few_shot" />
      </SettingsCard>

      {/* Version Info */}
      <div className="text-xs text-gray-400 text-center">
        Proactive Reporting Agent v{health?.version || '0.6.0'} | Python + LangGraph + React
      </div>
    </div>
  );
}

function SettingsCard({
  icon: Icon,
  title,
  children,
}: {
  icon: typeof Database;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
      <div className="flex items-center gap-2 mb-4">
        <Icon size={18} className="text-gray-500" />
        <h3 className="text-sm font-semibold text-gray-700">{title}</h3>
      </div>
      <div className="space-y-3">{children}</div>
    </div>
  );
}

function SettingsRow({
  label,
  value,
  status,
}: {
  label: string;
  value: string;
  status?: 'ok' | 'error';
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-gray-500">{label}</span>
      <div className="flex items-center gap-2">
        {status && <StatusIcon ok={status === 'ok'} />}
        <span className="text-sm font-medium text-gray-900">{value}</span>
      </div>
    </div>
  );
}

function StatusIcon({ ok }: { ok: boolean }) {
  return ok ? (
    <CheckCircle size={14} className="text-green-500" />
  ) : (
    <XCircle size={14} className="text-red-400" />
  );
}
