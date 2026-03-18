import { useState } from 'react';
import { useSignals } from '../hooks/useSignals';
import { SignalCard } from '../components/shared/SignalCard';
import { EmptyState } from '../components/shared/EmptyState';
import { SkeletonCard } from '../components/shared/SkeletonCard';
import { FilterBar } from '../components/shared/FilterBar';
import type { PredictionRow } from '../api/types';

type SortBy = 'ev' | 'date';

export function SignalsTab() {
  const [filterParams, setFilterParams] = useState<{ surface: string; min_ev: number }>({
    surface: '',
    min_ev: 0,
  });
  const [sortBy, setSortBy] = useState<SortBy>('ev');

  const signals = useSignals({
    surface: filterParams.surface || undefined,
    min_ev: filterParams.min_ev > 0 ? filterParams.min_ev : undefined,
  });

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

  const sortedSignals = (): PredictionRow[] => {
    if (!signals.data?.data) return [];
    const data = [...signals.data.data];
    if (sortBy === 'ev') {
      return data.sort((a, b) => (b.ev_value ?? -Infinity) - (a.ev_value ?? -Infinity));
    }
    return data.sort(
      (a, b) => new Date(b.predicted_at).getTime() - new Date(a.predicted_at).getTime()
    );
  };

  return (
    <div>
      <FilterBar filters={filters} />
      <div className="p-6">
        {signals.isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <SkeletonCard key={i} variant="signal" />
            ))}
          </div>
        ) : sortedSignals().length === 0 ? (
          <EmptyState
            heading="No active signals"
            body="No bets currently exceed the EV threshold. Click Refresh Data to fetch the latest predictions."
            action={{ label: 'Refresh Data', onClick: () => {} }}
          />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {sortedSignals().map((signal, idx) => (
              <SignalCard
                key={`${signal.tourney_id}-${signal.match_num}-${signal.player_id}-${idx}`}
                signal={signal}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
