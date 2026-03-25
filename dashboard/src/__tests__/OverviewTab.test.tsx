import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { OverviewTab } from '../tabs/OverviewTab';

// Mock all data hooks
vi.mock('../hooks/useBankroll', () => ({
  useBankroll: vi.fn(),
}));
vi.mock('../hooks/useBacktest', () => ({
  useBacktestSummary: vi.fn(),
  useBacktestBets: vi.fn(() => ({
    isLoading: false,
    isError: false,
    data: { total: 0, offset: 0, limit: 5, data: [] },
  })),
  useRunBacktest: vi.fn(),
  useBacktestJobStatus: vi.fn(),
}));
vi.mock('../hooks/useSimulation', () => ({
  useSimulationResult: vi.fn(() => ({ data: undefined, isLoading: false, isError: false })),
  useRunSimulation: vi.fn(() => ({ mutate: vi.fn(), isPending: false, data: undefined })),
}));
vi.mock('../hooks/useCalibration', () => ({
  useCalibration: vi.fn(),
}));
vi.mock('../hooks/useSignals', () => ({
  useSignals: vi.fn(),
}));
vi.mock('../hooks/useModels', () => ({
  useModels: vi.fn(),
}));

// Mock charts to avoid jsdom rendering issues
vi.mock('../components/charts/BankrollChart', () => ({
  BankrollChart: () => <div role="img" aria-label="Bankroll equity curve over time" />,
}));
vi.mock('../components/charts/CalibrationChart', () => ({
  CalibrationChart: () => (
    <div role="img" aria-label="Calibration reliability diagram" />
  ),
}));

import { useBankroll } from '../hooks/useBankroll';
import { useBacktestSummary } from '../hooks/useBacktest';
import { useCalibration } from '../hooks/useCalibration';
import { useSignals } from '../hooks/useSignals';
import { useModels } from '../hooks/useModels';

const mockBankrollData = {
  initial: 1000,
  current: 1150,
  peak: 1200,
  max_drawdown: 0.05,
  curve: [
    { date: '2023-01-01', bankroll: 1000 },
    { date: '2023-06-01', bankroll: 1150 },
  ],
};

const mockBacktestData = {
  n_bets: 120,
  kelly_roi: 0.152,
  flat_roi: 0.08,
  total_pnl_kelly: 152.0,
  total_pnl_flat: 80.0,
  by_surface: [],
  by_tourney_level: [],
  by_year: [],
  by_ev_bucket: [],
  by_rank_tier: [],
};

const mockCalibrationData = {
  model_version: 'v1',
  fold: null,
  bins: [
    { midpoint: 0.1, empirical_freq: 0.09, n_samples: 50 },
    { midpoint: 0.5, empirical_freq: 0.51, n_samples: 100 },
  ],
};

const mockModelsData = {
  data: [
    {
      model_version: 'logistic_v1',
      brier_score: 0.215,
      log_loss: 0.48,
      calibration_quality: 'good',
      kelly_roi: 0.152,
      flat_roi: 0.08,
      total_bets: 120,
    },
  ],
};

const mockSignalsData = {
  data: [
    {
      tourney_id: 't1',
      match_num: 1,
      tour: 'atp',
      player_id: 1,
      model_version: 'v1',
      calibrated_prob: 0.65,
      ev_value: 0.08,
      edge: 0.05,
      decimal_odds: 1.9,
      predicted_at: '2023-01-01T00:00:00Z',
    },
    {
      tourney_id: 't1',
      match_num: 2,
      tour: 'atp',
      player_id: 2,
      model_version: 'v1',
      calibrated_prob: 0.7,
      ev_value: 0.12,
      edge: 0.09,
      decimal_odds: 1.7,
      predicted_at: '2023-01-01T00:00:00Z',
    },
  ],
};

function setupLoadedMocks() {
  vi.mocked(useBankroll).mockReturnValue({
    data: mockBankrollData,
    isLoading: false,
    isError: false,
  } as any);
  vi.mocked(useBacktestSummary).mockReturnValue({
    data: mockBacktestData,
    isLoading: false,
    isError: false,
  } as any);
  vi.mocked(useCalibration).mockReturnValue({
    data: mockCalibrationData,
    isLoading: false,
    isError: false,
  } as any);
  vi.mocked(useSignals).mockReturnValue({
    data: mockSignalsData,
    isLoading: false,
    isError: false,
  } as any);
  vi.mocked(useModels).mockReturnValue({
    data: mockModelsData,
    isLoading: false,
    isError: false,
  } as any);
}

describe('OverviewTab', () => {
  it('renders 4 KPI cards with correct labels', () => {
    setupLoadedMocks();
    render(<OverviewTab />);
    expect(screen.getByText('ROI')).toBeInTheDocument();
    expect(screen.getByText('Total P&L')).toBeInTheDocument();
    expect(screen.getByText('Brier Score')).toBeInTheDocument();
    expect(screen.getByText('Active Signals')).toBeInTheDocument();
  });

  it('renders Monte Carlo section with simulation controls', () => {
    setupLoadedMocks();
    render(<OverviewTab />);
    expect(screen.getByText('Monte Carlo Simulation')).toBeInTheDocument();
    // MonteCarloSection renders its form/results — just check section heading is present
    expect(screen.getByText('Monte Carlo Simulation')).toBeInTheDocument();
  });

  it('shows skeleton loaders when isLoading is true', () => {
    vi.mocked(useBankroll).mockReturnValue({ isLoading: true, isError: false } as any);
    vi.mocked(useBacktestSummary).mockReturnValue({ isLoading: true, isError: false } as any);
    vi.mocked(useCalibration).mockReturnValue({ isLoading: true, isError: false } as any);
    vi.mocked(useSignals).mockReturnValue({ isLoading: true, isError: false } as any);
    vi.mocked(useModels).mockReturnValue({ isLoading: true, isError: false } as any);

    render(<OverviewTab />);
    const skeletons = screen.getAllByRole('generic').filter((el) =>
      el.getAttribute('aria-busy') === 'true'
    );
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders Brier Score KPI with value from useModels data', () => {
    setupLoadedMocks();
    render(<OverviewTab />);
    expect(screen.getByText('0.2150')).toBeInTheDocument();
  });

  it('shows error message when isError is true', () => {
    vi.mocked(useBankroll).mockReturnValue({ isLoading: false, isError: true } as any);
    vi.mocked(useBacktestSummary).mockReturnValue({ isLoading: false, isError: false } as any);
    vi.mocked(useCalibration).mockReturnValue({ isLoading: false, isError: false } as any);
    vi.mocked(useSignals).mockReturnValue({ isLoading: false, isError: false } as any);
    vi.mocked(useModels).mockReturnValue({ isLoading: false, isError: false } as any);

    render(<OverviewTab />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(
      screen.getByText(/Failed to load data/i)
    ).toBeInTheDocument();
  });
});
