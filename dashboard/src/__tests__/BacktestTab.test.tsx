import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { BacktestTab } from '../tabs/BacktestTab';

// Mock @nivo/bar — ResponsiveBar can't render in jsdom
vi.mock('@nivo/bar', () => ({
  ResponsiveBar: () => null,
}));

// Mock hooks
vi.mock('../hooks/useBacktest', () => ({
  useBacktestSummary: vi.fn(),
  useBacktestBets: vi.fn(),
}));

import { useBacktestSummary, useBacktestBets } from '../hooks/useBacktest';

const mockSummary = {
  n_bets: 100,
  kelly_roi: 8.5,
  flat_roi: 4.2,
  total_pnl_kelly: 850,
  total_pnl_flat: 420,
  by_surface: [
    { surface: 'Hard', kelly_roi: 10.2 },
    { surface: 'Clay', kelly_roi: -2.1 },
  ],
  by_tourney_level: [
    { tourney_level: 'G', kelly_roi: 12.0 },
    { tourney_level: 'M', kelly_roi: 5.5 },
  ],
  by_year: [
    { year: '2021', kelly_roi: 7.1 },
    { year: '2022', kelly_roi: 9.3 },
  ],
  by_ev_bucket: [
    { ev_bucket: '0-2%', kelly_roi: 3.1 },
    { ev_bucket: '2-5%', kelly_roi: 8.4 },
  ],
  by_rank_tier: [
    { rank_tier: 'Top 10', kelly_roi: 11.0 },
    { rank_tier: '11-50', kelly_roi: 6.2 },
  ],
};

const mockBetsResponse = {
  total: 2,
  offset: 0,
  limit: 20,
  data: [
    {
      id: 1,
      fold_year: 2022,
      tourney_id: 'aus-open-2022',
      match_num: 101,
      tour: 'atp',
      model_version: 'logistic_v1',
      player_id: 100,
      outcome: 1,
      calibrated_prob: 0.65,
      decimal_odds: 1.8,
      ev: 0.04,
      kelly_bet: 0.08,
      pnl_kelly: 64.0,
      pnl_flat: 80.0,
      bankroll_before: 1000,
      bankroll_after: 1064,
      surface: 'Hard',
      tourney_level: 'G',
      tourney_date: '2022-01-17',
    },
  ],
};

describe('BacktestTab', () => {
  beforeEach(() => {
    vi.mocked(useBacktestSummary).mockReturnValue({
      data: mockSummary,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useBacktestSummary>);

    vi.mocked(useBacktestBets).mockReturnValue({
      data: mockBetsResponse,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useBacktestBets>);
  });

  it('renders filter bar with Surface, Year, Model labels', () => {
    render(<BacktestTab />);
    // Use getAllByText since labels appear in both filter bar and table headers
    expect(screen.getAllByText('Surface').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Year').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Model').length).toBeGreaterThanOrEqual(1);
  });

  it('renders 5 chart containers with role="img"', () => {
    render(<BacktestTab />);
    const charts = screen.getAllByRole('img');
    expect(charts).toHaveLength(5);
  });

  it('shows empty state when no data', () => {
    vi.mocked(useBacktestSummary).mockReturnValue({
      data: { ...mockSummary, n_bets: 0 },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useBacktestSummary>);

    render(<BacktestTab />);
    expect(screen.getByText('No backtest results')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Run a backtest to see ROI breakdowns and bet history. Use the API or CLI to trigger a run.'
      )
    ).toBeInTheDocument();
  });

  it('shows skeleton loaders when summary isLoading=true', () => {
    vi.mocked(useBacktestSummary).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as unknown as ReturnType<typeof useBacktestSummary>);

    vi.mocked(useBacktestBets).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as unknown as ReturnType<typeof useBacktestBets>);

    render(<BacktestTab />);
    const loadingIndicators = document.querySelectorAll('[aria-busy="true"]');
    expect(loadingIndicators.length).toBeGreaterThan(0);
  });

  it('renders bet history table with "Showing" pagination text', () => {
    render(<BacktestTab />);
    expect(screen.getByText(/Showing/)).toBeInTheDocument();
  });
});
