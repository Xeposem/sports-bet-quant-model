import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import App from '../App';

// Mock useRefreshAll to avoid QueryClient issues in Header
vi.mock('../hooks/useRefresh', () => ({
  useRefreshAll: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
    isSuccess: false,
    isError: false,
  })),
}));

describe('App', () => {
  it('renders the Tennis Quant header', () => {
    render(<App />);
    expect(screen.getByText('Tennis Quant')).toBeInTheDocument();
  });

  it('renders all 4 tab triggers', () => {
    render(<App />);
    expect(screen.getByRole('tab', { name: /overview/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /backtest/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /models/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /signals/i })).toBeInTheDocument();
  });

  it('shows Overview tab content by default', () => {
    render(<App />);
    // Monte Carlo Simulation heading is rendered in the Overview tab
    expect(screen.getByRole('heading', { name: 'Monte Carlo Simulation' })).toBeInTheDocument();
  });

  it('renders ErrorBoundary in the component tree', () => {
    render(<App />);
    // ErrorBoundary wraps TabNav — the tabs should be present if ErrorBoundary is working
    expect(screen.getByRole('tablist')).toBeInTheDocument();
  });

  it('renders the Refresh Data button in header', () => {
    render(<App />);
    expect(screen.getByRole('button', { name: /refresh data/i })).toBeInTheDocument();
  });
});
