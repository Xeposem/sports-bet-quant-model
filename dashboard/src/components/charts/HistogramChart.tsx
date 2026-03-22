import { ResponsiveBar } from '@nivo/bar';
import { nivoTheme } from './nivoTheme';

interface HistogramChartProps {
  distribution: number[];
  initialBankroll: number;
}

interface BinDatum {
  bin: string;
  count: number;
  isRuin: boolean;
}

function buildBins(distribution: number[], nBins: number = 20): BinDatum[] {
  if (distribution.length === 0) return [];

  const min = Math.min(...distribution);
  const max = Math.max(...distribution);
  const range = max - min || 1;
  const binWidth = range / nBins;

  const bins: BinDatum[] = Array.from({ length: nBins }, (_, i) => {
    const lo = min + i * binWidth;
    const hi = lo + binWidth;
    const midpoint = (lo + hi) / 2;
    const label = `$${Math.round(lo)}-$${Math.round(hi)}`;
    return { bin: label, count: 0, isRuin: midpoint <= 0 };
  });

  for (const value of distribution) {
    const idx = Math.min(Math.floor((value - min) / binWidth), nBins - 1);
    bins[idx].count += 1;
  }

  return bins;
}

export function HistogramChart({ distribution, initialBankroll: _initialBankroll }: HistogramChartProps) {
  const bins = buildBins(distribution);
  const total = distribution.length || 1;

  return (
    <div className="h-[250px] w-full" role="img" aria-label="Terminal bankroll distribution histogram">
      <ResponsiveBar
        data={bins}
        keys={['count']}
        indexBy="bin"
        theme={nivoTheme}
        colors={(bar) => (bar.data.isRuin ? '#ef4444' : '#22c55e')}
        margin={{ top: 10, right: 20, bottom: 60, left: 50 }}
        axisBottom={{
          legend: 'Terminal Bankroll ($)',
          legendPosition: 'middle',
          legendOffset: 50,
          tickRotation: -45,
          renderTick: () => null, // hide individual tick labels — too many bins
        }}
        axisLeft={{
          legend: 'Frequency',
          legendPosition: 'middle',
          legendOffset: -40,
        }}
        enableLabel={false}
        enableGridX={false}
        tooltip={({ indexValue, value }) => (
          <div
            style={{
              background: '#1e293b',
              color: '#f1f5f9',
              border: '1px solid #334155',
              padding: '8px 12px',
              borderRadius: 4,
              fontSize: 12,
            }}
          >
            <strong>{String(indexValue)}</strong>
            <br />
            Count: {Number(value)} ({((Number(value) / total) * 100).toFixed(1)}%)
          </div>
        )}
      />
    </div>
  );
}
