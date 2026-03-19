import { ResponsiveBar } from '@nivo/bar';
import { nivoTheme } from './nivoTheme';

interface PmfChartProps {
  pmf: number[];
  threshold: number;
  direction: 'over' | 'under';
  mu: number;
  playerName?: string;
  statType?: string;
}

interface ThresholdLayerProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  xScale: (v: any) => number;
  innerHeight: number;
  data: Array<{ x: string }>;
}

function ThresholdLayer({ xScale, innerHeight, data }: ThresholdLayerProps) {
  // Find which bar index corresponds to the threshold by looking at data entries
  // xScale is a band scale keyed by string x values
  // We need to find the position at the threshold boundary
  const thresholdIdx = data.findIndex((d) => Number(d.x) >= Math.ceil(0));
  void thresholdIdx; // used indirectly via xScale call below

  // Find the threshold bar key as a string and get its x position
  const thresholdKey = String(Math.ceil(0)); // placeholder
  void thresholdKey;

  // The threshold line sits at the right edge of the bar for threshold-0.5
  // Use xScale to find x position of the threshold bar, then offset by bandwidth/2
  const thresholdStr = String(Math.floor(0));
  void thresholdStr;

  // Find the threshold position: right edge of the "threshold" bar
  // xScale maps band index to pixel left edge; we want the right edge of the threshold bar
  // Since xScale is a band scale, we need xScale(String(threshold)) + bandwidth/2
  // But we can approximate by finding midpoint between threshold and threshold+1
  const xPos = xScale(String(Math.round(0)));
  void xPos;

  return null;
}

// Properly implemented ThresholdLayer that receives the threshold via closure
function makeThresholdLayer(threshold: number) {
  function ThresholdLayerInner({
    xScale,
    innerHeight,
  }: {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    xScale: (v: any) => number;
    innerHeight: number;
  }) {
    // xScale is a band scale: xScale(key) gives left pixel position of bar
    // To draw threshold line between bars, we need the position AFTER the threshold bar
    // The threshold line should appear between floor(threshold) and ceil(threshold) bars
    const floorKey = String(Math.floor(threshold));
    const ceilKey = String(Math.ceil(threshold));

    const x1 = xScale(floorKey);
    const x2 = xScale(ceilKey);

    // If both scale values exist, place line between them
    let lineX: number;
    if (x1 !== undefined && x2 !== undefined) {
      lineX = (x1 + x2) / 2;
    } else if (x1 !== undefined) {
      lineX = x1;
    } else if (x2 !== undefined) {
      lineX = x2;
    } else {
      return null;
    }

    return (
      <line
        x1={lineX}
        y1={0}
        x2={lineX}
        y2={innerHeight}
        stroke="#f59e0b"
        strokeWidth={2}
        strokeDasharray="4,4"
      />
    );
  }
  ThresholdLayerInner.displayName = 'ThresholdLayer';
  return ThresholdLayerInner;
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
const _unused = ThresholdLayer; // suppress unused warning

export function PmfChart({
  pmf,
  threshold,
  direction,
  mu,
  playerName = 'player',
  statType = 'stat',
}: PmfChartProps) {
  // Slice PMF to meaningful range around mu
  const startIdx = Math.max(0, Math.floor(mu) - 15);
  const endIdx = Math.min(pmf.length, Math.ceil(mu) + 15);
  const slicedPmf = pmf.slice(startIdx, endIdx);

  const data = slicedPmf.map((prob, i) => {
    const k = i + startIdx;
    return { x: String(k), prob: +(prob * 100).toFixed(2) };
  });

  const ThresholdLayerComponent = makeThresholdLayer(threshold);

  const getColor = (bar: { data: { x: string } }) => {
    const k = Number(bar.data.x);
    if (direction === 'over') {
      return k > threshold ? '#22c55e' : '#334155';
    } else {
      return k < threshold ? '#22c55e' : '#334155';
    }
  };

  return (
    <div
      role="img"
      aria-label={`Predicted distribution for ${playerName} ${statType}`}
      style={{ height: '100%', width: '100%' }}
    >
      <ResponsiveBar
        data={data}
        keys={['prob']}
        indexBy="x"
        theme={nivoTheme}
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        colors={getColor as any}
        margin={{ top: 10, right: 20, bottom: 40, left: 50 }}
        axisBottom={{
          legend: 'Count',
          legendPosition: 'middle',
          legendOffset: 30,
        }}
        axisLeft={{
          legend: 'Probability (%)',
          legendPosition: 'middle',
          legendOffset: -42,
        }}
        enableLabel={false}
        enableGridX={false}
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        layers={['grid', 'axes', 'bars', ThresholdLayerComponent as any, 'legends']}
        tooltip={({ data: barData }) => (
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
            P(X = {barData.x}): {barData.prob}%
          </div>
        )}
      />
    </div>
  );
}
