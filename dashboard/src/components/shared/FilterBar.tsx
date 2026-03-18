import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

interface FilterDef {
  key: string;
  label: string;
  options: string[];
  value: string;
  onChange: (val: string) => void;
}

interface FilterBarProps {
  filters: FilterDef[];
}

// Radix Select does not allow value="" — use "__all__" as the "All" sentinel
const ALL_VALUE = '__all__';

export function FilterBar({ filters }: FilterBarProps) {
  return (
    <div className="flex items-center gap-4 bg-slate-800 border-b border-slate-700 h-11 px-6">
      {filters.map((filter) => (
        <div key={filter.key} className="flex items-center gap-2">
          <span className="text-xs uppercase tracking-wider text-slate-400">
            {filter.label}
          </span>
          <Select
            value={filter.value === '' ? ALL_VALUE : filter.value}
            onValueChange={(val) => filter.onChange(val === ALL_VALUE ? '' : val)}
          >
            <SelectTrigger
              className="h-8 w-36 bg-slate-800 border-slate-700 text-slate-100 text-xs"
              aria-label={filter.label}
            >
              <SelectValue placeholder="All" />
            </SelectTrigger>
            <SelectContent className="bg-slate-800 border-slate-700 text-slate-100">
              <SelectItem value={ALL_VALUE}>All</SelectItem>
              {filter.options.map((opt) => (
                <SelectItem key={opt} value={opt}>
                  {opt}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ))}
    </div>
  );
}
