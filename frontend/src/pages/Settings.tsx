import { useEffect, useState } from 'react';
import {
  Database, Brain, Clock, Mail, MessageSquare, FileOutput,
  CheckCircle, XCircle, Loader2, KeyRound, Eye, EyeOff,
} from 'lucide-react';
import {
  getHealth, getDbStats, getRagStats,
  getLLMSettings, saveLLMSettings, clearLLMSettings,
} from '../api/client';
import type { HealthStatus, DbStats, RagStats } from '../types';

const MODEL_OPTIONS = [
  'gpt-4o',
  'gpt-4o-mini',
  'gpt-4.1',
  'gpt-4.1-mini',
  'o4-mini',
];

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

      {/* OpenAI credentials */}
      <LLMSettingsCard
        serverKeyConfigured={health?.server_llm_key_configured ?? false}
        defaultModel={health?.default_model || 'gpt-4o'}
      />

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

function LLMSettingsCard({
  serverKeyConfigured,
  defaultModel,
}: {
  serverKeyConfigured: boolean;
  defaultModel: string;
}) {
  const stored = getLLMSettings();
  const [apiKey, setApiKey] = useState(stored.apiKey);
  const [model, setModel] = useState(stored.model || defaultModel);
  const [showKey, setShowKey] = useState(false);
  const [saved, setSaved] = useState(false);

  const isCustomModel = model !== '' && !MODEL_OPTIONS.includes(model);
  const hasKey = apiKey.trim().length > 0;

  function handleSave() {
    saveLLMSettings({ apiKey: apiKey.trim(), model: model.trim() });
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }

  function handleClear() {
    clearLLMSettings();
    setApiKey('');
    setModel(defaultModel);
    setShowKey(false);
  }

  return (
    <SettingsCard icon={KeyRound} title="OpenAI Anahtari ve Model">
      <p className="text-xs text-gray-500">
        Anahtariniz yalnizca bu sekmede tutulur ve sadece rapor calistirdiginizda
        istek basligi olarak gonderilir. Sunucu anahtari diske yazmaz; sekmeyi
        kapattiginizda anahtar tarayicidan da silinir, yeniden girmeniz gerekir.
        Model tercihiniz sir olmadigi icin kalici olarak hatirlanir.
      </p>

      <div className="space-y-1">
        <label className="text-sm text-gray-500" htmlFor="openai-key">API Anahtari</label>
        <div className="flex gap-2">
          <input
            id="openai-key"
            type={showKey ? 'text' : 'password'}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="sk-..."
            autoComplete="off"
            spellCheck={false}
            className="flex-1 rounded-lg border border-gray-200 px-3 py-2 text-sm font-mono
                       focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="button"
            onClick={() => setShowKey((v) => !v)}
            aria-label={showKey ? 'Anahtari gizle' : 'Anahtari goster'}
            className="rounded-lg border border-gray-200 px-3 text-gray-500 hover:bg-gray-50"
          >
            {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        </div>
      </div>

      <div className="space-y-1">
        <label className="text-sm text-gray-500" htmlFor="openai-model">Model</label>
        <select
          id="openai-model"
          value={isCustomModel ? 'custom' : model}
          onChange={(e) => setModel(e.target.value === 'custom' ? '' : e.target.value)}
          className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm
                     focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {MODEL_OPTIONS.map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
          <option value="custom">Diger (elle gir)</option>
        </select>

        {isCustomModel || model === '' ? (
          <input
            type="text"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="orn. gpt-4.1-nano"
            spellCheck={false}
            className="mt-2 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm font-mono
                       focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        ) : null}
      </div>

      {!hasKey && !serverKeyConfigured && (
        <p className="text-xs text-amber-600">
          Anahtar girilmedi ve sunucuda da tanimli degil — pipeline calisir ama
          LLM adimlari (yazar, degerlendirici) atlanir.
        </p>
      )}
      {!hasKey && serverKeyConfigured && (
        <p className="text-xs text-gray-500">
          Anahtar girilmedi — sunucudaki varsayilan anahtar kullanilir.
        </p>
      )}

      <div className="flex items-center gap-2 pt-1">
        <button
          type="button"
          onClick={handleSave}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white
                     hover:bg-blue-700"
        >
          Kaydet
        </button>
        <button
          type="button"
          onClick={handleClear}
          className="rounded-lg border border-gray-200 px-4 py-2 text-sm text-gray-600
                     hover:bg-gray-50"
        >
          Temizle
        </button>
        {saved && (
          <span className="flex items-center gap-1 text-xs text-green-600">
            <CheckCircle size={14} /> Kaydedildi
          </span>
        )}
      </div>
    </SettingsCard>
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
