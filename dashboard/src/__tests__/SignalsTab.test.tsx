import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { SignalsTab } from '../tabs/SignalsTab';

vi.mock('../hooks/useSignals', () => ({
  useSignals: vi.fn(() => ({
    isLoading: false,
    isError: false,
    data: {
      data: [
        {
          tourney_id: '2024-580',
          match_num: 1,
          tour: 'atp',
          player_id: 104925,
          model_version: 'logistic_v1',
          calibrated_prob: 0.68,
          ev_value: 7.2,
          edge: 0.12,
          decimal_odds: 1.85,
          predicted_at: '2024-06-15',
        },
        {
          tourney_id: '2024-580',
          match_num: 2,
          tour: 'atp',
          player_id: 104745,
          model_version: 'logistic_v1',
          calibrated_prob: 0.55,
          ev_value: 3.1,
          edge: 0.06,
          decimal_odds: 2.10,
          predicted_at: '2024-06-14',
        },
      ],
    },
  })),
}));

describe('SignalsTab', () => {
  it('renders signal cards with EV text', () => {
    render(<SignalsTab />);
    // Should render EV values for both signals
    const evElements = screen.getAllByText(/EV/i);
    expect(evElements.length).toBeGreaterThan(0);
  });

  it('renders filter bar with surface and min EV options', () => {
    render(<SignalsTab />);
    expect(screen.getByText(/surface/i)).toBeInTheDocument();
    expect(screen.getByText(/min ev/i)).toBeInTheDocument();
  });

  it('shows empty state when signals data is empty array', async () => {
    const { useSignals } = await import('../hooks/useSignals');
    vi.mocked(useSignals).mockReturnValueOnce({
      isLoading: false,
      isError: false,
      data: { data: [] },
    } as unknown as ReturnType<typeof useSignals>);
    render(<SignalsTab />);
    expect(screen.getByText('No active signals')).toBeInTheDocument();
  });

  it('shows skeleton loaders when isLoading=true', async () => {
    const { useSignals } = await import('../hooks/useSignals');
    vi.mocked(useSignals).mockReturnValueOnce({
      isLoading: true,
      isError: false,
      data: undefined,
    } as unknown as ReturnType<typeof useSignals>);
    render(<SignalsTab />);
    const skeletons = screen.getAllByLabelText(/loading signal data/i);
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('signal card has role="article"', () => {
    render(<SignalsTab />);
    const articles = screen.getAllByRole('article');
    expect(articles.length).toBeGreaterThan(0);
  });
});
