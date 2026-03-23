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

export interface PropLineResponse {
  id: number;
  player_name: string;
  stat_type: string;
  line_value: number;
  direction: string;
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

// Screenshot scan schemas (Phase 10)
export interface PropScanCard {
  player_name: string;
  stat_type: 'aces' | 'games_won' | 'double_faults';
  line_value: number;
  directions: Array<'over' | 'under'>;
}

export interface PropScanResponse {
  status: string;
  cards: PropScanCard[];
}

// Monte Carlo simulation schemas (Phase 9)
export interface PercentilePath {
  step: number;
  p5: number;
  p25: number;
  p50: number;
  p75: number;
  p95: number;
}

export interface MonteCarloRequest {
  n_seasons: number;
  initial_bankroll: number;
  kelly_fraction: number;
  ev_threshold: number;
}

export interface MonteCarloResult {
  p_ruin: number;
  expected_terminal: number;
  sharpe_ratio: number;
  paths: PercentilePath[];
  terminal_distribution: number[];
  n_seasons: number;
  initial_bankroll: number;
}

// Manual entry CRUD types (Phase 9 — DASH-07)
export interface OddsListRow {
  tourney_id: string;
  match_num: number;
  tour: string;
  bookmaker: string;
  decimal_odds_a: number;
  decimal_odds_b: number;
  source: string;
  imported_at: string;
}

export interface OddsListResponse {
  data: OddsListRow[];
}

export interface PropLineListRow {
  id: number;
  player_name: string;
  stat_type: string;
  line_value: number;
  direction: string;
  match_date: string;
  bookmaker: string;
  entered_at: string;
}

export interface PropLinesListResponse {
  data: PropLineListRow[];
}

export interface OddsEntry {
  player_a: string;
  player_b: string;
  odds_a: number;
  odds_b: number;
  match_date: string;
  bookmaker: string;
}

export interface OddsEntryResponse {
  linked: boolean;
  tourney_id: string | null;
  match_num: number | null;
  candidates: string[] | null;
  message: string;
}

// Signal schemas (Phase 9)
export interface SignalRecord {
  id: number;
  tourney_id: string;
  match_num: number;
  tour: string;
  player_id: number;
  model_version: string;
  status: 'new' | 'seen' | 'acted-on' | 'expired';
  calibrated_prob: number | null;
  ev_value: number | null;
  edge: number | null;
  decimal_odds: number | null;
  kelly_stake: number | null;
  confidence: number | null;
  sharpe: number | null;
  predicted_at: string | null;
  created_at: string;
}

export interface SignalsResponse {
  data: SignalRecord[];
}

// Paper Trading schemas (Phase 9)
export interface PaperSession {
  id: number;
  initial_bankroll: number;
  current_bankroll: number;
  kelly_fraction: number;
  ev_threshold: number;
  started_at: string;
  active: number;
  total_bets: number;
  resolved_bets: number;
  win_rate: number | null;
  total_pnl: number;
}

export interface PaperBet {
  id: number;
  session_id: number;
  tourney_id: string;
  match_num: number;
  player_id: number;
  model_version: string;
  calibrated_prob: number;
  decimal_odds: number;
  ev_value: number;
  kelly_stake: number;
  bankroll_before: number;
  bankroll_after: number | null;
  outcome: number | null;
  pnl: number | null;
  placed_at: string;
  resolved_at: string | null;
  result_source: string | null;
}

export interface PaperBetsResponse {
  data: PaperBet[];
}

export interface PaperEquityPoint {
  date: string;
  bankroll: number;
}

export interface PaperEquityResponse {
  initial: number;
  current: number;
  total_pnl: number;
  win_rate: number | null;
  curve: PaperEquityPoint[];
}
