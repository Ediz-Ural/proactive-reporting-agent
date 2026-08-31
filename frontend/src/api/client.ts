import axios from 'axios';
import type {
  HealthStatus,
  PipelineRun,
  ReportFile,
  DbStats,
  RagStats,
  PipelineResult,
  LLMSettings,
} from '../types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 180000, // 3 minutes for sync pipeline
});

// ── LLM credentials ─────────────────────────────────────────────────────────
// The user's own OpenAI key never leaves their browser except as a header on
// the requests that actually run the pipeline. It is not stored server-side.

const LLM_KEY_STORAGE = 'openai_api_key';
const LLM_MODEL_STORAGE = 'openai_model';

export const getLLMSettings = (): LLMSettings => ({
  apiKey: localStorage.getItem(LLM_KEY_STORAGE) || '',
  model: localStorage.getItem(LLM_MODEL_STORAGE) || '',
});

export const saveLLMSettings = ({ apiKey, model }: LLMSettings) => {
  if (apiKey) localStorage.setItem(LLM_KEY_STORAGE, apiKey);
  else localStorage.removeItem(LLM_KEY_STORAGE);

  if (model) localStorage.setItem(LLM_MODEL_STORAGE, model);
  else localStorage.removeItem(LLM_MODEL_STORAGE);
};

export const clearLLMSettings = () => {
  localStorage.removeItem(LLM_KEY_STORAGE);
  localStorage.removeItem(LLM_MODEL_STORAGE);
};

// JWT token + LLM credential interceptor
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  const { apiKey, model } = getLLMSettings();
  if (apiKey) config.headers['X-OpenAI-Key'] = apiKey;
  if (model) config.headers['X-OpenAI-Model'] = model;

  return config;
});

// 401 → redirect to login
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// ── Auth ────────────────────────────────────────────────────────────────────

export const login = (email: string, password: string) => {
  const formData = new URLSearchParams();
  formData.append('username', email);
  formData.append('password', password);
  return api.post<{ access_token: string; token_type: string; user: Record<string, unknown> }>(
    '/auth/login',
    formData,
    { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } },
  );
};

export const getMe = () => api.get('/auth/me');

export const logout = () => {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  window.location.href = '/login';
};

// ── Health (public) ─────────────────────────────────────────────────────────

export const getHealth = () =>
  api.get<HealthStatus>('/health');

// ── Runs ────────────────────────────────────────────────────────────────────

export const getRuns = (limit = 20) =>
  api.get<{ runs: PipelineRun[]; total: number }>(`/runs?limit=${limit}`);

export const getLatestRun = () =>
  api.get<{
    run: PipelineRun;
    report_content: string | null;
    report_html: string | null;
  }>('/runs/latest');

export const getRunDetail = (runId: string) =>
  api.get<{ run: PipelineRun }>(`/runs/${runId}`);

// ── Reports ─────────────────────────────────────────────────────────────────

export const getReports = (companyId?: number) =>
  api.get<{ reports: ReportFile[] }>('/reports', {
    params: companyId ? { company_id: companyId } : undefined,
  });

export const getReport = (filename: string, companyId?: number) =>
  api.get<{
    filename: string;
    company_id: number;
    content_md: string;
    content_html: string | null;
  }>(`/reports/${filename}`, {
    params: companyId ? { company_id: companyId } : undefined,
  });

// ── Stats ───────────────────────────────────────────────────────────────────

export const getDbStats = () =>
  api.get<DbStats>('/db/stats');

export const getRagStats = () =>
  api.get<RagStats>('/rag/stats');

// ── Pipeline ────────────────────────────────────────────────────────────────

export const runPipeline = (data: {
  start_date: string;
  end_date: string;
  report_type: string;
  recipients?: string[];
  company_id?: number;
}) => api.post<PipelineResult>('/run/sync', data);

export const runPipelineAsync = (data: {
  start_date: string;
  end_date: string;
  report_type: string;
  recipients?: string[];
  company_id?: number;
}) => api.post<{ run_id: string; status: string; message: string }>('/run', data);

export const runMonthly = () =>
  api.post<{ run_id: string; status: string; message: string }>('/run/monthly');

// ── Admin ───────────────────────────────────────────────────────────────────

export interface CompanyStat {
  company_id: number;
  company_name: string;
  total_orders: number;
  unique_customers: number;
  total_revenue: number;
  total_profit: number;
  profit_margin_pct: number;
  avg_order_value: number;
  avg_discount: number;
}

export interface CompanyStatsResponse {
  companies: CompanyStat[];
  totals: {
    total_orders: number;
    total_revenue: number;
    total_profit: number;
    total_customers: number;
  };
}

export const getCompanyStats = () =>
  api.get<CompanyStatsResponse>('/admin/company-stats');

export const getCompanies = () =>
  api.get<{ companies: Array<Record<string, unknown>> }>('/admin/companies');

export const createCompany = (data: { name: string; slug: string; email_domain?: string; segment: string }) =>
  api.post('/admin/companies', data);

export const getUsers = () =>
  api.get<{ users: Array<Record<string, unknown>> }>('/admin/users');

export const registerUser = (data: {
  email: string;
  password: string;
  full_name: string;
  company_id: number;
}) => api.post('/auth/register', data);

export const sendReportEmail = (data: {
  report_filename: string;
  company_id: number;
  recipients: string[];
}) => api.post('/admin/send-existing-report', data);

export const uploadData = (file: File, companyId?: number) => {
  const formData = new FormData();
  formData.append('file', file);
  const params = companyId ? `?company_id=${companyId}` : '';
  return api.post(`/admin/upload-data${params}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

export default api;
