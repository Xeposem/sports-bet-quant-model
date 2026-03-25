import { useState, useEffect } from 'react';
import { useBacktestSummary, useBacktestBets, useRunBacktest, useBacktestJobStatus } from '@/hooks/useBacktest';
import { ResponsiveLine } from '@nivo/line';
import { toast } from 'sonner';
import type { SweepResultEntry } from '@/api/types';
import { RoiBarChart } from '@/components/charts/RoiBarChart';
import { FilterBar } from '@/components/shared/FilterBar';
import { FilterChip } from '@/components/shared/FilterChip';
import { BetHistoryTable } from '@/components/shared/BetHistoryTable';
import { SkeletonCard } from '@/components/shared/SkeletonCard';
import { EmptyState } from '@/components/shared/EmptyState';

interface ChartFilter {
  dimension: string;
  value: string;
}

interface FilterParams {
  surface: string;
  year: string;
  model: string;
}

function buildBetsFilterObject(
  filterParams: FilterParams,
  chartFilter: ChartFilter | null
): Record<string, string> {
  const result: Record<string, string> = {};
  if (filterParams.surface) result.surface = filterParams.surface;
  if (filterParams.year) result.year = filterParams.year;
  if (filterParams.model) result.model = filterParams.model;
  if (chartFilter) result[chartFilter.dimension] = chartFilter.value;
  return result;
}

function toRoiData(rows: Record<string, unknown>[], idKey: string): { id: string; roi: number }[] {
  return rows.map((row) => ({
    id: String(row[idKey] ?? ''),
    roi: Number(row['kelly_roi'] ?? 0),
  }));
}

