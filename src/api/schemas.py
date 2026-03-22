"""
Pydantic v2 request and response schemas for the Tennis Betting API.

All response models use ConfigDict(from_attributes=True) to support
ORM-style attribute access (SQLAlchemy row objects → schema instances).

Organization:
    - Common/error schemas
    - Prediction schemas (GET /predict)
    - Backtest schemas (GET /backtest, /bets, /bankroll, /models, /calibration)
    - Odds schemas (POST /odds, /odds/upload)
    - Props schemas (GET /props, POST /props)
    - Job/status schemas (POST /refresh, /backtest/run)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Common / error
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    """Structured error payload returned by the custom exception handler."""
    model_config = ConfigDict(from_attributes=True)

    error: str
    message: str
    detail: Optional[str] = None


class PaginatedResponse(BaseModel):
    """Generic pagination wrapper — subclassed by concrete paginated responses."""
    model_config = ConfigDict(from_attributes=True)

    total: int
    offset: int
    limit: int
    data: List[Any]


# ---------------------------------------------------------------------------
# Prediction schemas
# ---------------------------------------------------------------------------

class PredictionRow(BaseModel):
    """Single row from the predictions table."""
    model_config = ConfigDict(from_attributes=True)

    tourney_id: str
    match_num: int
    tour: str
    player_id: int
    model_version: str
    calibrated_prob: Optional[float] = None
    ev_value: Optional[float] = None
    edge: Optional[float] = None
    decimal_odds: Optional[float] = None
    predicted_at: str


class PredictResponse(BaseModel):
    """Response for GET /predict."""
    model_config = ConfigDict(from_attributes=True)

    data: List[PredictionRow]


# ---------------------------------------------------------------------------
# Backtest schemas
# ---------------------------------------------------------------------------

class BacktestSummary(BaseModel):
    """Aggregated backtest performance metrics."""
    model_config = ConfigDict(from_attributes=True)

    n_bets: int
    kelly_roi: float
    flat_roi: float
    total_pnl_kelly: float
    total_pnl_flat: float
    by_surface: List[Dict[str, Any]]
    by_tourney_level: List[Dict[str, Any]]
    by_year: List[Dict[str, Any]]
    by_ev_bucket: List[Dict[str, Any]]
    by_rank_tier: List[Dict[str, Any]]


class BacktestBetRow(BaseModel):
    """Single row from the backtest_results table."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    fold_year: int
    tourney_id: str
    match_num: int
    tour: str
    model_version: str
    player_id: int
    outcome: int
    calibrated_prob: float
    decimal_odds: float
    ev: float
    kelly_bet: float
    pnl_kelly: float
    pnl_flat: float
    bankroll_before: float
    bankroll_after: float
    surface: Optional[str] = None
    tourney_level: Optional[str] = None
    tourney_date: str


class PaginatedBetsResponse(BaseModel):
    """Paginated response for GET /bets."""
    model_config = ConfigDict(from_attributes=True)

    total: int
    offset: int
    limit: int
    data: List[BacktestBetRow]


class BankrollPoint(BaseModel):
    """Single (date, bankroll) data point for the equity curve."""
    model_config = ConfigDict(from_attributes=True)

    date: str
    bankroll: float


class BankrollResponse(BaseModel):
    """Bankroll curve and summary statistics."""
    model_config = ConfigDict(from_attributes=True)

    initial: float
    current: float
    peak: float
    max_drawdown: float
    curve: List[BankrollPoint]


class ModelMetrics(BaseModel):
    """Per-model performance summary for GET /models."""
    model_config = ConfigDict(from_attributes=True)

    model_version: str
    brier_score: Optional[float] = None
    log_loss: Optional[float] = None
    calibration_quality: Optional[str] = None
    kelly_roi: Optional[float] = None
    flat_roi: Optional[float] = None
    total_bets: int


class ModelsResponse(BaseModel):
    """Response for GET /models — lists all available models."""
    model_config = ConfigDict(from_attributes=True)

    data: List[ModelMetrics]


class CalibrationBin(BaseModel):
    """One bin in a calibration reliability diagram."""
    model_config = ConfigDict(from_attributes=True)

    midpoint: float
    empirical_freq: float
    n_samples: int


