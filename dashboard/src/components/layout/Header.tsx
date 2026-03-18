import { Loader2, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { useRefreshAll } from '../../hooks/useRefresh';

export function Header() {
  const refresh = useRefreshAll();

  const handleRefresh = () => {
    refresh.mutate(undefined, {
      onError: () => {
        toast.error('Refresh failed — check the API server logs for details.');
      },
    });
  };

  return (
    <header className="flex items-center justify-between px-6 h-14 bg-slate-900 border-b border-slate-700">
      <span className="text-slate-100 font-semibold text-xl">Tennis Quant</span>
      <Button
        variant="outline"
        size="sm"
        onClick={handleRefresh}
        disabled={refresh.isPending}
        aria-disabled={refresh.isPending}
        aria-label={refresh.isPending ? 'Refreshing data' : 'Refresh Data'}
        className="flex items-center gap-2 border-slate-600 text-slate-100 hover:bg-slate-800"
      >
        {refresh.isPending ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <RefreshCw className="h-4 w-4" />
        )}
        {refresh.isPending ? 'Refreshing...' : 'Refresh Data'}
      </Button>
    </header>
  );
}
