import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { SignalCard } from '@/components/shared/SignalCard';
import type { SignalRecord } from '@/api/types';

const mockSignal: SignalRecord = {
  id: 1,
  tourney_id: '2024-540',
  match_num: 42,
  tour: 'ATP',
  player_id: 104745,
  model_version: 'ensemble_v1',
  status: 'new',
  calibrated_prob: 0.65,
  ev_value: 8.2,
  edge: 0.12,
  decimal_odds: 1.85,
  kelly_stake: 42.50,
  confidence: 0.75,
  sharpe: 1.3,
  predicted_at: '2024-01-15',
  created_at: '2024-01-15',
};

describe('SignalCard', () => {
  it('renders EV value', () => {
    render(<SignalCard signal={mockSignal} />);
    expect(screen.getByText('+8.2% EV')).toBeInTheDocument();
  });

  it('renders status badge', () => {
    render(<SignalCard signal={mockSignal} />);
    expect(screen.getByText('New')).toBeInTheDocument();
  });

  it('renders confidence field', () => {
    render(<SignalCard signal={mockSignal} />);
    expect(screen.getByText(/75%/)).toBeInTheDocument();
  });

  it('renders Sharpe field', () => {
    render(<SignalCard signal={mockSignal} />);
    expect(screen.getByText(/1\.30/)).toBeInTheDocument();
  });

  it('renders stake dollars', () => {
    render(<SignalCard signal={mockSignal} />);
    expect(screen.getByText(/\$42\.50/)).toBeInTheDocument();
  });

  it('renders Place Bet button', () => {
    render(<SignalCard signal={mockSignal} />);
    expect(screen.getByRole('button', { name: /place bet/i })).toBeInTheDocument();
  });

  it('disables Place Bet when no paper session', () => {
    render(<SignalCard signal={mockSignal} paperSessionActive={false} />);
    expect(screen.getByRole('button', { name: /place bet/i })).toBeDisabled();
  });

  it('renders Mark Acted On button for new signals', () => {
    render(<SignalCard signal={mockSignal} />);
    expect(screen.getByRole('button', { name: /mark acted on/i })).toBeInTheDocument();
  });

  it('hides Mark Acted On for expired signals', () => {
    render(<SignalCard signal={{ ...mockSignal, status: 'expired' }} />);
    expect(screen.queryByRole('button', { name: /mark acted on/i })).not.toBeInTheDocument();
  });

  it('applies dimmed class when dimmed prop is true', () => {
    const { container } = render(<SignalCard signal={mockSignal} dimmed={true} />);
    expect(container.firstChild).toHaveClass('opacity-50');
  });
});
