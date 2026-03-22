import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import type {
  OddsListResponse,
  OddsEntry,
  OddsEntryResponse,
  PropLinesListResponse,
} from '../api/types';

export function useOddsList() {
  return useQuery<OddsListResponse>({
    queryKey: ['odds', 'list'],
    queryFn: () => apiFetch<OddsListResponse>('/odds/list'),
    staleTime: Infinity,
    retry: 1,
  });
}

export function useSubmitOdds() {
  const queryClient = useQueryClient();
  return useMutation<OddsEntryResponse, Error, OddsEntry>({
    mutationFn: (entry) =>
      apiFetch<OddsEntryResponse>('/odds/manual', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(entry),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['odds'] });
      queryClient.invalidateQueries({ queryKey: ['signals'] });
    },
  });
}

export function useDeleteOdds() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, { tourney_id: string; match_num: number }>({
    mutationFn: ({ tourney_id, match_num }) =>
      apiFetch<void>(`/odds/${tourney_id}/${match_num}`, { method: 'DELETE' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['odds'] });
      queryClient.invalidateQueries({ queryKey: ['signals'] });
    },
  });
}

export function usePropLinesList() {
  return useQuery<PropLinesListResponse>({
    queryKey: ['props', 'lines'],
    queryFn: () => apiFetch<PropLinesListResponse>('/props/lines'),
    staleTime: Infinity,
    retry: 1,
  });
}

export function useDeletePropLine() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, { lineId: number }>({
    mutationFn: ({ lineId }) =>
      apiFetch<void>(`/props/lines/${lineId}`, { method: 'DELETE' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['props'] });
    },
  });
}
