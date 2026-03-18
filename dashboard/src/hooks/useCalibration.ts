import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import type { CalibrationResponse } from '../api/types';

export function useCalibration(model?: string) {
  return useQuery<CalibrationResponse>({
    queryKey: ['calibration', model],
    queryFn: () => apiFetch<CalibrationResponse>(`/calibration${model ? `?model=${model}` : ''}`),
    staleTime: Infinity,
    retry: 1,
  });
}
