import { useState, useRef, useEffect } from 'react';
import { createChart, LineSeries, ColorType } from 'lightweight-charts';
import { toast } from 'sonner';
import { KpiCard } from '../components/shared/KpiCard';
import { EmptyState } from '../components/shared/EmptyState';
import {
  usePaperSession,
  usePaperBets,
  usePaperEquity,
  useStartSession,
  useResetSession,
  useResolveBet,
} from '../hooks/usePaperTrading';
import type { PaperBet, PaperEquityPoint } from '../api/types';

function formatCurrency(val: number): string {
  return `$${val.toFixed(2)}`;
}

interface PaperEquityChartProps {
  curve: PaperEquityPoint[];
  totalPnl: number;
}

function PaperEquityChart({ curve, totalPnl }: PaperEquityChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || curve.length === 0) return;

    const lineColor = totalPnl >= 0 ? '#22c55e' : '#ef4444';

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 300,
      layout: {
        background: { type: ColorType.Solid, color: '#0f172a' },
        textColor: '#64748b',
      },
      grid: {
        vertLines: { color: '#1e293b' },
        horzLines: { color: '#1e293b' },
      },
      crosshair: {
        horzLine: { color: '#64748b' },
        vertLine: { color: '#64748b' },
      },
      timeScale: { borderColor: '#334155' },
      rightPriceScale: { borderColor: '#334155' },
    });

    const series = chart.addSeries(LineSeries, {
      color: lineColor,
      lineWidth: 2,
    });

    series.setData(curve.map((p) => ({ time: p.date, value: p.bankroll })));

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [curve, totalPnl]);

  if (curve.length === 0) {
    return (
      <EmptyState
        heading="Equity curve unavailable"
        body="Place and resolve bets to see the equity curve."
      />
    );
  }

  return (
    <div
      ref={containerRef}
      role="img"
      aria-label="Paper trading equity curve"
      style={{ height: 300, width: '100%' }}
    />
  );
}

interface BetRowProps {
  bet: PaperBet;
  onResolve: (betId: number, outcome: number) => void;
  isResolving: boolean;
}

function BetRow({ bet, onResolve, isResolving }: BetRowProps) {
  const isPending = bet.outcome === null;
  const pnlColor = bet.pnl != null && bet.pnl >= 0 ? 'text-green-500' : 'text-red-500';

  return (
    <tr className="border-b border-slate-700 hover:bg-slate-700">
      <td className="px-3 py-2 text-sm text-slate-300">{bet.placed_at.split('T')[0]}</td>
      <td className="px-3 py-2 text-sm text-slate-300">
        {bet.tourney_id} #{bet.match_num}
      </td>
      <td className="px-3 py-2 text-sm text-slate-300">{formatCurrency(bet.kelly_stake)}</td>
      <td className="px-3 py-2 text-sm">
        {isPending ? (
          <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30">
            Pending
          </span>
        ) : bet.outcome === 1 ? (
          <span className="text-xs px-2 py-0.5 rounded-full bg-green-500/20 text-green-400 border border-green-500/30">
            Win
          </span>
        ) : (
          <span className="text-xs px-2 py-0.5 rounded-full bg-red-500/20 text-red-400 border border-red-500/30">
            Loss
          </span>
        )}
      </td>
      <td className={`px-3 py-2 text-sm font-medium ${isPending ? 'text-slate-500' : pnlColor}`}>
        {bet.pnl != null ? (bet.pnl >= 0 ? `+${bet.pnl.toFixed(2)}` : bet.pnl.toFixed(2)) : '--'}
      </td>
      <td className="px-3 py-2 text-sm text-slate-300">
        {bet.bankroll_after != null ? formatCurrency(bet.bankroll_after) : '--'}
      </td>
      {isPending && (
        <td className="px-3 py-2">
          <div className="flex gap-1">
            <button
              onClick={() => onResolve(bet.id, 1)}
              disabled={isResolving}
              className="text-xs px-2 py-1 rounded bg-green-500/20 text-green-400 hover:bg-green-500/40 disabled:opacity-50 border border-green-500/30"
            >
              Win
            </button>
            <button
              onClick={() => onResolve(bet.id, 0)}
              disabled={isResolving}
              className="text-xs px-2 py-1 rounded bg-red-500/20 text-red-400 hover:bg-red-500/40 disabled:opacity-50 border border-red-500/30"
            >
              Loss
            </button>
          </div>
        </td>
      )}
      {!isPending && <td className="px-3 py-2" />}
    </tr>
  );
}

