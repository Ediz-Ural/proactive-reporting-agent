import axios from 'axios';
import type {
  HealthStatus,
  PipelineRun,
  ReportFile,
  DbStats,
  RagStats,
  PipelineResult,
} from '../types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 180000, // 3 minutes for sync pipeline
});

// Health
export const getHealth = () =>
  api.get<HealthStatus>('/health');

// Runs
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

// Reports
export const getReports = () =>
  api.get<{ reports: ReportFile[] }>('/reports');

export const getReport = (filename: string) =>
  api.get<{
    filename: string;
    content_md: string;
    content_html: string | null;
  }>(`/reports/${filename}`);

// Stats
export const getDbStats = () =>
  api.get<DbStats>('/db/stats');

export const getRagStats = () =>
  api.get<RagStats>('/rag/stats');

// Pipeline
export const runPipeline = (data: {
  start_date: string;
  end_date: string;
  report_type: string;
  recipients?: string[];
}) => api.post<PipelineResult>('/run/sync', data);

export const runPipelineAsync = (data: {
  start_date: string;
  end_date: string;
  report_type: string;
  recipients?: string[];
}) => api.post<{ run_id: string; status: string; message: string }>('/run', data);

export const runMonthly = () =>
  api.post<{ run_id: string; status: string; message: string }>('/run/monthly');

export default api;
