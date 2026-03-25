import { useState } from 'react';
import { useSignals, useUpdateSignalStatus } from '../hooks/useSignals';
import { usePlacePaperBet, usePaperSession } from '../hooks/usePaperTrading';
import { useRefreshAll } from '../hooks/useRefresh';
import { SignalCard } from '../components/shared/SignalCard';
import { EmptyState } from '../components/shared/EmptyState';
import { SkeletonCard } from '../components/shared/SkeletonCard';
import { FilterBar } from '../components/shared/FilterBar';
import { toast } from 'sonner';
import type { SignalRecord } from '../api/types';

type SortBy = 'ev' | 'date';

export function SignalsTab() {
  const [filterParams, setFilterParams] = useState<{ surface: string; min_ev: number }>({
    surface: '',
    min_ev: 0,
  });
  const [sortBy, setSortBy] = useState<SortBy>('ev');
  const [threshold, setThreshold] = useState<number>(() => {
    const stored = localStorage.getItem('ev_threshold');
    return stored ? parseFloat(stored) : 0;
  });
  const [dimMode, setDimMode] = useState<boolean>(true);
  const [clvThreshold, setClvThreshold] = useState<number>(() => {
    const stored = localStorage.getItem('clv_threshold_signals');
    return stored ? parseFloat(stored) : 0.03;
  });
  const handleClvChange = (val: number) => {
    setClvThreshold(val);
    localStorage.setItem('clv_threshold_signals', String(val));
  };

  const signals = useSignals({
    surface: filterParams.surface || undefined,
    min_ev: filterParams.min_ev > 0 ? filterParams.min_ev : undefined,
  });

  const refresh = useRefreshAll();
  const updateStatus = useUpdateSignalStatus();
  const placeBet = usePlacePaperBet();
  const paperSession = usePaperSession();

  const paperSessionActive = !!(paperSession.data && paperSession.data.active === 1);

  const handleRefresh = () => {
    refresh.mutate(undefined, {
      onError: () => {
        toast.error('Refresh failed — check the API server logs for details.');
      },
    });
  };

  const handleMarkActedOn = (signalId: number) => {
    updateStatus.mutate(
      { signalId, status: 'acted-on' },
      {
        onSuccess: () => toast('Signal marked as acted on'),
        onError: () => toast.error('Failed to update signal status'),
      }
    );
  };

  const handlePlaceBet = (signalId: number, matchLabel: string, stake?: number | null) => {
    placeBet.mutate(
      { signal_id: signalId },
      {
        onSuccess: () =>
          toast(`Bet placed -- ${stake != null ? `$${stake.toFixed(2)}` : ''} on match ${matchLabel}`),
        onError: () => toast.error('Failed to place bet — check that a paper session is active'),
      }
    );
  };

  const handleThresholdChange = (val: number) => {
    setThreshold(val);
    localStorage.setItem('ev_threshold', String(val));
  };

  const filters = [
    {
      key: 'surface',
      label: 'Surface',
      options: ['Hard', 'Clay', 'Grass'],
      value: filterParams.surface,
      onChange: (val: string) => setFilterParams((p) => ({ ...p, surface: val })),
    },
    {
      key: 'min_ev',
      label: 'Min EV',
      options: ['1%', '2%', '3%', '5%', '10%'],
      value: filterParams.min_ev > 0 ? `${filterParams.min_ev}%` : '',
      onChange: (val: string) => {
        const num = val ? parseInt(val, 10) : 0;
        setFilterParams((p) => ({ ...p, min_ev: isNaN(num) ? 0 : num }));
      },
    },
    {
      key: 'sort',
      label: 'Sort',
      options: ['Highest EV', 'Most Recent'],
      value: sortBy === 'ev' ? 'Highest EV' : 'Most Recent',
      onChange: (val: string) => setSortBy(val === 'Most Recent' ? 'date' : 'ev'),
    },
  ];

  if (signals.isError) {
    return (
      <div className="p-6" role="alert">
        <p className="text-red-500">
          Failed to load data. Check that the API server is running on port 8000.
        </p>
      </div>
    );
  }

  const sortedSignals = (): SignalRecord[] => {
    if (!signals.data?.data) return [];
    const data = [...signals.data.data];
    if (sortBy === 'ev') {
      return data.sort((a, b) => (b.ev_value ?? -Infinity) - (a.ev_value ?? -Infinity));
    }
    return data.sort(
      (a, b) =>
        new Date(b.predicted_at ?? b.created_at).getTime() -
        new Date(a.predicted_at ?? a.created_at).getTime()
    );
  };

  const allSignals = sortedSignals();

  return (
    <div>
      <FilterBar filters={filters} />
      {/* EV Threshold Slider */}
      <div className="px-6 pt-4 pb-2 flex items-center gap-4">
        <span className="text-sm text-slate-400 whitespace-nowrap">Min EV: {threshold.toFixed(1)}%</span>
        <input
          type="range"
          min={0}
          max={20}
          step={0.1}
          value={threshold}
          onChange={(e) => handleThresholdChange(parseFloat(e.target.value))}
          className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-green-500"
          aria-label="EV threshold slider"
        />
        <button
          onClick={() => setDimMode((d) => !d)}
          className="text-xs px-2 py-1 rounded border border-slate-600 text-slate-400 hover:bg-slate-700 whitespace-nowrap"
        >
          {dimMode ? 'Dim' : 'Hide'}
        </button>
      </div>
      {/* CLV Threshold Slider */}
      <div className="px-6 pt-2 pb-2 flex items-center gap-4">
        <span className="text-sm text-slate-400 whitespace-nowrap">CLV: {clvThreshold.toFixed(2)}</span>
        <input
          type="range"
          min={0}
          max={0.15}
          step={0.01}
          value={clvThreshold}
          onChange={(e) => handleClvChange(parseFloat(e.target.value))}
          className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-cyan-500"
          aria-label="CLV threshold"
        />
      </div>
      <div className="p-6">
        {signals.isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <SkeletonCard key={i} variant="signal" />
            ))}
          </div>
        ) : allSignals.length === 0 ? (
          <EmptyState
            heading="No active signals"
            body="No bets currently exceed the EV threshold. Click Refresh Data to fetch the latest predictions."
            action={{ label: 'Refresh Data', onClick: handleRefresh }}
          />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {allSignals
              .filter((signal) => {
                const belowThreshold = (signal.ev_value ?? 0) < threshold;
                if (belowThreshold && !dimMode) return false;
                return true;
              })
              .map((signal, idx) => {
                const belowThreshold = (signal.ev_value ?? 0) < threshold;
                return (
                  <SignalCard
                    key={`${signal.id}-${idx}`}
                    signal={signal}
                    dimmed={belowThreshold && dimMode}
                    paperSessionActive={paperSessionActive}
                    onMarkActedOn={handleMarkActedOn}
                    onPlaceBet={(id) =>
                      handlePlaceBet(id, `${signal.tourney_id} #${signal.match_num}`, signal.kelly_stake)
                    }
                  />
                );
              })}
          </div>
        )}
      </div>
    </div>
  );
}
