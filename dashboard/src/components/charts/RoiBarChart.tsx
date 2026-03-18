import { ResponsiveBar } from '@nivo/bar';
import { nivoTheme } from './nivoTheme';

interface RoiBarChartProps {
  data: { id: string; roi: number }[];
  dimension: string;
  onBarClick: (value: string) => void;
  activeFilter?: string;
}

export function RoiBarChart({ data, dimension, onBarClick, activeFilter }: RoiBarChartProps) {
  return (
    <div style={{ height: 220 }} role="img" aria-label={`ROI by ${dimension}`}>
      <ResponsiveBar
        data={data}
        keys={['roi']}
        indexBy="id"
        layout="horizontal"
        theme={nivoTheme}
        colors={(bar) =>
          String(bar.data.id) === activeFilter
            ? '#60a5fa'
            : Number(bar.value) >= 0
            ? '#22c55e'
            : '#ef4444'
        }
        onClick={(bar) => onBarClick(String(bar.indexValue))}
        margin={{ top: 10, right: 20, bottom: 30, left: 80 }}
        axisLeft={{ tickSize: 0 }}
        axisBottom={{
          legend: 'ROI %',
          legendPosition: 'middle',
          legendOffset: 25,
        }}
        enableGridY={false}
        enableLabel={false}
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
            <strong>{String(indexValue)}</strong>: {Number(value).toFixed(2)}%
          </div>
        )}
      />
    </div>
  );
}
