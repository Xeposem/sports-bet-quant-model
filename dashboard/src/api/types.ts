// Prediction schemas
export interface PredictionRow {
  tourney_id: string;
  match_num: number;
  tour: string;
  player_id: number;
  model_version: string;
  calibrated_prob: number | null;
  ev_value: number | null;
  edge: number | null;
  decimal_odds: number | null;
  predicted_at: string;
}
export interface PredictResponse { data: PredictionRow[]; }

// Backtest schemas
export interface BacktestSummary {
  n_bets: number;
  kelly_roi: number;
  flat_roi: number;
  total_pnl_kelly: number;
  total_pnl_flat: number;
  by_surface: Record<string, unknown>[];
  by_tourney_level: Record<string, unknown>[];
  by_year: Record<string, unknown>[];
  by_ev_bucket: Record<string, unknown>[];
  by_rank_tier: Record<string, unknown>[];
}
export interface BacktestBetRow {
  id: number;
  fold_year: number;
  tourney_id: string;
  match_num: number;
  tour: string;
  model_version: string;
  player_id: number;
  outcome: number;
  calibrated_prob: number;
  decimal_odds: number;
  ev: number;
  kelly_bet: number;
  pnl_kelly: number;
  pnl_flat: number;
  bankroll_before: number;
  bankroll_after: number;
  surface: string | null;
  tourney_level: string | null;
  tourney_date: string;
}
export interface PaginatedBetsResponse {
  total: number;
  offset: number;
  limit: number;
  data: BacktestBetRow[];
}

// Bankroll schemas
export interface BankrollPoint { date: string; bankroll: number; }
export interface BankrollResponse {
  initial: number;
  current: number;
  peak: number;
  max_drawdown: number;
  curve: BankrollPoint[];
}

// Model schemas
export interface ModelMetrics {
  model_version: string;
  brier_score: number | null;
  log_loss: number | null;
  calibration_quality: string | null;
  kelly_roi: number | null;
  flat_roi: number | null;
  total_bets: number;
}
export interface ModelsResponse { data: ModelMetrics[]; }

// Calibration schemas
export interface CalibrationBin { midpoint: number; empirical_freq: number; n_samples: number; }
export interface CalibrationResponse {
  model_version: string;
  fold: string | null;
  bins: CalibrationBin[];
}

// Job/refresh schemas
export interface JobResponse { job_id: string; status: string; }
export interface RefreshStatusResponse {
  job_id: string;
  status: string;
  step: string | null;
  started_at: string | null;
  result: Record<string, unknown> | null;
}

// Props schemas
export interface PropPrediction {
  id: number;
  player_name: string;
  stat_type: 'aces' | 'games_won' | 'double_faults';
  match_date: string;
  mu: number;
  pmf: number[];
  model_version: string;
  actual_value: number | null;
  resolved_at: string | null;
  line_value: number | null;
  direction: 'over' | 'under' | null;
  p_hit: number | null;
}

export interface PropLineEntry {
  player_name: string;
  stat_type: 'aces' | 'games_won' | 'double_faults';
  line_value: number;
  direction: 'over' | 'under';
  match_date: string;
}

export interface PropsListResponse {
  status: string;
  data: PropPrediction[];
}

export interface PropAccuracyBin {
  predicted_p: number;
  actual_hit_rate: number;
  n: number;
}

export interface PropAccuracyResponse {
  status: string;
  overall_hit_rate: number | null;
  hit_rate_by_stat: Record<string, number | null>;
  total_tracked: number;
  rolling_30d: Array<{ date: string; hit_rate: number }>;
  calibration_bins: PropAccuracyBin[];
}
