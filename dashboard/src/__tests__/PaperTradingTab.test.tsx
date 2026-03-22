import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { PaperTradingTab } from '../tabs/PaperTradingTab';
import type { PaperSession, PaperBet } from '../api/types';

// Mock lightweight-charts
const mockSeries = { setData: vi.fn() };
const mockChart = {
  addSeries: vi.fn(() => mockSeries),
  timeScale: vi.fn(() => ({ fitContent: vi.fn() })),
  remove: vi.fn(),
  applyOptions: vi.fn(),
};
vi.mock('lightweight-charts', () => ({
  createChart: vi.fn(() => mockChart),
  LineSeries: {},
  ColorType: { Solid: 'solid' },
}));

vi.mock('../hooks/usePaperTrading', () => ({
  usePaperSession: vi.fn(),
  usePaperBets: vi.fn(),
  usePaperEquity: vi.fn(),
  useStartSession: vi.fn(),
  useResetSession: vi.fn(),
  useResolveBet: vi.fn(),
}));

import {
  usePaperSession,
  usePaperBets,
  usePaperEquity,
  useStartSession,
  useResetSession,
  useResolveBet,
} from '../hooks/usePaperTrading';

const mockMutate = vi.fn();

const noSessionState = {
  data: undefined,
  isLoading: false,
  isError: false,
};

const activeSession: PaperSession = {
  id: 1,
  initial_bankroll: 1000,
  current_bankroll: 1500,
  kelly_fraction: 0.25,
  ev_threshold: 2.0,
  started_at: '2024-01-01T00:00:00Z',
  active: 1,
  total_bets: 10,
  resolved_bets: 6,
  win_rate: 0.6,
  total_pnl: 500,
};

const activeSessionState = {
  data: activeSession,
  isLoading: false,
  isError: false,
};

const noBetsState = {
  data: { data: [] },
  isLoading: false,
  isError: false,
};

const mockBets: PaperBet[] = [
  {
    id: 1,
    session_id: 1,
    tourney_id: '2024-540',
    match_num: 1,
    player_id: 104745,
    model_version: 'ensemble_v1',
    calibrated_prob: 0.65,
    decimal_odds: 1.85,
    ev_value: 8.2,
    kelly_stake: 42.50,
    bankroll_before: 1000,
    bankroll_after: 1042.50,
    outcome: 1,
    pnl: 42.50,
    placed_at: '2024-01-15T10:00:00Z',
    resolved_at: '2024-01-16T10:00:00Z',
    result_source: null,
  },
  {
    id: 2,
    session_id: 1,
    tourney_id: '2024-540',
    match_num: 2,
    player_id: 104925,
    model_version: 'ensemble_v1',
    calibrated_prob: 0.58,
    decimal_odds: 2.10,
    ev_value: 3.1,
    kelly_stake: 28.00,
    bankroll_before: 1042.50,
    bankroll_after: null,
    outcome: null,
    pnl: null,
    placed_at: '2024-01-17T10:00:00Z',
    resolved_at: null,
    result_source: null,
  },
];

const betsState = {
  data: { data: mockBets },
  isLoading: false,
  isError: false,
};

const equityState = {
  data: {
    initial: 1000,
    current: 1500,
    total_pnl: 500,
    win_rate: 0.6,
    curve: [
      { date: '2024-01-15', bankroll: 1042.50 },
      { date: '2024-01-17', bankroll: 1500 },
    ],
  },
  isLoading: false,
  isError: false,
};

const emptyEquityState = {
  data: { initial: 1000, current: 1000, total_pnl: 0, win_rate: null, curve: [] },
  isLoading: false,
  isError: false,
};

function setupNoSession() {
  vi.mocked(usePaperSession).mockReturnValue(noSessionState as any);
  vi.mocked(usePaperBets).mockReturnValue(noBetsState as any);
  vi.mocked(usePaperEquity).mockReturnValue(emptyEquityState as any);
  vi.mocked(useStartSession).mockReturnValue({ mutate: mockMutate, isPending: false } as any);
  vi.mocked(useResetSession).mockReturnValue({ mutate: mockMutate, isPending: false } as any);
  vi.mocked(useResolveBet).mockReturnValue({ mutate: mockMutate, isPending: false } as any);
}

function setupActiveSession(hasBets = false) {
  vi.mocked(usePaperSession).mockReturnValue(activeSessionState as any);
  vi.mocked(usePaperBets).mockReturnValue(hasBets ? betsState as any : noBetsState as any);
  vi.mocked(usePaperEquity).mockReturnValue(hasBets ? equityState as any : emptyEquityState as any);
  vi.mocked(useStartSession).mockReturnValue({ mutate: mockMutate, isPending: false } as any);
  vi.mocked(useResetSession).mockReturnValue({ mutate: mockMutate, isPending: false } as any);
  vi.mocked(useResolveBet).mockReturnValue({ mutate: mockMutate, isPending: false } as any);
}

describe('PaperTradingTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows "No active session" empty state when no session exists', () => {
    setupNoSession();
    render(<PaperTradingTab />);
    expect(screen.getByText('No active session')).toBeInTheDocument();
  });

  it('shows "Start Session" button when no session', () => {
    setupNoSession();
    render(<PaperTradingTab />);
    expect(screen.getByRole('button', { name: /start session/i })).toBeInTheDocument();
  });

  it('shows KPI cards when session active', () => {
    setupActiveSession(false);
    render(<PaperTradingTab />);
    expect(screen.getByText('BANKROLL')).toBeInTheDocument();
    expect(screen.getByText('P&L')).toBeInTheDocument();
    expect(screen.getByText('WIN RATE')).toBeInTheDocument();
    expect(screen.getByText('BETS')).toBeInTheDocument();
  });

  it('shows bankroll value in KPI card when session active', () => {
    setupActiveSession(false);
    render(<PaperTradingTab />);
    expect(screen.getByText('$1500.00')).toBeInTheDocument();
  });

  it('shows "No bets placed yet" when session active but no bets', () => {
    setupActiveSession(false);
    render(<PaperTradingTab />);
    expect(screen.getByText('No bets placed yet')).toBeInTheDocument();
  });

  it('shows "Reset Session" button when session active', () => {
    setupActiveSession(false);
    render(<PaperTradingTab />);
    expect(screen.getByRole('button', { name: /reset session/i })).toBeInTheDocument();
  });

  it('shows bet history table when bets exist', () => {
    setupActiveSession(true);
    render(<PaperTradingTab />);
    expect(screen.getByText('Bet History')).toBeInTheDocument();
  });

  it('shows "Paper Trading" heading text', () => {
    setupNoSession();
    render(<PaperTradingTab />);
    expect(screen.getByText('Paper Trading')).toBeInTheDocument();
  });

  it('shows "Pending" badge for unresolved bet', () => {
    setupActiveSession(true);
    render(<PaperTradingTab />);
    expect(screen.getByText('Pending')).toBeInTheDocument();
  });

  it('shows Win/Loss resolution buttons for pending bets', () => {
    setupActiveSession(true);
    render(<PaperTradingTab />);
    // There should be Win and Loss buttons for the pending bet (bet id=2)
    const winButtons = screen.getAllByRole('button', { name: /^win$/i });
    const lossButtons = screen.getAllByRole('button', { name: /^loss$/i });
    expect(winButtons.length).toBeGreaterThan(0);
    expect(lossButtons.length).toBeGreaterThan(0);
  });
});
