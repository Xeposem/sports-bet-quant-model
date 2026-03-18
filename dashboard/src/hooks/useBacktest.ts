import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import type { BacktestSummary, PaginatedBetsResponse } from '../api/types';

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
