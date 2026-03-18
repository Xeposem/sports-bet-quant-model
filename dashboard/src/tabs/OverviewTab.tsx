import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { BankrollChart } from '../components/charts/BankrollChart';
import { CalibrationChart } from '../components/charts/CalibrationChart';
import { KpiCard } from '../components/shared/KpiCard';
import { SkeletonCard } from '../components/shared/SkeletonCard';
import { EmptyState } from '../components/shared/EmptyState';
import { useBankroll } from '../hooks/useBankroll';
import { useBacktestSummary } from '../hooks/useBacktest';
import { useCalibration } from '../hooks/useCalibration';
import { useSignals } from '../hooks/useSignals';

function formatPercent(value: number | undefined | null): string {
  if (value == null) return '—';
  return `${(value * 100).toFixed(1)}%`;
}

function formatCurrency(value: number | undefined | null): string {
  if (value == null) return '—';
  const sign = value >= 0 ? '+' : '';
  return `${sign}$${Math.abs(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatBrier(value: number | undefined | null): string {
  if (value == null) return '—';
  return value.toFixed(4);
}

export function OverviewTab() {
  const bankroll = useBankroll();
  const backtest = useBacktestSummary();
  const calibration = useCalibration();
  const signals = useSignals();

  const isLoading =
    bankroll.isLoading || backtest.isLoading || calibration.isLoading || signals.isLoading;
  const isError =
    bankroll.isError || backtest.isError || calibration.isError || signals.isError;

  if (isError) {
    return (
      <div className="p-6" role="alert">
        <p className="text-red-500">
          Failed to load data. Check that the API server is running on port 8000.
        </p>
      </div>
    );
  }

  // KPI values
  const roi = backtest.data?.kelly_roi;
  const pnl = backtest.data?.total_pnl_kelly;
  const brierScore = null as number | null; // will come from models hook — placeholder per spec
  const signalCount = signals.data?.data?.length ?? 0;

  const roiTrend =
    roi == null ? 'neutral' : roi > 0 ? 'positive' : roi < 0 ? 'negative' : 'neutral';
  const pnlTrend =
    pnl == null ? 'neutral' : pnl > 0 ? 'positive' : pnl < 0 ? 'negative' : 'neutral';

  return (
    <div className="p-6 space-y-8">
      {/* KPI row */}
      <div className="flex flex-wrap gap-8">
        {isLoading ? (
          <>
            <SkeletonCard variant="kpi" />
            <SkeletonCard variant="kpi" />
            <SkeletonCard variant="kpi" />
            <SkeletonCard variant="kpi" />
          </>
        ) : (
          <>
            <KpiCard label="ROI" value={formatPercent(roi)} trend={roiTrend} />
            <KpiCard label="Total P&L" value={formatCurrency(pnl)} trend={pnlTrend} />
            <KpiCard label="Brier Score" value={formatBrier(brierScore)} trend="neutral" />
            <KpiCard
              label="Active Signals"
              value={String(signalCount)}
              trend="neutral"
            />
          </>
        )}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Bankroll chart — 2/3 width */}
        <div className="lg:col-span-2">
          <Card className="bg-slate-800 border-slate-700">
            <CardHeader className="pb-2">
              <CardTitle className="text-base text-slate-100">Bankroll Equity Curve</CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <SkeletonCard variant="chart" height={280} />
              ) : (
                <BankrollChart
                  data={bankroll.data?.curve ?? []}
                  initialBankroll={bankroll.data?.initial ?? 1000}
                />
              )}
            </CardContent>
          </Card>
        </div>

        {/* Calibration chart — 1/3 width */}
        <div className="lg:col-span-1">
          <Card className="bg-slate-800 border-slate-700">
            <CardHeader className="pb-2">
              <CardTitle className="text-base text-slate-100">Calibration</CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <SkeletonCard variant="chart" height={240} />
              ) : (
                <CalibrationChart
                  bins={calibration.data?.bins ?? []}
                  modelVersion={calibration.data?.model_version}
                />
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* DASH-04 Monte Carlo placeholder */}
      <Card className="bg-slate-800 border-slate-700">
        <CardHeader>
          <CardTitle className="text-base text-slate-100">Monte Carlo Simulation</CardTitle>
        </CardHeader>
        <CardContent>
          <EmptyState
            heading="Simulation not yet available"
            body="Monte Carlo bankroll simulation will be available after Phase 9."
          />
        </CardContent>
      </Card>
    </div>
  );
}
