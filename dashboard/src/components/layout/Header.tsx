import { RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface HeaderProps {
  onRefresh?: () => void;
}

export function Header({ onRefresh }: HeaderProps) {
  return (
    <header className="flex items-center justify-between px-6 h-14 bg-slate-900 border-b border-slate-700">
      <span className="text-slate-100 font-semibold text-xl">Tennis Quant</span>
      <Button
        variant="outline"
        size="sm"
        onClick={onRefresh}
        aria-label="Refresh Data"
        className="flex items-center gap-2 border-slate-600 text-slate-100 hover:bg-slate-800"
      >
        <RefreshCw className="h-4 w-4" />
        Refresh Data
      </Button>
    </header>
  );
}