export function PaperTradingTab() {
  const [bankrollInput, setBankrollInput] = useState<number>(1000);
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 20;

  const sessionQuery = usePaperSession();
  const betsQuery = usePaperBets();
  const equityQuery = usePaperEquity();
  const startSession = useStartSession();
  const resetSession = useResetSession();
  const resolveBet = useResolveBet();

  const session = sessionQuery.data;
  const hasSession = !!session && session.active === 1;
  const bets = betsQuery.data?.data ?? [];
  const hasBets = bets.length > 0;
  const curve = equityQuery.data?.curve ?? [];

  const handleStart = () => {
    startSession.mutate(
      { initial_bankroll: bankrollInput, kelly_fraction: 0.25, ev_threshold: 2.0 },
      {
        onSuccess: () => toast('Paper trading session started'),
        onError: () => toast.error('Failed to start session'),
      }
    );
  };

  const handleReset = () => {
    const confirmed = window.confirm(
      'Reset paper trading session? This will delete all bet history and reset your bankroll to $0. This cannot be undone.'
    );
    if (!confirmed) return;
    resetSession.mutate(undefined, {
      onSuccess: () => toast('Session reset'),
      onError: () => toast.error('Failed to reset session'),
    });
  };

  const handleResolve = (betId: number, outcome: number) => {
    resolveBet.mutate(
      { betId, outcome },
      {
        onSuccess: () => toast(outcome === 1 ? 'Bet resolved as Win' : 'Bet resolved as Loss'),
        onError: () => toast.error('Failed to resolve bet'),
      }
    );
  };

  const sortedBets = [...bets].sort(
    (a, b) => new Date(b.placed_at).getTime() - new Date(a.placed_at).getTime()
  );
  const pageCount = Math.ceil(sortedBets.length / PAGE_SIZE);
  const pageBets = sortedBets.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  // State A: No active session
  if (!hasSession) {
    return (
      <div className="p-6">
        <h2 className="text-xl font-semibold text-slate-100">Paper Trading</h2>
        <EmptyState
          heading="No active session"
          body="Start a paper trading session to track bets and P&L. Set your starting bankroll and click Start Session."
        />
        <div className="mt-4 flex items-center gap-4">
          <label className="text-sm text-slate-400">Starting Bankroll ($)</label>
          <input
            type="number"
            min={100}
            value={bankrollInput}
            onChange={(e) => setBankrollInput(parseFloat(e.target.value))}
            className="bg-slate-800 border border-slate-700 text-slate-100 rounded px-3 py-2 w-32"
            aria-label="Starting bankroll amount"
          />
          <button
            onClick={handleStart}
            disabled={startSession.isPending}
            className="bg-green-500 hover:bg-green-600 text-white font-semibold px-4 py-2 rounded disabled:opacity-50"
          >
            Start Session
          </button>
        </div>
      </div>
    );
  }

  // State B or C: Active session
  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold text-slate-100">Paper Trading</h2>
        <button
          onClick={handleReset}
          className="text-sm text-red-500 hover:text-red-400"
        >
          Reset Session
        </button>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <KpiCard label="BANKROLL" value={formatCurrency(session.current_bankroll)} />
        <KpiCard
          label="P&L"
          value={
            session.total_pnl >= 0
              ? `+${formatCurrency(session.total_pnl).slice(1)}`
              : `-$${Math.abs(session.total_pnl).toFixed(2)}`
          }
          trend={session.total_pnl >= 0 ? 'positive' : 'negative'}
        />
        <KpiCard
          label="WIN RATE"
          value={session.win_rate !== null ? `${(session.win_rate * 100).toFixed(1)}%` : 'N/A'}
        />
        <KpiCard label="BETS" value={String(session.total_bets)} />
      </div>

      {/* State B: No bets yet */}
      {!hasBets ? (
        <EmptyState
          heading="No bets placed yet"
          body="Place bets from the Signals tab. Kelly-sized stakes will appear here."
        />
      ) : (
        <>
          {/* Equity Curve */}
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">
              Equity Curve
            </h3>
            <div className="h-[300px]">
              <PaperEquityChart curve={curve} totalPnl={session.total_pnl} />
            </div>
          </div>

          {/* Bet History Table */}
          <div className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-700">
              <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
                Bet History
              </h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-900">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs uppercase tracking-wider text-slate-500">Date</th>
                    <th className="px-3 py-2 text-left text-xs uppercase tracking-wider text-slate-500">Match</th>
                    <th className="px-3 py-2 text-left text-xs uppercase tracking-wider text-slate-500">Stake</th>
                    <th className="px-3 py-2 text-left text-xs uppercase tracking-wider text-slate-500">Result</th>
                    <th className="px-3 py-2 text-left text-xs uppercase tracking-wider text-slate-500">P&amp;L</th>
                    <th className="px-3 py-2 text-left text-xs uppercase tracking-wider text-slate-500">Bankroll After</th>
                    <th className="px-3 py-2 text-left text-xs uppercase tracking-wider text-slate-500">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {pageBets.map((bet) => (
                    <BetRow
                      key={bet.id}
                      bet={bet}
                      onResolve={handleResolve}
                      isResolving={resolveBet.isPending}
                    />
                  ))}
                </tbody>
              </table>
            </div>
            {pageCount > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-slate-700">
                <span className="text-slate-400 text-sm">
                  Page {page + 1} of {pageCount}
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                    disabled={page === 0}
                    className="text-xs px-3 py-1 rounded border border-slate-600 text-slate-300 hover:bg-slate-700 disabled:opacity-50"
                  >
                    Prev
                  </button>
                  <button
                    onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
                    disabled={page >= pageCount - 1}
                    className="text-xs px-3 py-1 rounded border border-slate-600 text-slate-300 hover:bg-slate-700 disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
