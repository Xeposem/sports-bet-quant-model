import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ManualEntryModal } from '../components/modals/ManualEntryModal';

vi.mock('../hooks/useManualEntry', () => ({
  useOddsList: vi.fn(),
  useSubmitOdds: vi.fn(),
  useDeleteOdds: vi.fn(),
  usePropLinesList: vi.fn(),
  useDeletePropLine: vi.fn(),
}));

vi.mock('../hooks/useProps', () => ({
  useSubmitPropLine: vi.fn(),
  useProps: vi.fn(),
  usePropAccuracy: vi.fn(),
}));

import {
  useOddsList,
  useSubmitOdds,
  useDeleteOdds,
  usePropLinesList,
  useDeletePropLine,
} from '../hooks/useManualEntry';
import { useSubmitPropLine } from '../hooks/useProps';

const defaultMutate = vi.fn();
const defaultMutation = {
  mutate: defaultMutate,
  isPending: false,
  isError: false,
  isSuccess: false,
};

function setupDefaultMocks() {
  vi.mocked(useOddsList).mockReturnValue({
    data: { data: [] },
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof useOddsList>);

  vi.mocked(usePropLinesList).mockReturnValue({
    data: { data: [] },
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof usePropLinesList>);

  vi.mocked(useSubmitOdds).mockReturnValue(
    defaultMutation as unknown as ReturnType<typeof useSubmitOdds>
  );
  vi.mocked(useDeleteOdds).mockReturnValue(
    defaultMutation as unknown as ReturnType<typeof useDeleteOdds>
  );
  vi.mocked(useSubmitPropLine).mockReturnValue(
    defaultMutation as unknown as ReturnType<typeof useSubmitPropLine>
  );
  vi.mocked(useDeletePropLine).mockReturnValue(
    defaultMutation as unknown as ReturnType<typeof useDeletePropLine>
  );
}

describe('ManualEntryModal', () => {
  beforeEach(() => {
    setupDefaultMocks();
  });

  it('renders "Enter Data" dialog title when open', () => {
    render(<ManualEntryModal open={true} onOpenChange={vi.fn()} />);
    expect(screen.getByText('Enter Data')).toBeInTheDocument();
  });

  it('shows "Match Odds" and "Prop Line" toggle buttons', () => {
    render(<ManualEntryModal open={true} onOpenChange={vi.fn()} />);
    expect(screen.getByText('Match Odds')).toBeInTheDocument();
    expect(screen.getByText('Prop Line')).toBeInTheDocument();
  });

  it('default form is Match Odds with Player A input visible', () => {
    render(<ManualEntryModal open={true} onOpenChange={vi.fn()} />);
    expect(screen.getByPlaceholderText('Player A name')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Player B name')).toBeInTheDocument();
  });

  it('switching to Prop Line shows Player Name and Stat Type fields', async () => {
    const user = userEvent.setup();
    render(<ManualEntryModal open={true} onOpenChange={vi.fn()} />);
    await user.click(screen.getByText('Prop Line'));
    expect(screen.getByPlaceholderText('Player name')).toBeInTheDocument();
    // Stat type select is present
    expect(screen.getByDisplayValue('Aces')).toBeInTheDocument();
  });

  it('shows "Save Entry" submit button', () => {
    render(<ManualEntryModal open={true} onOpenChange={vi.fn()} />);
    expect(screen.getByText('Save Entry')).toBeInTheDocument();
  });

  it('shows "No entries yet" when CRUD tables are empty', () => {
    render(<ManualEntryModal open={true} onOpenChange={vi.fn()} />);
    const emptyMessages = screen.getAllByText('No entries yet');
    expect(emptyMessages.length).toBeGreaterThan(0);
  });

  it('shows odds entries in CRUD table when data exists', () => {
    vi.mocked(useOddsList).mockReturnValue({
      data: {
        data: [
          {
            tourney_id: '2024-580',
            match_num: 1,
            tour: 'atp',
            bookmaker: 'pinnacle',
            decimal_odds_a: 1.85,
            decimal_odds_b: 2.10,
            source: 'manual',
            imported_at: '2024-06-15T00:00:00Z',
          },
          {
            tourney_id: '2024-580',
            match_num: 2,
            tour: 'atp',
            bookmaker: 'pinnacle',
            decimal_odds_a: 1.72,
            decimal_odds_b: 2.35,
            source: 'manual',
            imported_at: '2024-06-16T00:00:00Z',
          },
        ],
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useOddsList>);

    render(<ManualEntryModal open={true} onOpenChange={vi.fn()} />);
    expect(screen.getByText('1.85')).toBeInTheDocument();
    expect(screen.getByText('1.72')).toBeInTheDocument();
  });

  it('shows Delete buttons on CRUD table rows when data exists', () => {
    vi.mocked(useOddsList).mockReturnValue({
      data: {
        data: [
          {
            tourney_id: '2024-580',
            match_num: 1,
            tour: 'atp',
            bookmaker: 'pinnacle',
            decimal_odds_a: 1.85,
            decimal_odds_b: 2.10,
            source: 'manual',
            imported_at: '2024-06-15T00:00:00Z',
          },
        ],
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useOddsList>);

    render(<ManualEntryModal open={true} onOpenChange={vi.fn()} />);
    const deleteButtons = screen.getAllByText('Delete');
    expect(deleteButtons.length).toBeGreaterThan(0);
  });

  it('does not render dialog when open=false', () => {
    render(<ManualEntryModal open={false} onOpenChange={vi.fn()} />);
    expect(screen.queryByText('Enter Data')).not.toBeInTheDocument();
  });
});
