interface KpiCardProps {
  label: string;
  value: string;
  trend?: 'positive' | 'negative' | 'neutral';
}

export function KpiCard({ label, value, trend = 'neutral' }: KpiCardProps) {
  const valueColor =
    trend === 'positive'
      ? 'text-green-500'
      : trend === 'negative'
      ? 'text-red-500'
      : 'text-slate-100';

  return (
    <div
      className="bg-slate-800 border border-slate-700 rounded-lg p-4 min-w-[160px]"
      aria-label={`${label}: ${value}`}
    >
      <p className="text-xs uppercase tracking-wider text-slate-500 font-normal">{label}</p>
      <p className={`text-[28px] font-semibold ${valueColor} mt-1`}>{value}</p>
    </div>
  );
}
