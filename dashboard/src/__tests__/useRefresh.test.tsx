import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { type ReactNode } from 'react';
import { useRefreshAll } from '../hooks/useRefresh';

// Mock apiFetch
vi.mock('../api/client', () => ({
  apiFetch: vi.fn(),
}));

import { apiFetch } from '../api/client';

function createWrapper(queryClient?: QueryClient) {
  const qc = queryClient ?? new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return {
    wrapper: function Wrapper({ children }: { children: ReactNode }) {
      return (
        <QueryClientProvider client={qc}>
          {children}
        </QueryClientProvider>
      );
    },
    queryClient: qc,
  };
}

describe('useRefreshAll', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('calls POST /refresh on mutate', async () => {
    let resolveStatus: (() => void) | null = null;
    const statusPromise = new Promise<void>((res) => { resolveStatus = res; });

    vi.mocked(apiFetch).mockImplementation(async (path: string, init?: RequestInit) => {
      if (init?.method === 'POST' && path === '/refresh') {
        return { job_id: 'abc123', status: 'pending' };
      }
      // Block status poll until we choose to resolve it
      await statusPromise;
      return { job_id: 'abc123', status: 'complete', step: null, started_at: null, result: null };
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useRefreshAll(), { wrapper });

    act(() => {
      result.current.mutate(undefined);
    });

    // Let the POST call execute
    await act(async () => {
      await Promise.resolve();
    });

    expect(vi.mocked(apiFetch)).toHaveBeenCalledWith('/refresh', { method: 'POST' });

    // Clean up — resolve the hanging status call and advance one interval
    resolveStatus!();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
      await Promise.resolve();
    });
  });

  it('polls until status is complete and resolves', async () => {
    let pollCount = 0;

    vi.mocked(apiFetch).mockImplementation(async (path: string, init?: RequestInit) => {
      if (init?.method === 'POST' && path === '/refresh') {
        return { job_id: 'job1', status: 'pending' };
      }
      pollCount++;
      if (pollCount < 2) {
        return { job_id: 'job1', status: 'running', step: null, started_at: null, result: null };
      }
      return { job_id: 'job1', status: 'complete', step: null, started_at: null, result: null };
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useRefreshAll(), { wrapper });

    act(() => {
      result.current.mutate(undefined);
    });

    // Advance through 2 intervals (2000ms each)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
      await Promise.resolve();
    });

    expect(pollCount).toBeGreaterThanOrEqual(2);
  });

  it('invalidates all queries on success', async () => {
    vi.mocked(apiFetch).mockImplementation(async (path: string, init?: RequestInit) => {
      if (init?.method === 'POST' && path === '/refresh') {
        return { job_id: 'job2', status: 'pending' };
      }
      return { job_id: 'job2', status: 'complete', step: null, started_at: null, result: null };
    });

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { wrapper } = createWrapper(queryClient);
    const { result } = renderHook(() => useRefreshAll(), { wrapper });

    act(() => {
      result.current.mutate(undefined);
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
      await Promise.resolve();
    });

    expect(invalidateSpy).toHaveBeenCalled();
  });
});
