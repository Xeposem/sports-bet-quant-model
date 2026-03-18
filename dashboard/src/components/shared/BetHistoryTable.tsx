import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import type { BacktestBetRow } from '@/api/types';

interface BetHistoryTableProps {
  data: BacktestBetRow[];
  total: number;
  offset: number;
  limit: number;
  onPageChange: (offset: number) => void;
  isLoading: boolean;
}

function formatCurrency(val: number): string {
  const sign = val >= 0 ? '+' : '';
  return `${sign}${val.toFixed(2)}`;
}

export function BetHistoryTable({
  data,
  total,
  offset,
  limit,
  onPageChange,
  isLoading,
}: BetHistoryTableProps) {
  if (isLoading) {
    return (
      <div aria-busy="true" aria-label="Loading bet history table">
        <div className="space-y-2 p-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton
              key={i}
              className={`h-10 w-full ${i % 2 === 0 ? 'bg-slate-700' : 'bg-slate-800'}`}
            />
          ))}
        </div>
      </div>
    );
  }

  if (total === 0 && !isLoading) {
    return (
      <div className="p-8 text-center">
        <p className="text-slate-100 font-semibold text-lg">No backtest results</p>
        <p className="text-slate-500 mt-2">
          Run a backtest to see ROI breakdowns and bet history. Use the API or CLI to trigger a run.
        </p>
      </div>
    );
  }

  const showingStart = offset + 1;
  const showingEnd = Math.min(offset + limit, total);

  return (
    <div>
      <Table>
        <TableHeader className="bg-slate-800">
          <TableRow>
            <TableHead className="text-xs uppercase tracking-wider text-slate-400">Date</TableHead>
            <TableHead className="text-xs uppercase tracking-wider text-slate-400">Surface</TableHead>
            <TableHead className="text-xs uppercase tracking-wider text-slate-400">Tournament</TableHead>
            <TableHead className="text-xs uppercase tracking-wider text-slate-400">Model</TableHead>
            <TableHead className="text-xs uppercase tracking-wider text-slate-400">EV%</TableHead>
            <TableHead className="text-xs uppercase tracking-wider text-slate-400">Kelly Bet</TableHead>
            <TableHead className="text-xs uppercase tracking-wider text-slate-400">P&amp;L</TableHead>
            <TableHead className="text-xs uppercase tracking-wider text-slate-400">Bankroll</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((row, i) => (
            <TableRow
              key={row.id}
              className={i % 2 === 0 ? 'bg-slate-800 hover:bg-slate-700' : 'bg-slate-900 hover:bg-slate-700'}
            >
              <TableCell className="text-slate-100 text-sm">{row.tourney_date}</TableCell>
              <TableCell className="text-slate-100 text-sm">{row.surface ?? 'N/A'}</TableCell>
              <TableCell className="text-slate-100 text-sm">{row.tourney_id}</TableCell>
              <TableCell className="text-slate-100 text-sm">{row.model_version}</TableCell>
              <TableCell
                className={`text-sm font-medium ${
                  row.ev > 0 ? 'text-green-500' : 'text-red-500'
                }`}
              >
                {row.ev.toFixed(2)}%
              </TableCell>
              <TableCell className="text-slate-100 text-sm">{row.kelly_bet.toFixed(4)}</TableCell>
              <TableCell
                className={`text-sm font-medium ${
                  row.pnl_kelly >= 0 ? 'text-green-500' : 'text-red-500'
                }`}
              >
                {formatCurrency(row.pnl_kelly)}
              </TableCell>
              <TableCell className="text-slate-100 text-sm">
                {row.bankroll_after.toFixed(2)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <div className="flex items-center justify-between px-4 py-3 bg-slate-800 border-t border-slate-700">
        <span className="text-slate-400 text-sm">
          Showing {showingStart}–{showingEnd} of {total} bets
        </span>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(offset - limit)}
            disabled={offset === 0}
            className="border-slate-700 bg-slate-800 text-slate-100 hover:bg-slate-700"
          >
            Prev
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(offset + limit)}
            disabled={offset + limit >= total}
            className="border-slate-700 bg-slate-800 text-slate-100 hover:bg-slate-700"
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
