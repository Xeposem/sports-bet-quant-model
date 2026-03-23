import { useRef } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { apiFetch } from '../api/client';
import type { JobResponse, RefreshStatusResponse } from '../api/types';

const STEP_LABELS: Record<string, string> = {
  ingest: 'Ingesting match data…',
  ratings: 'Computing Glicko-2 ratings…',
  sentiment: 'Scoring sentiment…',
  features: 'Building feature matrix…',
  props_predict: 'Generating prop predictions…',
  props_resolution: 'Resolving prop results…',
  done: 'Complete',
};

export function useRefreshAll() {
  const queryClient = useQueryClient();
  const jobIdRef = useRef<string | null>(null);

  const cancel = async () => {
    if (!jobIdRef.current) return;
    await apiFetch(`/refresh/cancel?job_id=${jobIdRef.current}`, { method: 'POST' });
  };

  const mutation = useMutation({
    mutationFn: async () => {
      const job = await apiFetch<JobResponse>('/refresh', { method: 'POST' });
      jobIdRef.current = job.job_id;
      const toastId = toast.loading('Starting refresh…', {
        action: { label: 'Cancel', onClick: () => cancel() },
      });

      return new Promise<void>((resolve, reject) => {
        const interval = setInterval(async () => {
          try {
            const status = await apiFetch<RefreshStatusResponse>(
              `/refresh/status?job_id=${job.job_id}`,
            );

            if (status.step && status.step !== 'done' && status.step !== 'cancelled') {
              toast.loading(STEP_LABELS[status.step] ?? status.step, {
                id: toastId,
                action: { label: 'Cancel', onClick: () => cancel() },
              });
            }

            if (status.status === 'complete') {
              clearInterval(interval);
              jobIdRef.current = null;
              toast.success('Pipeline refresh complete', { id: toastId });
              resolve();
            } else if (status.status === 'cancelled') {
              clearInterval(interval);
              jobIdRef.current = null;
              toast.warning('Refresh cancelled', { id: toastId });
              resolve();
            } else if (status.status === 'failed' || status.status === 'error') {
              clearInterval(interval);
              jobIdRef.current = null;
              toast.error('Refresh failed — check API logs', { id: toastId });
              reject(new Error('Refresh failed'));
            }
          } catch (err) {
            clearInterval(interval);
            jobIdRef.current = null;
            toast.error('Refresh failed — lost connection', { id: toastId });
            reject(err);
          }
        }, 2000);
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries();
    },
  });

  return mutation;
}
