import { useState } from 'react';
import { ResponsiveBar } from '@nivo/bar';
import { ResponsiveLine } from '@nivo/line';
import { usePropBacktest } from '../hooks/useProps';
import { CalibrationChart } from '../components/charts/CalibrationChart';
import { EmptyState } from '../components/shared/EmptyState';
import { SkeletonCard } from '../components/shared/SkeletonCard';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { nivoTheme } from '../components/charts/nivoTheme';
import type { CalibrationBin } from '../api/types';

const STAT_LABELS: Record<string, string> = {
  aces: 'Aces',
  double_faults: 'Double Faults',
  games_won: 'Games Won',
  breaks_of_serve: 'Breaks of Serve',
  sets_won: 'Sets Won',
  first_set_winner: 'First Set Winner',
};

const ALL_STAT_TYPES = ['aces', 'double_faults', 'games_won', 'breaks_of_serve', 'sets_won', 'first_set_winner'];

export function PropAnalysisTab() {
  const { data, isLoading } = usePropBacktest();
  const [selectedStat, setSelectedStat] = useState<string>('aces');

  if (isLoading) {
    return (
      <div className="p-6 space-y-6">
        <h2 className="text-xl font-semibold text-slate-100">Prop Analysis</h2>
        <SkeletonCard variant="chart" height={240} />
        <SkeletonCard variant="chart" height={240} />
      </div>
    );
  }

  if (!data || data.total_tracked === 0) {
    return (
      <div className="p-6">
        <h2 className="text-xl font-semibold text-slate-100 mb-2">Prop Analysis</h2>
        <EmptyState
          heading="No resolved prop predictions available"
          body="No resolved prop predictions from 2023+ available for analysis. Enter prop lines and run the prop models, then check back once actual match results are resolved."
        />
      </div>
    );
  }

  // Section 1: Hit rate by stat type — map to bar chart format
  const hitRateBarData = data.by_stat_type.map((row) => ({
    stat: STAT_LABELS[row.stat_type] ?? row.stat_type,
    'Hit Rate': +(row.hit_rate * 100).toFixed(1),
  }));

  // Section 2: Calibration chart — filter bins by selectedStat and convert to CalibrationBin[]
  const filteredCalibrationBins: CalibrationBin[] = data.calibration_bins
    .filter((b) => b.stat_type === selectedStat)
    .map((b) => ({
      midpoint: b.predicted_p,
      empirical_freq: b.actual_hit_rate,
      n_samples: b.n,
    }));

  // Section 3: Rolling hit rate line chart — filter by selectedStat
  const filteredRolling = data.rolling_hit_rate.filter((r) => r.stat_type === selectedStat);
  const rollingLineData = [
    {
      id: STAT_LABELS[selectedStat] ?? selectedStat,
      data: filteredRolling.map((r) => ({ x: r.date, y: +(r.hit_rate * 100).toFixed(1) })),
    },
  ];

  return (
    <div className="p-6 space-y-8">
      <h2 className="text-xl font-semibold text-slate-100">Prop Analysis</h2>
      <p className="text-sm text-slate-400 -mt-6">
        Based on {data.total_tracked} resolved prop predictions since {data.date_from}
      </p>

      {/* Section 1: Hit Rate by Stat Type Bar Chart */}
      <Card className="bg-slate-800 border-slate-700">
        <CardHeader className="pb-2">
          <CardTitle className="text-base text-slate-100">Hit Rate by Stat Type</CardTitle>
        </CardHeader>
        <CardContent>
          {hitRateBarData.length === 0 ? (
            <EmptyState heading="No data" body="No stat-level breakdown available." />
          ) : (
            <div style={{ height: 260 }} role="img" aria-label="Hit rate by stat type bar chart">
              <ResponsiveBar
                data={hitRateBarData}
                keys={['Hit Rate']}
                indexBy="stat"
                theme={nivoTheme}
                colors={['#22c55e']}
                margin={{ top: 10, right: 20, bottom: 60, left: 55 }}
                axisBottom={{
                  tickRotation: -20,
                  legend: 'Stat Type',
                  legendPosition: 'middle',
                  legendOffset: 50,
                }}
                axisLeft={{
                  legend: 'Hit Rate (%)',
                  legendPosition: 'middle',
                  legendOffset: -45,
                }}
                enableLabel={true}
                labelSkipHeight={12}
                labelTextColor="#f1f5f9"
                enableGridX={false}
                maxValue={100}
                minValue={0}
                markers={[
                  {
                    axis: 'y',
                    value: 55,
                    lineStyle: { stroke: '#f59e0b', strokeWidth: 1, strokeDasharray: '4,4' },
                    legend: '55% edge threshold',
                    legendPosition: 'top-right',
                    textStyle: { fill: '#64748b', fontSize: 10 },
                  },
                ]}
              />
            </div>
          )}
        </CardContent>
      </Card>

      {/* Stat type selector for sections 2 and 3 */}
      <div className="flex items-center gap-4">
        <label className="text-sm text-slate-400">Filter by stat type:</label>
        <Select value={selectedStat} onValueChange={setSelectedStat}>
          <SelectTrigger className="w-52 border-slate-700 bg-slate-900 text-slate-100">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {ALL_STAT_TYPES.map((st) => (
              <SelectItem key={st} value={st}>
                {STAT_LABELS[st] ?? st}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Sections 2 and 3 side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Section 2: Calibration Chart */}
        <Card className="bg-slate-800 border-slate-700">
          <CardHeader className="pb-2">
            <CardTitle className="text-base text-slate-100">
              Calibration — {STAT_LABELS[selectedStat] ?? selectedStat}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <CalibrationChart bins={filteredCalibrationBins} modelVersion={selectedStat} />
          </CardContent>
        </Card>

        {/* Section 3: Rolling Hit Rate Line Chart */}
        <Card className="bg-slate-800 border-slate-700">
          <CardHeader className="pb-2">
            <CardTitle className="text-base text-slate-100">
              Rolling Hit Rate — {STAT_LABELS[selectedStat] ?? selectedStat}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {filteredRolling.length === 0 ? (
              <EmptyState
                heading="No rolling data"
                body="No resolved predictions available for this stat type."
              />
            ) : (
              <div style={{ height: 240 }} role="img" aria-label="Rolling hit rate line chart">
                <ResponsiveLine
                  data={rollingLineData}
                  theme={nivoTheme}
                  margin={{ top: 10, right: 20, bottom: 50, left: 55 }}
                  xScale={{ type: 'point' }}
                  yScale={{ type: 'linear', min: 0, max: 100 }}
                  axisBottom={{
                    tickRotation: -30,
                    legend: 'Date',
                    legendPosition: 'middle',
                    legendOffset: 42,
                  }}
                  axisLeft={{
                    legend: 'Hit Rate (%)',
                    legendPosition: 'middle',
                    legendOffset: -45,
                  }}
                  colors={['#22c55e']}
                  pointSize={4}
                  pointColor={{ theme: 'background' }}
                  pointBorderWidth={2}
                  pointBorderColor={{ from: 'serieColor' }}
                  enableGridX={false}
                  markers={[
                    {
                      axis: 'y',
                      value: 55,
                      lineStyle: { stroke: '#f59e0b', strokeWidth: 1, strokeDasharray: '4,4' },
                      legend: '55%',
                      legendPosition: 'top-right',
                      textStyle: { fill: '#64748b', fontSize: 10 },
                    },
                  ]}
                />
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Section 4: Stat-level breakdown table */}
      <Card className="bg-slate-800 border-slate-700">
        <CardHeader className="pb-2">
          <CardTitle className="text-base text-slate-100">Stat-Level Breakdown</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700 text-slate-400 text-left">
                  <th className="pb-2 pr-4 font-medium">Stat Type</th>
                  <th className="pb-2 pr-4 font-medium text-right">Sample Size</th>
                  <th className="pb-2 pr-4 font-medium text-right">Hit Rate</th>
                  <th className="pb-2 pr-4 font-medium text-right">Avg P(hit)</th>
                  <th className="pb-2 font-medium text-right">Calibration Score</th>
                </tr>
              </thead>
              <tbody>
                {data.by_stat_type.map((row) => {
                  const hitRatePct = (row.hit_rate * 100).toFixed(1);
                  const avgPHitPct = (row.avg_p_hit * 100).toFixed(1);
                  const isEdge = row.hit_rate >= 0.55;
                  return (
                    <tr key={row.stat_type} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                      <td className="py-2 pr-4 text-slate-100 font-medium">
                        {STAT_LABELS[row.stat_type] ?? row.stat_type}
                      </td>
                      <td className="py-2 pr-4 text-right text-slate-300">{row.n}</td>
                      <td className={`py-2 pr-4 text-right font-semibold ${isEdge ? 'text-green-400' : 'text-slate-300'}`}>
                        {hitRatePct}%
                      </td>
                      <td className="py-2 pr-4 text-right text-slate-300">{avgPHitPct}%</td>
                      <td className="py-2 text-right text-slate-300">{row.calibration_score.toFixed(3)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
