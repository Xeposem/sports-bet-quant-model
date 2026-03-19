import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import type { PropsListResponse, PropLineEntry, PropLineResponse, PropAccuracyResponse } from '../api/types';

export function useProps() {
  return useQuery<PropsListResponse>({
    queryKey: ['props'],
    queryFn: () => apiFetch<PropsListResponse>('/props'),
    staleTime: Infinity,
    retry: 1,
  });
}

export function useSubmitPropLine() {
  const queryClient = useQueryClient();
  return useMutation<PropLineResponse, Error, PropLineEntry>({
    mutationFn: (entry: PropLineEntry) =>
      apiFetch<PropLineResponse>('/props', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(entry),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['props'] });
    },
  });
}

export function usePropAccuracy() {
  return useQuery<PropAccuracyResponse>({
    queryKey: ['props', 'accuracy'],
    queryFn: () => apiFetch<PropAccuracyResponse>('/props/accuracy'),
    staleTime: Infinity,
    retry: 1,
  });
}
