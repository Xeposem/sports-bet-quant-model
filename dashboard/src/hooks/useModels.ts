import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import type { ModelsResponse } from '../api/types';

export function useModels() {
  return useQuery<ModelsResponse>({
    queryKey: ['models'],
    queryFn: () => apiFetch<ModelsResponse>('/models'),
    staleTime: Infinity,
    retry: 1,
  });
}
