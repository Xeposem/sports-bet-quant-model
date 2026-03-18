import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import type { BankrollResponse } from '../api/types';

export function useBankroll() {
  return useQuery<BankrollResponse>({
    queryKey: ['bankroll'],
    queryFn: () => apiFetch<BankrollResponse>('/bankroll'),
    staleTime: Infinity,
    retry: 1,
  });
}
