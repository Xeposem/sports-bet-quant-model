import { Skeleton } from '@/components/ui/skeleton';

interface SkeletonCardProps {
  variant: 'kpi' | 'chart' | 'table' | 'signal';
  height?: number;
}

export function SkeletonCard({ variant, height = 280 }: SkeletonCardProps) {
  if (variant === 'kpi') {
    return (
      <div aria-busy="true" aria-label="Loading kpi data" className="p-4">
        <Skeleton className="h-4 w-20 mb-3" />
        <Skeleton className="h-8 w-28" />
      </div>
    );
  }

  if (variant === 'chart') {
    return (
      <div aria-busy="true" aria-label="Loading chart data" style={{ height }}>
        <Skeleton className="w-full h-full" />
      </div>
    );
  }

  if (variant === 'table') {
    return (
      <div aria-busy="true" aria-label="Loading table data" className="space-y-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className={`h-10 w-full ${i % 2 === 0 ? 'bg-slate-700' : 'bg-slate-800'}`} />
        ))}
      </div>
    );
  }

  // signal variant
  return (
    <div aria-busy="true" aria-label="Loading signal data">
      <Skeleton className="h-40 w-full" />
    </div>
  );
}
