import type { SignalRecord } from '../../api/types';

interface SignalCardProps {
  signal: SignalRecord;
  onPlaceBet?: (signalId: number) => void;
  onMarkActedOn?: (signalId: number) => void;
  paperSessionActive?: boolean;
  dimmed?: boolean;
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

function formatStake(stake: number | null): string {
  if (stake === null) return 'N/A';
  return `$${stake.toFixed(2)}`;
}

function formatConfidence(confidence: number | null): string {
  if (confidence === null) return 'N/A';
  return `${(confidence * 100).toFixed(0)}%`;
}

function formatSharpe(sharpe: number | null): string {
  if (sharpe === null) return 'N/A';
  return sharpe.toFixed(2);
}

function statusBadgeClass(status: string): string {
  switch (status) {
    case 'new':
      return 'bg-green-500 text-white';
    case 'seen':
      return 'bg-slate-600 text-slate-200';
    case 'acted-on':
      return 'bg-blue-500 text-white';
    case 'expired':
      return 'bg-slate-700 text-slate-400 line-through';
    default:
      return 'bg-slate-600 text-slate-200';
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case 'new':
      return 'New';
    case 'seen':
      return 'Seen';
    case 'acted-on':
      return 'Acted On';
    case 'expired':
      return 'Expired';
    default:
      return status;
  }
}

export function SignalCard({
  signal,
  onPlaceBet,
  onMarkActedOn,
  paperSessionActive = false,
  dimmed = false,
}: SignalCardProps) {
  const borderClass = evBorderClass(signal.ev_value);
  const evColor = signal.ev_value !== null && signal.ev_value > 0 ? 'text-green-500' : 'text-slate-100';

  return (
    <div
      className={`bg-slate-800 border border-slate-700 rounded-lg p-4 ${borderClass} ${dimmed ? 'opacity-50 pointer-events-none' : ''}`}
      role="article"
      aria-label={`Signal: ${signal.tourney_id} match ${signal.match_num} -- EV ${signal.ev_value !== null ? signal.ev_value.toFixed(1) : 'N/A'}%`}
    >
      <div className="flex justify-between items-start">
        <p className="text-sm font-semibold text-slate-100">
          {signal.tourney_id} #{signal.match_num}
        </p>
        <span className={`text-xs px-2 py-0.5 rounded-full ${statusBadgeClass(signal.status)}`}>
          {statusLabel(signal.status)}
        </span>
      </div>
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
      <div className="flex gap-4 text-sm mt-1 text-slate-300">
        <span>
          <span className="text-slate-500">Confidence: </span>
          {formatConfidence(signal.confidence)}
        </span>
        <span>
          <span className="text-slate-500">Sharpe: </span>
          {formatSharpe(signal.sharpe)}
        </span>
        <span>
          <span className="text-slate-500">Stake: </span>
          {formatStake(signal.kelly_stake)}
        </span>
      </div>
      <p className="text-xs text-slate-500 mt-2">{signal.model_version}</p>
      {signal.court_speed_tier && (
        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium mt-1 ${
          signal.court_speed_tier === 'Fast' ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400' :
          signal.court_speed_tier === 'Slow' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400' :
          'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
        }`}>
          {signal.court_speed_tier}
          {signal.court_speed_index != null && ` (${signal.court_speed_index.toFixed(2)})`}
        </span>
      )}
      <div className="flex gap-2 mt-3">
        {signal.status !== 'expired' && signal.status !== 'acted-on' && (
          <button
            onClick={() => onMarkActedOn?.(signal.id)}
            className="text-xs px-3 py-1 rounded border border-slate-600 text-slate-300 hover:bg-slate-700"
          >
            Mark Acted On
          </button>
        )}
        <button
          onClick={() => onPlaceBet?.(signal.id)}
          disabled={!paperSessionActive}
          className="text-xs px-3 py-1 rounded bg-green-500 text-white hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed w-full"
          title={!paperSessionActive ? 'Start a paper trading session first' : undefined}
        >
          Place Bet
        </button>
      </div>
    </div>
  );
}