class CalibrationResponse(BaseModel):
    """Calibration data for a specific model/fold combination."""
    model_config = ConfigDict(from_attributes=True)

    model_version: str
    fold: Optional[str] = None
    bins: List[CalibrationBin]


# ---------------------------------------------------------------------------
# Props schemas
# ---------------------------------------------------------------------------

class PropsResponse(BaseModel):
    """Response for GET /props — stub until Phase 8."""
    model_config = ConfigDict(from_attributes=True)

    status: str  # 'not_available' in v1
    data: List[Any]


class PropLineEntry(BaseModel):
    """Request body for POST /props — manual PrizePicks line entry."""
    model_config = ConfigDict(from_attributes=True)

    player_name: str
    stat_type: str
    line_value: float
    direction: str
    match_date: str
    bookmaker: str = "prizepicks"


class PropLineResponse(BaseModel):
    """Response row after inserting a prop line."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    player_name: str
    stat_type: str
    line_value: float
    direction: str
    match_date: str


class PropPredictionRow(BaseModel):
    """Single prop prediction row joined with optional bookmaker line data."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    player_name: str
    stat_type: str
    match_date: str
    mu: float
    pmf: List[float]
    model_version: str
    actual_value: Optional[int] = None
    resolved_at: Optional[str] = None
    line_value: Optional[float] = None
    direction: Optional[str] = None
    p_hit: Optional[float] = None


class PropsListResponse(BaseModel):
    """Response for GET /props — real predictions when available."""
    model_config = ConfigDict(from_attributes=True)

    status: str
    data: List[PropPredictionRow]


class PropAccuracyBin(BaseModel):
    """One calibration bin for P(hit) reliability diagram."""
    model_config = ConfigDict(from_attributes=True)

    predicted_p: float
    actual_hit_rate: float
    n: int


class PropAccuracyResponse(BaseModel):
    """Response for GET /props/accuracy — prop prediction performance metrics."""
    model_config = ConfigDict(from_attributes=True)

    status: str
    overall_hit_rate: Optional[float] = None
    hit_rate_by_stat: Dict[str, Optional[float]]
    total_tracked: int
    rolling_30d: List[Dict[str, Any]]
    calibration_bins: List[PropAccuracyBin]


# ---------------------------------------------------------------------------
# Odds schemas
# ---------------------------------------------------------------------------

class OddsEntry(BaseModel):
    """Request body for POST /odds/manual."""
    model_config = ConfigDict(from_attributes=True)

    player_a: str
    player_b: str
    odds_a: float
    odds_b: float
    match_date: str
    bookmaker: str = "pinnacle"


class OddsEntryResponse(BaseModel):
    """Response for POST /odds/manual — indicates whether match was linked."""
    model_config = ConfigDict(from_attributes=True)

    linked: bool
    tourney_id: Optional[str] = None
    match_num: Optional[int] = None
    candidates: Optional[List[str]] = None
    message: str


class OddsUploadResponse(BaseModel):
    """Response for POST /odds/upload — CSV import summary."""
    model_config = ConfigDict(from_attributes=True)

    imported: int
    skipped: int
    total: int


# ---------------------------------------------------------------------------
# Job / status schemas
# ---------------------------------------------------------------------------

class JobResponse(BaseModel):
    """Immediate response when a background job is created."""
    model_config = ConfigDict(from_attributes=True)

    job_id: str
    status: str


class RefreshStatusResponse(BaseModel):
    """Status poll response for GET /refresh/{job_id}."""
    model_config = ConfigDict(from_attributes=True)

    job_id: str
    status: str
    step: Optional[str] = None
    started_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class BacktestRunStatus(BaseModel):
    """Status poll response for GET /backtest/run/{job_id}."""
    model_config = ConfigDict(from_attributes=True)

    job_id: str
    status: str
    started_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class BacktestRunRequest(BaseModel):
    """Request body for POST /backtest/run."""
    model_config = ConfigDict(from_attributes=True)

    kelly_fraction: float = 0.25
    max_bet_pct: float = 0.03
    ev_threshold: float = 0.0
    initial_bankroll: float = 1000.0
    model_version: str = "logistic_v1"


