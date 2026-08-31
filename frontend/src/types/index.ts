export interface WeeklySummary {
  period: string;
  total_revenue: number;
  total_profit: number;
  profit_margin_pct: number;
  total_orders: number;
  total_quantity: number;
  avg_order_value: number;
  unique_customers: number;
  top_category: string;
}

export interface TrendData {
  metric: string;
  direction: 'up' | 'down' | 'stable';
  growth_rate_pct: number;
  first_value: number;
  last_value: number;
  mean_value: number;
  sma_7: number | null;
}

export interface Anomaly {
  date: string;
  column: string;
  value: number;
  z_score?: number;
  anomaly_score?: number;
  method: string;
}

export interface CategoryPerformance {
  category: string;
  sub_category: string;
  total_sales: number;
  total_profit: number;
  profit_margin_pct: number;
  sales_share_pct: number;
  performance_rank: number;
}

export interface Evaluation {
  numerical_accuracy: number;
  completeness: number;
  readability: number;
  actionability: number;
  hallucination_free: number;
  overall_score: number;
  approved: boolean;
  feedback: string;
}

export interface PeriodComparison {
  total_sales_change_pct?: number;
  total_profit_change_pct?: number;
  total_orders_change_pct?: number;
}

export interface PipelineRun {
  run_id: string;
  timestamp: string;
  report_type: string;
  period: string;
  quality_score: number;
  evaluator_iterations: number;
  delivery_sent: boolean;
  error_count: number;
  weekly_summary?: Partial<WeeklySummary>;
  period_comparison?: PeriodComparison;
  evaluation?: Partial<Evaluation>;
}

export interface DailySales {
  order_date: string;
  total_sales: number;
  total_profit: number;
  total_orders: number;
}

export interface ReportFile {
  filename: string;
  company_id: number;
  created_at: number;
  size_bytes: number;
  has_html: boolean;
}

export interface HealthStatus {
  status: string;
  version: string;
  database: {
    connected: boolean;
    db_type: string;
    message: string;
  };
  scheduler_enabled: boolean;
  server_llm_key_configured: boolean;
  default_model: string;
}

export interface LLMSettings {
  apiKey: string;
  model: string;
}

export interface DbStats {
  total_orders: number;
  date_range: {
    min: string;
    max: string;
  };
  categories: Array<{ category: string; cnt: number }>;
}

export interface RagStats {
  status: string;
  total_chunks?: number;
  total_reports?: number;
  report_ids?: string[];
  error?: string;
}

export interface PipelineResult {
  run_id: string;
  status: string;
  weekly_summary: WeeklySummary;
  analysis_results: Record<string, unknown>;
  draft_report: string;
  evaluation: Evaluation;
  delivery_status: Record<string, unknown>;
  errors: string[];
}
