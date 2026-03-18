import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import type { PredictResponse } from '../api/types';

export function useSignals(params?: { surface?: string; min_ev?: number }) {
  const searchParams = new URLSearchParams();
  if (params?.surface) searchParams.set('surface', params.surface);
  if (params?.min_ev !== undefined) searchParams.set('min_ev', String(params.min_ev));
  const qs = searchParams.toString();
  return useQuery<PredictResponse>({
    queryKey: ['signals', params],
    queryFn: () => apiFetch<PredictResponse>(`/predict${qs ? `?${qs}` : ''}`),
    staleTime: Infinity,
    retry: 1,
  });
}
