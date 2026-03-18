import { X } from 'lucide-react';

interface FilterChipProps {
  label: string;
  onDismiss: () => void;
}

export function FilterChip({ label, onDismiss }: FilterChipProps) {
  return (
    <div className="inline-flex items-center gap-1">
      <span className="text-slate-400 text-xs">Filtered by:</span>
      <span className="inline-flex items-center bg-slate-700 text-slate-100 text-xs rounded-full px-3 py-1 gap-1">
        {label}
        <button
          onClick={onDismiss}
          aria-label={`Remove ${label} filter`}
          className="ml-1 hover:text-white focus:outline-none"
        >
          <X size={14} />
        </button>
      </span>
    </div>
  );
}
