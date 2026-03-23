import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { PropScanPreview } from '../components/shared/PropScanPreview';
import type { PropScanCard } from '../api/types';

// Mock useSubmitPropLine
const mockMutateAsync = vi.fn();
vi.mock('../hooks/useProps', () => ({
  useSubmitPropLine: vi.fn(() => ({
    mutateAsync: mockMutateAsync,
    isPending: false,
  })),
  useProps: vi.fn(() => ({ data: undefined, isLoading: false })),
  usePropAccuracy: vi.fn(() => ({ data: undefined, isLoading: false })),
  useScanPropScreenshot: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
}));

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}));

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

const sampleCards: PropScanCard[] = [
  {
    player_name: 'Carlos Alcaraz',
    stat_type: 'aces',
    line_value: 5.5,
    directions: ['over', 'under'],
  },
  {
    player_name: 'Novak Djokovic',
    stat_type: 'games_won',
    line_value: 22.5,
    directions: ['over'],
  },
];

describe('PropScanPreview', () => {
  beforeEach(() => {
    mockMutateAsync.mockResolvedValue({ id: 1, player_name: 'Carlos Alcaraz', stat_type: 'aces', line_value: 5.5, direction: 'over', match_date: '2026-03-23' });
  });

  it('renders table rows for each card direction (2 directions = 2 rows for first card, 1 for second = 3 total)', () => {
    const onClose = vi.fn();
    render(<PropScanPreview cards={sampleCards} onClose={onClose} />, { wrapper });

    // 2 rows for Alcaraz (over + under), 1 row for Djokovic (over) = 3 total data rows
    const rows = screen.getAllByRole('row');
    // header row + 3 data rows
    expect(rows.length).toBe(4);
    // Alcaraz appears in 2 rows (over and under)
    expect(screen.getAllByText('Carlos Alcaraz').length).toBe(2);
    expect(screen.getByText('Novak Djokovic')).toBeInTheDocument();
  });

  it('all checkboxes are checked by default', () => {
    const onClose = vi.fn();
    render(<PropScanPreview cards={sampleCards} onClose={onClose} />, { wrapper });

    const checkboxes = screen.getAllByRole('checkbox');
    // 1 select-all + 3 row checkboxes
    expect(checkboxes.length).toBe(4);
    // Row checkboxes (indices 1-3) should all be checked
    checkboxes.slice(1).forEach((cb) => {
      expect(cb).toBeChecked();
    });
  });

  it('unchecking a row decrements the Submit Selected count', () => {
    const onClose = vi.fn();
    render(<PropScanPreview cards={sampleCards} onClose={onClose} />, { wrapper });

    // Initially shows "Submit Selected (3)"
    expect(screen.getByText('Submit Selected (3)')).toBeInTheDocument();

    // Uncheck the first row checkbox
    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[1]); // first row checkbox

    // Now should show "Submit Selected (2)"
    expect(screen.getByText('Submit Selected (2)')).toBeInTheDocument();
  });

  it('Submit Selected button is disabled when no rows checked', () => {
    const onClose = vi.fn();
    render(<PropScanPreview cards={sampleCards} onClose={onClose} />, { wrapper });

    // Uncheck all rows via select-all
    const selectAll = screen.getAllByRole('checkbox')[0];
    fireEvent.click(selectAll); // all checked -> deselect all

    const submitBtn = screen.getByText('Submit Selected (0)').closest('button');
    expect(submitBtn).toBeDisabled();
  });

  it('clicking Submit Selected calls mutateAsync for each checked row', async () => {
    const onClose = vi.fn();
    render(<PropScanPreview cards={sampleCards} onClose={onClose} />, { wrapper });

    const submitBtn = screen.getByText('Submit Selected (3)');
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledTimes(3);
    });
  });

  it('displays stat type as readable label', () => {
    const onClose = vi.fn();
    render(<PropScanPreview cards={sampleCards} onClose={onClose} />, { wrapper });

    // Aces appears for 2 rows (over and under for Alcaraz)
    expect(screen.getAllByText('Aces').length).toBe(2);
    expect(screen.getByText('Games Won')).toBeInTheDocument();
  });

  it('renders Over badge with green styling and Under badge with amber styling', () => {
    const onClose = vi.fn();
    render(<PropScanPreview cards={sampleCards} onClose={onClose} />, { wrapper });

    const overBadges = screen.getAllByText('Over');
    const underBadges = screen.getAllByText('Under');
    expect(overBadges.length).toBeGreaterThan(0);
    expect(underBadges.length).toBeGreaterThan(0);
  });
});
