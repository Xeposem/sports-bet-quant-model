import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import type { PaperSession, PaperBetsResponse, PaperBet, PaperEquityResponse } from '../api/types';

export function usePaperSession() {
  return useQuery<PaperSession>({
    queryKey: ['paper', 'session'],
    queryFn: () => apiFetch<PaperSession>('/paper/session'),
    staleTime: Infinity,
    retry: false,
  });
}

export function useStartSession() {
  const queryClient = useQueryClient();
  return useMutation<PaperSession, Error, { initial_bankroll: number; kelly_fraction?: number; ev_threshold?: number }>({
    mutationFn: (params) =>
      apiFetch<PaperSession>('/paper/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['paper'] });
    },
  });
}

export function useResetSession() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, void>({
    mutationFn: () =>
      apiFetch<void>('/paper/session', { method: 'DELETE' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['paper'] });
    },
  });
}

export function usePaperBets() {
  return useQuery<PaperBetsResponse>({
    queryKey: ['paper', 'bets'],
    queryFn: () => apiFetch<PaperBetsResponse>('/paper/bets'),
    staleTime: Infinity,
    retry: false,
  });
}

export function usePlacePaperBet() {
  const queryClient = useQueryClient();
  return useMutation<PaperBet, Error, { signal_id: number }>({
    mutationFn: (params) =>
      apiFetch<PaperBet>('/paper/bets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['paper'] });
      queryClient.invalidateQueries({ queryKey: ['signals'] });
    },
  });
}

export function useResolveBet() {
  const queryClient = useQueryClient();
  return useMutation<PaperBet, Error, { betId: number; outcome: number }>({
    mutationFn: ({ betId, outcome }) =>
      apiFetch<PaperBet>(`/paper/bets/${betId}/resolve`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ outcome }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['paper'] });
    },
  });
}

export function usePaperEquity() {
  return useQuery<PaperEquityResponse>({
    queryKey: ['paper', 'equity'],
    queryFn: () => apiFetch<PaperEquityResponse>('/paper/equity'),
    staleTime: Infinity,
    retry: false,
  });
}
