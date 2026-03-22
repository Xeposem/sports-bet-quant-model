import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import type { SignalsResponse, SignalRecord } from '../api/types';

export function useSignals(params?: { surface?: string; min_ev?: number; status?: string }) {
  const searchParams = new URLSearchParams();
  if (params?.surface) searchParams.set('surface', params.surface);
  if (params?.min_ev !== undefined) searchParams.set('min_ev', String(params.min_ev));
  if (params?.status) searchParams.set('status', params.status);
  const qs = searchParams.toString();
  return useQuery<SignalsResponse>({
    queryKey: ['signals', params],
    queryFn: () => apiFetch<SignalsResponse>(`/signals${qs ? `?${qs}` : ''}`),
    staleTime: Infinity,
    retry: 1,
  });
}

export function useUpdateSignalStatus() {
  const queryClient = useQueryClient();
  return useMutation<SignalRecord, Error, { signalId: number; status: string }>({
    mutationFn: ({ signalId, status }) =>
      apiFetch<SignalRecord>(`/signals/${signalId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['signals'] });
    },
  });
}
