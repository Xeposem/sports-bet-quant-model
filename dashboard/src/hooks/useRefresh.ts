import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import type { JobResponse, RefreshStatusResponse } from '../api/types';

export function useRefreshAll() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      const job = await apiFetch<JobResponse>('/refresh', { method: 'POST' });
      // Poll every 2 seconds until complete or error
      return new Promise<void>((resolve, reject) => {
        const interval = setInterval(async () => {
          try {
            const status = await apiFetch<RefreshStatusResponse>(`/refresh/${job.job_id}`);
            if (status.status === 'complete') {
              clearInterval(interval);
              resolve();
            } else if (status.status === 'error') {
              clearInterval(interval);
              reject(new Error('Refresh failed'));
            }
          } catch (err) {
            clearInterval(interval);
            reject(err);
          }
        }, 2000);
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries();
    },
  });
}
