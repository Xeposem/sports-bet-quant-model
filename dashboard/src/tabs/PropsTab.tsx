import { useState, useRef, useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { KpiCard } from '../components/shared/KpiCard';
import { SkeletonCard } from '../components/shared/SkeletonCard';
import { EmptyState } from '../components/shared/EmptyState';
import { CalibrationChart } from '../components/charts/CalibrationChart';
import { PmfChart } from '../components/charts/PmfChart';
import { useProps, useSubmitPropLine, usePropAccuracy, useScanPropScreenshot } from '../hooks/useProps';
import { PropScanPreview } from '../components/shared/PropScanPreview';
import type { PropPrediction, CalibrationBin, PropScanResponse } from '../api/types';

type StatType = 'aces' | 'games_won' | 'double_faults';
type Direction = 'over' | 'under';

function formatHitRate(value: number | null | undefined): string {
  if (value == null) return '--';
  return `${(value * 100).toFixed(1)}%`;
}

function getHitRateTrend(value: number | null | undefined): 'positive' | 'negative' | 'neutral' {
  if (value == null) return 'neutral';
  if (value >= 0.55) return 'positive';
  if (value < 0.45) return 'negative';
  return 'neutral';
}

function getValueBadge(pHit: number | null): {
  text: string;
  className: string;
} {
  if (pHit == null) return { text: 'No Value', className: 'bg-slate-700 text-slate-400 border-slate-600' };
  if (pHit > 0.60) return { text: 'Value', className: 'bg-green-500/20 text-green-400 border-green-500/30' };
  if (pHit >= 0.55) return { text: 'Marginal', className: 'bg-amber-500/20 text-amber-400 border-amber-500/30' };
  return { text: 'No Value', className: 'bg-slate-700 text-slate-400 border-slate-600' };
}

function getPHitColorClass(pHit: number | null): string {
  if (pHit == null) return 'text-slate-400';
  if (pHit > 0.60) return 'text-green-500';
  if (pHit >= 0.55) return 'text-amber-500';
  return 'text-slate-400';
}

// Rolling hit rate bar chart using @nivo/bar (fallback since @nivo/line is not installed)
import { ResponsiveBar } from '@nivo/bar';
import { nivoTheme } from '../components/charts/nivoTheme';

function RollingHitRateChart({
  data,
}: {
  data: Array<{ date: string; hit_rate: number }>;
}) {
  if (!data || data.length === 0) {
    return (
      <EmptyState
        heading="No resolved props yet"
        body="Hit rate tracking begins once prop predictions have been compared to actual match results."
      />
    );
  }

  const barData = data.map((d) => ({
    date: d.date,
    hit_rate: +(d.hit_rate * 100).toFixed(1),
  }));

  return (
    <div
      style={{ height: 220 }}
      role="img"
      aria-label="Rolling 30-day prop hit rate"
    >
      <ResponsiveBar
        data={barData}
        keys={['hit_rate']}
        indexBy="date"
        theme={nivoTheme}
        colors={['#22c55e']}
        margin={{ top: 10, right: 20, bottom: 50, left: 50 }}
        axisBottom={{
          tickRotation: -30,
          legend: 'Date',
          legendPosition: 'middle',
          legendOffset: 42,
        }}
        axisLeft={{
          legend: 'Hit Rate (%)',
          legendPosition: 'middle',
          legendOffset: -42,
        }}
        enableLabel={false}
        enableGridX={false}
        maxValue={100}
        minValue={0}
        markers={[
          {
            axis: 'y',
            value: 55,
            lineStyle: { stroke: '#f59e0b', strokeWidth: 1, strokeDasharray: '4,4' },
            legend: '55% threshold',
            legendPosition: 'top-right',
            textStyle: { fill: '#64748b', fontSize: 10 },
          },
        ]}
      />
    </div>
  );
}

export function PropsTab() {
  const today = new Date().toISOString().split('T')[0];

  const [playerName, setPlayerName] = useState('');
  const [statType, setStatType] = useState<StatType | ''>('');
  const [lineValue, setLineValue] = useState('');
  const [direction, setDirection] = useState<Direction | ''>('');
  const [matchDate, setMatchDate] = useState(today);
  const [currentPrediction, setCurrentPrediction] = useState<PropPrediction | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const scanMutation = useScanPropScreenshot();
  const [scanResult, setScanResult] = useState<PropScanResponse | null>(null);

  const propsQuery = useProps();
  const accuracyQuery = usePropAccuracy();
  const submitMutation = useSubmitPropLine();

  const handleUpload = async (file: File) => {
    try {
      const result = await scanMutation.mutateAsync(file);
      if (result.cards.length === 0) {
        toast.error('No ATP player props found in screenshot');
      } else {
        setScanResult(result);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to scan screenshot');
    }
  };

  useEffect(() => {
    const handler = (e: ClipboardEvent) => {
      const item = Array.from(e.clipboardData?.items ?? [])
        .find(i => i.type.startsWith('image/'));
      if (item) {
        const blob = item.getAsFile();
        if (blob) handleUpload(blob);
      }
    };
    window.addEventListener('paste', handler);
    return () => window.removeEventListener('paste', handler);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const isAccuracyLoading = accuracyQuery.isLoading;
  const accuracyData = accuracyQuery.data;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!statType || !direction) {
      toast.error('Please select a stat type and direction.');
      return;
    }
    const entry = {
      player_name: playerName,
      stat_type: statType as StatType,
      line_value: parseFloat(lineValue),
      direction: direction as Direction,
      match_date: matchDate,
    };
    submitMutation.mutate(entry, {
      onSuccess: () => {
        // After the prop line is stored, refetch predictions and find the match
        propsQuery.refetch().then((res) => {
          const predictions = res.data?.data ?? [];
          const match = predictions.find(
            (p) =>
              p.player_name.toLowerCase() === playerName.toLowerCase() &&
              p.stat_type === statType &&
              p.match_date === matchDate,
          );
          if (match) {
            setCurrentPrediction(match);
          } else {
            toast.info('Prop line saved. No prediction available yet for this player/date — run the prop models first.');
          }
        });
      },
      onError: (err) => {
        const msg = err.message ?? '';
        if (msg.includes('404') || msg.toLowerCase().includes('not found')) {
          toast.error('Player not found. Try a more complete name (e.g., \'Novak Djokovic\' instead of \'Djokovic\').');
        } else {
          toast.error('Could not submit prop line. Check the player name and try again.');
        }
      },
    });
  };

  // Map prop accuracy calibration bins to CalibrationChart format
  const calibrationBins: CalibrationBin[] = (accuracyData?.calibration_bins ?? []).map((b) => ({
    midpoint: b.predicted_p,
    empirical_freq: b.actual_hit_rate,
    n_samples: b.n,
  }));

  const badge = getValueBadge(currentPrediction?.p_hit ?? null);
  const pHitColorClass = getPHitColorClass(currentPrediction?.p_hit ?? null);

  return (
    <div className="p-6 space-y-8">

      {/* Section A: KPI Row */}
      <div className="flex flex-wrap gap-8">
        {isAccuracyLoading ? (
          <>
            <SkeletonCard variant="kpi" />
            <SkeletonCard variant="kpi" />
            <SkeletonCard variant="kpi" />
            <SkeletonCard variant="kpi" />
            <SkeletonCard variant="kpi" />
          </>
        ) : (
          <>
            <KpiCard
              label="Hit Rate"
              value={formatHitRate(accuracyData?.overall_hit_rate)}
              trend={getHitRateTrend(accuracyData?.overall_hit_rate)}
            />
            <KpiCard
              label="Aces Hit Rate"
              value={formatHitRate(accuracyData?.hit_rate_by_stat?.aces)}
              trend={getHitRateTrend(accuracyData?.hit_rate_by_stat?.aces)}
            />
            <KpiCard
              label="Games Won Hit Rate"
              value={formatHitRate(accuracyData?.hit_rate_by_stat?.games_won)}
              trend={getHitRateTrend(accuracyData?.hit_rate_by_stat?.games_won)}
            />
            <KpiCard
              label="Double Faults Hit Rate"
              value={formatHitRate(accuracyData?.hit_rate_by_stat?.double_faults)}
              trend={getHitRateTrend(accuracyData?.hit_rate_by_stat?.double_faults)}
            />
            <KpiCard
              label="Props Tracked"
              value={String(accuracyData?.total_tracked ?? 0)}
              trend="neutral"
            />
          </>
        )}
      </div>

      {/* Screenshot Scanner Section */}
      <Card className="border-slate-700 bg-slate-800/50">
        <CardHeader>
          <CardTitle className="text-lg">Scan PrizePicks Screenshot</CardTitle>
        </CardHeader>
        <CardContent>
          {scanResult ? (
            <PropScanPreview
              cards={scanResult.cards}
              onClose={() => setScanResult(null)}
            />
          ) : (
            <div className="flex flex-col items-center gap-4 py-6">
              <p className="text-sm text-slate-400">
                Upload a PrizePicks screenshot or paste from clipboard (Ctrl+V)
              </p>
              <input
                type="file"
                accept="image/*"
                ref={fileInputRef}
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleUpload(file);
                }}
              />
              <Button
                onClick={() => fileInputRef.current?.click()}
                disabled={scanMutation.isPending}
                variant="outline"
                className="border-slate-600"
              >
                {scanMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Scanning...
                  </>
                ) : (
                  'Scan PrizePicks Screenshot'
                )}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Section B: Prop Entry Form */}
      <Card className="bg-slate-800 border-slate-700">
        <CardHeader>
          <CardTitle className="text-base text-slate-100">Enter Prop Line</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit}>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 items-end">

              {/* Player Name */}
              <div>
                <label htmlFor="player-name" className="block text-xs text-slate-400 mb-1">
                  Player Name
                </label>
                <input
                  id="player-name"
                  type="text"
                  required
                  minLength={2}
                  placeholder="e.g. Carlos Alcaraz"
                  value={playerName}
                  onChange={(e) => setPlayerName(e.target.value)}
                  className="w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
                />
              </div>

              {/* Stat Type */}
              <div>
                <label className="block text-xs text-slate-400 mb-1">
                  Stat Type
                </label>
                <Select
                  value={statType}
                  onValueChange={(val) => setStatType(val as StatType)}
                  required
                >
                  <SelectTrigger className="w-full border-slate-700 bg-slate-900 text-slate-100">
                    <SelectValue placeholder="Select stat type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="aces">Aces</SelectItem>
                    <SelectItem value="games_won">Games Won</SelectItem>
                    <SelectItem value="double_faults">Double Faults</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Line Value */}
              <div>
                <label htmlFor="line-value" className="block text-xs text-slate-400 mb-1">
                  Line Value
                </label>
                <input
                  id="line-value"
                  type="number"
                  required
                  min={0}
                  step="0.5"
                  placeholder="e.g. 5.5"
                  value={lineValue}
                  onChange={(e) => setLineValue(e.target.value)}
                  className="w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
                />
              </div>

              {/* Direction */}
              <div>
                <label className="block text-xs text-slate-400 mb-1">
                  Direction
                </label>
                <Select
                  value={direction}
                  onValueChange={(val) => setDirection(val as Direction)}
                  required
                >
                  <SelectTrigger className="w-full border-slate-700 bg-slate-900 text-slate-100">
                    <SelectValue placeholder="Over / Under" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="over">Over</SelectItem>
                    <SelectItem value="under">Under</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Match Date */}
              <div>
                <label htmlFor="match-date" className="block text-xs text-slate-400 mb-1">
                  Match Date
                </label>
                <input
                  id="match-date"
                  type="date"
                  required
                  value={matchDate}
                  onChange={(e) => setMatchDate(e.target.value)}
                  className="w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
                />
              </div>
            </div>

            <div className="mt-4">
              <Button
                type="submit"
                disabled={submitMutation.isPending}
                aria-busy={submitMutation.isPending}
                className="w-full sm:w-auto"
              >
                {submitMutation.isPending && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Check Prop
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Section C: PMF Chart */}
      <Card className="bg-slate-800 border-slate-700">
        <CardHeader>
          <div className="flex items-center gap-2">
            <CardTitle className="text-base text-slate-100">Predicted Distribution</CardTitle>
            {currentPrediction?.p_hit != null && (
              <Badge className={badge.className}>{badge.text}</Badge>
            )}
          </div>
          {currentPrediction?.p_hit != null && (
            <p className={`text-2xl font-semibold ${pHitColorClass} mt-1`}>
              P({currentPrediction.direction ?? 'over'}): {(currentPrediction.p_hit * 100).toFixed(1)}%
            </p>
          )}
        </CardHeader>
        <CardContent>
          {currentPrediction && currentPrediction.pmf && currentPrediction.pmf.length > 0 ? (
            <div style={{ height: 240 }}>
              <PmfChart
                pmf={currentPrediction.pmf}
                threshold={currentPrediction.line_value ?? 0}
                direction={currentPrediction.direction ?? 'over'}
                mu={currentPrediction.mu}
                playerName={currentPrediction.player_name}
                statType={currentPrediction.stat_type}
              />
            </div>
          ) : (
            <EmptyState
              heading="No props tracked yet"
              body="Enter a prop line above to see the predicted distribution and value rating."
            />
          )}
        </CardContent>
      </Card>

      {/* Section D: Accuracy Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Rolling 30-Day Hit Rate */}
        <div className="lg:col-span-2">
          <Card className="bg-slate-800 border-slate-700">
            <CardHeader className="pb-2">
              <CardTitle className="text-base text-slate-100">30-Day Hit Rate</CardTitle>
            </CardHeader>
            <CardContent>
              {isAccuracyLoading ? (
                <SkeletonCard variant="chart" height={220} />
              ) : (
                <RollingHitRateChart data={accuracyData?.rolling_30d ?? []} />
              )}
            </CardContent>
          </Card>
        </div>

        {/* Prop Calibration Scatter */}
        <div className="lg:col-span-1">
          <Card className="bg-slate-800 border-slate-700">
            <CardHeader className="pb-2">
              <CardTitle className="text-base text-slate-100">Prop Calibration</CardTitle>
            </CardHeader>
            <CardContent>
              {isAccuracyLoading ? (
                <SkeletonCard variant="chart" height={240} />
              ) : (
                <CalibrationChart
                  bins={calibrationBins}
                  modelVersion="props_v1"
                />
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Error state for props query */}
      {propsQuery.isError && (
        <div className="p-6" role="alert">
          <p className="text-red-500">
            Failed to load props. Check that the API server is running on port 8000.
          </p>
        </div>
      )}
    </div>
  );
}