export function BacktestTab() {
  const [chartFilter, setChartFilter] = useState<ChartFilter | null>(null);
  const [filterParams, setFilterParams] = useState<FilterParams>({
    surface: '',
    year: '',
    model: '',
  });
  const [page, setPage] = useState(0);
  const [clvThreshold, setClvThreshold] = useState<number>(() => {
    const stored = localStorage.getItem('clv_threshold_backtest');
    return stored ? parseFloat(stored) : 0.03;
  });
  const handleClvChange = (val: number) => {
    setClvThreshold(val);
    localStorage.setItem('clv_threshold_backtest', String(val));
  };
  const [sweepJobId, setSweepJobId] = useState<string | null>(null);
  const [sweepResults, setSweepResults] = useState<SweepResultEntry[] | null>(null);
  const runBacktest = useRunBacktest();
  const jobStatus = useBacktestJobStatus(sweepJobId);

  useEffect(() => {
    if (jobStatus.data?.status === 'complete' && jobStatus.data.result?.sweep) {
      setSweepResults(jobStatus.data.result.sweep);
      setSweepJobId(null);
    }
  }, [jobStatus.data]);

  const handleRunSweep = () => {
    runBacktest.mutate(
      { clv_threshold: clvThreshold, sweep: true },
      {
        onSuccess: (data) => setSweepJobId(data.job_id),
        onError: () => toast.error('Failed to start sweep'),
      }
    );
  };

  const { data: summary, isLoading: summaryLoading, isError: summaryError } = useBacktestSummary(filterParams);
  const { data: betsData, isLoading: betsLoading } = useBacktestBets(
    page * 20,
    20,
    buildBetsFilterObject(filterParams, chartFilter)
  );

  const handleBarClick = (dimension: string, value: string) => {
    setChartFilter((prev) =>
      prev?.dimension === dimension && prev.value === value ? null : { dimension, value }
    );
    setPage(0);
  };

  const handleFilterChange = (key: keyof FilterParams) => (val: string) => {
    setFilterParams((prev) => ({ ...prev, [key]: val }));
    setPage(0);
  };

  // Extract unique years from by_year breakdown
  const yearOptions = summary?.by_year
    ? summary.by_year.map((r) => String(r['year'] ?? r['fold_year'] ?? '')).filter(Boolean)
    : [];

  const filters = [
    {
      key: 'surface',
      label: 'Surface',
      options: ['Hard', 'Clay', 'Grass', 'Carpet'],
      value: filterParams.surface,
      onChange: handleFilterChange('surface'),
    },
    {
      key: 'year',
      label: 'Year',
      options: yearOptions,
      value: filterParams.year,
      onChange: handleFilterChange('year'),
    },
    {
      key: 'model',
      label: 'Model',
      options: ['logistic_v1'],
      value: filterParams.model,
      onChange: handleFilterChange('model'),
    },
  ];

  if (summaryError) {
    return (
      <EmptyState
        heading="No backtest results"
        body="Run a backtest to see ROI breakdowns and bet history. Use the API or CLI to trigger a run."
      />
    );
  }

  const hasSummaryData = summary && summary.n_bets > 0;

  const surfaceData = summary?.by_surface ? toRoiData(summary.by_surface, 'surface') : [];
  const tourneyLevelData = summary?.by_tourney_level ? toRoiData(summary.by_tourney_level, 'tourney_level') : [];
  const yearData = summary?.by_year ? toRoiData(summary.by_year, 'year') : [];
  const evBucketData = summary?.by_ev_bucket ? toRoiData(summary.by_ev_bucket, 'ev_bucket') : [];
  const rankTierData = summary?.by_rank_tier ? toRoiData(summary.by_rank_tier, 'rank_tier') : [];
  const speedTierData = summary?.by_speed_tier ? toRoiData(summary.by_speed_tier, 'speed_tier') : [];

  return (
    <div>
      <FilterBar filters={filters} />
      {/* CLV Threshold Slider */}
      <div className="px-6 pt-4 pb-2 flex items-center gap-4">
        <span className="text-sm text-slate-400 whitespace-nowrap">CLV: {clvThreshold.toFixed(2)}</span>
        <input
          type="range"
          min={0}
          max={0.15}
          step={0.01}
          value={clvThreshold}
          onChange={(e) => handleClvChange(parseFloat(e.target.value))}
          className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-cyan-500"
          aria-label="CLV threshold"
        />
      </div>

      <div className="p-6 space-y-6">
        {/* ROI Charts Grid — 4 charts in 2x2, then 1 full-width */}
        {summaryLoading ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {Array.from({ length: 4 }).map((_, i) => (
              <SkeletonCard key={i} variant="chart" height={220} />
            ))}
          </div>
        ) : hasSummaryData ? (
          <>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
                <h3 className="text-xs uppercase tracking-wider text-slate-400 mb-3">ROI by Surface</h3>
                <RoiBarChart
                  data={surfaceData}
                  dimension="surface"
                  onBarClick={(value) => handleBarClick('surface', value)}
                  activeFilter={chartFilter?.dimension === 'surface' ? chartFilter.value : undefined}
                />
              </div>
              <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
                <h3 className="text-xs uppercase tracking-wider text-slate-400 mb-3">ROI by Tournament Level</h3>
                <RoiBarChart
                  data={tourneyLevelData}
                  dimension="tourney_level"
                  onBarClick={(value) => handleBarClick('tourney_level', value)}
                  activeFilter={chartFilter?.dimension === 'tourney_level' ? chartFilter.value : undefined}
                />
              </div>
              <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
                <h3 className="text-xs uppercase tracking-wider text-slate-400 mb-3">ROI by Year</h3>
                <RoiBarChart
                  data={yearData}
                  dimension="year"
                  onBarClick={(value) => handleBarClick('year', value)}
                  activeFilter={chartFilter?.dimension === 'year' ? chartFilter.value : undefined}
                />
              </div>
              <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
                <h3 className="text-xs uppercase tracking-wider text-slate-400 mb-3">ROI by EV Bucket</h3>
                <RoiBarChart
                  data={evBucketData}
                  dimension="ev_bucket"
                  onBarClick={(value) => handleBarClick('ev_bucket', value)}
                  activeFilter={chartFilter?.dimension === 'ev_bucket' ? chartFilter.value : undefined}
                />
              </div>
            </div>

            {/* Rank Tier and Speed Tier — 2-column row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
                <h3 className="text-xs uppercase tracking-wider text-slate-400 mb-3">ROI by Rank Tier</h3>
                <RoiBarChart
                  data={rankTierData}
                  dimension="rank_tier"
                  onBarClick={(value) => handleBarClick('rank_tier', value)}
                  activeFilter={chartFilter?.dimension === 'rank_tier' ? chartFilter.value : undefined}
                />
              </div>
              <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
                <h3 className="text-xs uppercase tracking-wider text-slate-400 mb-3">ROI by Court Speed Tier</h3>
                <RoiBarChart
                  data={speedTierData}
                  dimension="speed_tier"
                  onBarClick={(value) => handleBarClick('speed_tier', value)}
                  activeFilter={chartFilter?.dimension === 'speed_tier' ? chartFilter.value : undefined}
                />
              </div>
            </div>
          </>
        ) : (
          <EmptyState
            heading="No backtest results"
            body="Run a backtest to see ROI breakdowns and bet history. Use the API or CLI to trigger a run."
          />
        )}

        {/* Filter chip */}
        {chartFilter && (
          <div>
            <FilterChip
              label={`${chartFilter.dimension}: ${chartFilter.value}`}
              onDismiss={() => {
                setChartFilter(null);
                setPage(0);
              }}
            />
          </div>
        )}

        {/* Threshold Sensitivity Section */}
        <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xs uppercase tracking-wider text-slate-400">Threshold Sensitivity</h3>
            <button
              onClick={handleRunSweep}
              disabled={runBacktest.isPending || !!sweepJobId}
              className="text-xs px-3 py-1.5 rounded bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/40 disabled:opacity-50 border border-cyan-500/30"
            >
              {sweepJobId ? 'Running...' : 'Run Threshold Sweep'}
            </button>
          </div>
          {sweepJobId && (
            <p className="text-sm text-slate-400 text-center py-4">Running sweep, please wait...</p>
          )}
          {sweepResults && sweepResults.length > 0 && (
            <>
              <div className="overflow-x-auto mb-4">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-700">
                      <th className="px-2 py-1 text-left text-xs text-slate-500 uppercase">Threshold</th>
                      <th className="px-2 py-1 text-left text-xs text-slate-500 uppercase">Bets</th>
                      <th className="px-2 py-1 text-left text-xs text-slate-500 uppercase">ROI</th>
                      <th className="px-2 py-1 text-left text-xs text-slate-500 uppercase">Sharpe</th>
                      <th className="px-2 py-1 text-left text-xs text-slate-500 uppercase">Max DD</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sweepResults.map((r) => (
                      <tr key={r.clv_threshold} className="border-b border-slate-700/50">
                        <td className="px-2 py-1 text-slate-300">{r.clv_threshold.toFixed(2)}</td>
                        <td className="px-2 py-1 text-slate-300">{r.bets_placed}</td>
                        <td className={`px-2 py-1 font-medium ${r.roi >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {(r.roi * 100).toFixed(1)}%
                        </td>
                        <td className="px-2 py-1 text-slate-300">{r.sharpe.toFixed(2)}</td>
                        <td className="px-2 py-1 text-red-400">{(r.max_drawdown * 100).toFixed(1)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="h-[300px]">
                <ResponsiveLine
                  data={[{
                    id: 'ROI',
                    data: sweepResults.map(r => ({ x: r.clv_threshold, y: r.roi * 100 }))
                  }]}
                  margin={{ top: 20, right: 30, bottom: 50, left: 60 }}
                  xScale={{ type: 'linear', min: 0, max: 0.12 }}
                  yScale={{ type: 'linear', stacked: false }}
                  axisBottom={{
                    legend: 'CLV Threshold',
                    legendOffset: 36,
                    legendPosition: 'middle' as const,
                    format: (v: number) => v.toFixed(2),
                  }}
                  axisLeft={{
                    legend: 'ROI (%)',
                    legendOffset: -50,
                    legendPosition: 'middle' as const,
                  }}
                  colors={['#22c55e']}
                  pointSize={8}
                  pointColor="#22c55e"
                  pointBorderWidth={2}
                  pointBorderColor="#0f172a"
                  enableGridX={false}
                  theme={{
                    text: { fill: '#94a3b8' },
                    axis: {
                      ticks: { text: { fill: '#94a3b8' } },
                      legend: { text: { fill: '#94a3b8' } },
                    },
                    grid: { line: { stroke: '#1e293b' } },
                    crosshair: { line: { stroke: '#475569' } },
                    tooltip: {
                      container: { background: '#1e293b', color: '#e2e8f0', borderRadius: '8px' },
                    },
                  }}
                  useMesh={true}
                />
              </div>
            </>
          )}
        </div>

        {/* Bet History Table */}
        <div className="rounded-lg overflow-hidden border border-slate-700">
          <BetHistoryTable
            data={betsData?.data ?? []}
            total={betsData?.total ?? 0}
            offset={page * 20}
            limit={20}
            onPageChange={(newOffset) => setPage(Math.floor(newOffset / 20))}
            isLoading={betsLoading}
          />
        </div>
      </div>
    </div>
  );
}