# ---------------------------------------------------------------------------
# Simulation schemas (Phase 9)
# ---------------------------------------------------------------------------

class MonteCarloRequest(BaseModel):
    """Request body for POST /simulation/run."""
    model_config = ConfigDict(from_attributes=True)
    n_seasons: int = 1000
    initial_bankroll: float = 1000.0
    kelly_fraction: float = 0.25
    ev_threshold: float = 0.0


class PercentilePath(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    step: int
    p5: float
    p25: float
    p50: float
    p75: float
    p95: float


class MonteCarloResult(BaseModel):
    """Response for GET /simulation/result and POST /simulation/run."""
    model_config = ConfigDict(from_attributes=True)
    p_ruin: float
    expected_terminal: float
    sharpe_ratio: float
    paths: List[PercentilePath]
    terminal_distribution: List[float]
    n_seasons: int
    initial_bankroll: float


# ---------------------------------------------------------------------------
# Signal schemas (Phase 9)
# ---------------------------------------------------------------------------

class SignalRecord(BaseModel):
    """Signal row with prediction data and status."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    tourney_id: str
    match_num: int
    tour: str
    player_id: int
    model_version: str
    status: str
    calibrated_prob: Optional[float] = None
    ev_value: Optional[float] = None
    edge: Optional[float] = None
    decimal_odds: Optional[float] = None
    kelly_stake: Optional[float] = None
    confidence: Optional[float] = None
    sharpe: Optional[float] = None
    predicted_at: Optional[str] = None
    created_at: str


class SignalsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    data: List[SignalRecord]


class SignalStatusUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str  # "seen" | "acted-on"


# ---------------------------------------------------------------------------
# Paper Trading schemas (Phase 9)
# ---------------------------------------------------------------------------

class PaperSessionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    initial_bankroll: float = 1000.0
    kelly_fraction: float = 0.25
    ev_threshold: float = 0.0


class PaperSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    initial_bankroll: float
    current_bankroll: float
    kelly_fraction: float
    ev_threshold: float
    started_at: str
    active: int
    total_bets: int = 0
    resolved_bets: int = 0
    win_rate: Optional[float] = None
    total_pnl: float = 0.0


class PaperBetPlace(BaseModel):
    """Request to place a paper bet from a signal."""
    model_config = ConfigDict(from_attributes=True)
    signal_id: int


class PaperBetRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    session_id: int
    tourney_id: str
    match_num: int
    player_id: int
    model_version: str
    calibrated_prob: float
    decimal_odds: float
    ev_value: float
    kelly_stake: float
    bankroll_before: float
    bankroll_after: Optional[float] = None
    outcome: Optional[int] = None
    pnl: Optional[float] = None
    placed_at: str
    resolved_at: Optional[str] = None
    result_source: Optional[str] = None


class PaperBetsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    data: List[PaperBetRow]


class PaperBetResolve(BaseModel):
    """Manual resolution of a paper bet."""
    model_config = ConfigDict(from_attributes=True)
    outcome: int  # 1=won, 0=lost


class PaperEquityPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    date: str
    bankroll: float


class PaperEquityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    initial: float
    current: float
    total_pnl: float
    win_rate: Optional[float] = None
    curve: List[PaperEquityPoint]


# ---------------------------------------------------------------------------
# Manual entry CRUD schemas (Phase 9 — DASH-07)
# ---------------------------------------------------------------------------

class OddsListRow(BaseModel):
    """Row in the odds CRUD list."""
    model_config = ConfigDict(from_attributes=True)
    tourney_id: str
    match_num: int
    tour: str
    bookmaker: str
    decimal_odds_a: float
    decimal_odds_b: float
    source: str
    imported_at: str


class OddsListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    data: List[OddsListRow]


class PropLineListRow(BaseModel):
    """Row in the prop lines CRUD list."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    player_name: str
    stat_type: str
    line_value: float
    direction: str
    match_date: str
    bookmaker: str
    entered_at: str


class PropLinesListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    data: List[PropLineListRow]
