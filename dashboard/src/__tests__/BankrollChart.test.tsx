import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { BankrollChart } from '../components/charts/BankrollChart';
import type { BankrollPoint } from '../api/types';

// Mock lightweight-charts
const mockSeries = {
  setData: vi.fn(),
};
const mockChart = {
  addSeries: vi.fn(() => mockSeries),
  subscribeClick: vi.fn(),
  remove: vi.fn(),
  applyOptions: vi.fn(),
};
vi.mock('lightweight-charts', () => ({
  createChart: vi.fn(() => mockChart),
  BaselineSeries: {},
  ColorType: { Solid: 'solid' },
}));

const sampleData: BankrollPoint[] = [
  { date: '2023-01-01', bankroll: 1000 },
  { date: '2023-01-15', bankroll: 1050 },
  { date: '2023-02-01', bankroll: 980 },
];

describe('BankrollChart', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders container div with role="img"', () => {
    render(<BankrollChart data={sampleData} initialBankroll={1000} />);
    expect(screen.getByRole('img')).toBeInTheDocument();
    expect(screen.getByRole('img')).toHaveAttribute(
      'aria-label',
      'Bankroll equity curve over time'
    );
  });

  it('calls createChart on mount with data', async () => {
    const { createChart } = await import('lightweight-charts');
    render(<BankrollChart data={sampleData} initialBankroll={1000} />);
    expect(createChart).toHaveBeenCalled();
  });

  it('shows empty state when data is empty', () => {
    render(<BankrollChart data={[]} initialBankroll={1000} />);
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByText(/Bankroll curve unavailable/i)).toBeInTheDocument();
  });
});
