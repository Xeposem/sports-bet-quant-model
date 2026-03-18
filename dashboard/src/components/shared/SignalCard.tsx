import type { PredictionRow } from '../../api/types';

interface SignalCardProps {
  signal: PredictionRow;
}

function evBorderClass(evValue: number | null): string {
  if (evValue === null) return 'border-l-[3px] border-slate-700';
  if (evValue > 5) return 'border-l-[3px] border-green-500';
  if (evValue >= 2) return 'border-l-[3px] border-amber-500';
  return 'border-l-[3px] border-slate-700';
}

function formatEv(evValue: number | null): string {
  if (evValue === null) return 'N/A EV';
  const sign = evValue >= 0 ? '+' : '';
  return `${sign}${evValue.toFixed(1)}% EV`;
}

function formatProb(prob: number | null): string {
  if (prob === null) return 'N/A';
  return `${(prob * 100).toFixed(1)}%`;
}

function formatEdge(edge: number | null): string {
  if (edge === null) return 'N/A';
  return `${(edge * 100).toFixed(1)}%`;
}

function formatOdds(odds: number | null): string {
  if (odds === null) return 'N/A';
  return odds.toFixed(2);
}

export function SignalCard({ signal }: SignalCardProps) {
  const borderClass = evBorderClass(signal.ev_value);
  const evColor = signal.ev_value !== null && signal.ev_value > 0 ? 'text-green-500' : 'text-slate-100';

  return (
    <div
      className={`bg-slate-800 border border-slate-700 rounded-lg p-4 ${borderClass}`}
      role="article"
      aria-label={`Signal: ${signal.tourney_id} match ${signal.match_num} -- EV ${signal.ev_value !== null ? signal.ev_value.toFixed(1) : 'N/A'}%`}
    >
      <p className="text-sm font-semibold text-slate-100">
        {signal.tourney_id} #{signal.match_num}
      </p>
      <p className={`text-xl font-semibold ${evColor} mt-2`}>
        {formatEv(signal.ev_value)}
      </p>
      <div className="flex gap-4 text-sm mt-2">
        <span className="text-slate-300">
          <span className="text-slate-500">Prob: </span>
          {formatProb(signal.calibrated_prob)}
        </span>
        <span className="text-slate-300">
          <span className="text-slate-500">Edge: </span>
          {formatEdge(signal.edge)}
        </span>
        <span className="text-slate-300">
          <span className="text-slate-500">Odds: </span>
          {formatOdds(signal.decimal_odds)}
        </span>
      </div>
      <p className="text-xs text-slate-500 mt-2">{signal.model_version}</p>
    </div>
  );
}
