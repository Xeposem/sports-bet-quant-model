import { ResponsiveScatterPlot } from '@nivo/scatterplot';
import type { CalibrationBin } from '../../api/types';
import { nivoTheme } from './nivoTheme';
import { EmptyState } from '../shared/EmptyState';

interface DiagonalLayerProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  xScale: (v: number) => number;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  yScale: (v: number) => number;
}

function DiagonalLayer({ xScale, yScale }: DiagonalLayerProps) {
  return (
    <line
      x1={xScale(0)}
      y1={yScale(0)}
      x2={xScale(1)}
      y2={yScale(1)}
      stroke="#475569"
      strokeWidth={1}
      strokeDasharray="4 4"
    />
  );
}

interface CalibrationChartProps {
  bins: CalibrationBin[];
  modelVersion?: string;
}

export function CalibrationChart({ bins, modelVersion }: CalibrationChartProps) {
  if (!bins || bins.length === 0) {
    return (
      <EmptyState
        heading="Calibration data unavailable"
        body="No calibration data found for this model."
      />
    );
  }

  const data = [
    {
      id: modelVersion ?? 'calibration',
      data: bins.map((b) => ({ x: b.midpoint, y: b.empirical_freq })),
    },
  ];

  return (
    <div
      style={{ height: 240 }}
      role="img"
      aria-label="Calibration reliability diagram"
    >
      <ResponsiveScatterPlot
        data={data}
        theme={nivoTheme}
        xScale={{ type: 'linear', min: 0, max: 1 }}
        yScale={{ type: 'linear', min: 0, max: 1 }}
        nodeSize={8}
        colors={['#3b82f6']}
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        layers={['grid', 'axes', DiagonalLayer as any, 'nodes', 'markers', 'legends']}
        axisBottom={{
          legend: 'Predicted Probability',
          legendPosition: 'middle',
          legendOffset: 30,
        }}
        axisLeft={{
          legend: 'Empirical Win Rate',
          legendPosition: 'middle',
          legendOffset: -40,
        }}
        margin={{ top: 10, right: 20, bottom: 40, left: 50 }}
      />
    </div>
  );
}
