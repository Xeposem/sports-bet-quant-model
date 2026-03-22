import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

// Mock hooks before import
vi.mock('@/hooks/useSimulation', () => ({
  useSimulationResult: vi.fn(),
  useRunSimulation: vi.fn(),
}));

import { MonteCarloSection } from '@/components/shared/MonteCarloSection';
import { useSimulationResult, useRunSimulation } from '@/hooks/useSimulation';

const mockUseSimulationResult = useSimulationResult as unknown as ReturnType<typeof vi.fn>;
const mockUseRunSimulation = useRunSimulation as unknown as ReturnType<typeof vi.fn>;

describe('MonteCarloSection', () => {
  it('shows empty state when no simulation results', () => {
    mockUseSimulationResult.mockReturnValue({ data: undefined, isLoading: false, isError: true });
    mockUseRunSimulation.mockReturnValue({ mutate: vi.fn(), isPending: false, data: undefined });
    render(<MonteCarloSection />);
    expect(screen.getByText('No simulation results')).toBeInTheDocument();
  });

  it('shows Run Simulation button', () => {
    mockUseSimulationResult.mockReturnValue({ data: undefined, isLoading: false, isError: true });
    mockUseRunSimulation.mockReturnValue({ mutate: vi.fn(), isPending: false, data: undefined });
    render(<MonteCarloSection />);
    expect(screen.getByRole('button', { name: /run simulation/i })).toBeInTheDocument();
  });

  it('shows KPI cards when results available', () => {
    mockUseSimulationResult.mockReturnValue({
      data: {
        p_ruin: 0.05,
        expected_terminal: 1500.0,
        sharpe_ratio: 1.2,
        paths: [],
        terminal_distribution: [],
        n_seasons: 1000,
        initial_bankroll: 1000,
      },
      isLoading: false,
      isError: false,
    });
    mockUseRunSimulation.mockReturnValue({ mutate: vi.fn(), isPending: false, data: undefined });
    render(<MonteCarloSection />);
    expect(screen.getByText(/5\.0%/)).toBeInTheDocument(); // P(ruin)
    expect(screen.getByText(/\$1,500/)).toBeInTheDocument(); // Expected terminal
    expect(screen.getByText(/1\.20/)).toBeInTheDocument(); // Sharpe
  });

  it('renders heading text', () => {
    mockUseSimulationResult.mockReturnValue({ data: undefined, isLoading: false, isError: true });
    mockUseRunSimulation.mockReturnValue({ mutate: vi.fn(), isPending: false, data: undefined });
    render(<MonteCarloSection />);
    expect(screen.getByText('Monte Carlo Simulation')).toBeInTheDocument();
  });
});
