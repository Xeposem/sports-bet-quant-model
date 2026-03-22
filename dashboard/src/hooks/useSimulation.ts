import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import type { MonteCarloRequest, MonteCarloResult } from '../api/types';

export function useSimulationResult() {
  return useQuery<MonteCarloResult>({
    queryKey: ['simulation'],
    queryFn: () => apiFetch<MonteCarloResult>('/simulation/result'),
    staleTime: Infinity,
    retry: false, // 404 expected when no simulation has run
  });
}

export function useRunSimulation() {
  const queryClient = useQueryClient();
  return useMutation<MonteCarloResult, Error, MonteCarloRequest>({
    mutationFn: (params) =>
      apiFetch<MonteCarloResult>('/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['simulation'] });
    },
  });
}
