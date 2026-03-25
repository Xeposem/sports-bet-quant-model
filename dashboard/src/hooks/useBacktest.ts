import { useQuery, useMutation } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import type { BacktestSummary, PaginatedBetsResponse, SweepResultEntry } from '../api/types';

export function useBacktestSummary(params?: { surface?: string; year?: string; model?: string }) {
  const searchParams = new URLSearchParams();
  if (params?.surface) searchParams.set('surface', params.surface);
  if (params?.year) searchParams.set('year', params.year);
  if (params?.model) searchParams.set('model', params.model);
  const qs = searchParams.toString();
  return useQuery<BacktestSummary>({
    queryKey: ['backtest', params],
    queryFn: () => apiFetch<BacktestSummary>(`/backtest${qs ? `?${qs}` : ''}`),
    staleTime: Infinity,
    retry: 1,
  });
}

export function useBacktestBets(offset: number, limit: number, filters?: Record<string, string>) {
  return useQuery<PaginatedBetsResponse>({
    queryKey: ['backtest-bets', offset, limit, filters],
    queryFn: () => {
      const sp = new URLSearchParams();
      sp.set('offset', String(offset));
      sp.set('limit', String(limit));
      if (filters) { Object.entries(filters).forEach(([k, v]) => sp.set(k, v)); }
      return apiFetch<PaginatedBetsResponse>(`/backtest/bets?${sp.toString()}`);
    },
    staleTime: Infinity,
    retry: 1,
  });
}

interface BacktestRunParams {
  kelly_fraction?: number;
  max_bet_pct?: number;
  ev_threshold?: number;
  initial_bankroll?: number;
  model_version?: string;
  clv_threshold?: number;
  sweep?: boolean;
}

interface BacktestJobResponse {
  job_id: string;
  status: string;
}

export function useRunBacktest() {
  return useMutation<BacktestJobResponse, Error, BacktestRunParams>({
    mutationFn: (params) =>
      apiFetch<BacktestJobResponse>('/backtest/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      }),
  });
}

interface BacktestJobStatus {
  job_id: string;
  status: string;
  started_at?: string;
  result?: {
    sweep?: SweepResultEntry[];
    folds_run?: number;
    bets_placed?: number;
    total_pnl_kelly?: number;
    final_bankroll?: number;
  };
}

export function useBacktestJobStatus(jobId: string | null) {
  return useQuery<BacktestJobStatus>({
    queryKey: ['backtest-job', jobId],
    queryFn: () => apiFetch<BacktestJobStatus>(`/backtest/run/status?job_id=${jobId}`),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data?.status === 'complete' || data?.status === 'failed') return false;
      return 2000;
    },
  });
}
