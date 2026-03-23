import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import type { PropsListResponse, PropLineEntry, PropLineResponse, PropAccuracyResponse, PropScanResponse } from '../api/types';

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

export function useScanPropScreenshot() {
  return useMutation<PropScanResponse, Error, File>({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      // CRITICAL: Do NOT set Content-Type header — browser sets multipart boundary automatically
      return apiFetch<PropScanResponse>('/props/scan', {
        method: 'POST',
        body: formData,
      });
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
