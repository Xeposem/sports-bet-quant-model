import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { BankrollChart } from '../components/charts/BankrollChart';
import { CalibrationChart } from '../components/charts/CalibrationChart';
import { KpiCard } from '../components/shared/KpiCard';
import { SkeletonCard } from '../components/shared/SkeletonCard';
import { EmptyState } from '../components/shared/EmptyState';
import { useBankroll } from '../hooks/useBankroll';
import { useBacktestSummary } from '../hooks/useBacktest';
import { useBacktestBets } from '../hooks/useBacktest';
import { useCalibration } from '../hooks/useCalibration';
import { useSignals } from '../hooks/useSignals';
import { useModels } from '../hooks/useModels';

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
  const [clickedDate, setClickedDate] = useState<string | null>(null);

  const bankroll = useBankroll();
  const backtest = useBacktestSummary();
  const calibration = useCalibration();
  const signals = useSignals();
  const models = useModels();

  const dateBets = useBacktestBets(0, 5, clickedDate ? { tourney_date: clickedDate } : undefined);

  const isLoading =
    bankroll.isLoading || backtest.isLoading || calibration.isLoading || signals.isLoading || models.isLoading;
  const isError =
    bankroll.isError || backtest.isError || calibration.isError || signals.isError || models.isError;

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
  const brierScore = models.data?.data?.[0]?.brier_score ?? null;
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
                <Popover
                  open={clickedDate !== null}
                  onOpenChange={(open) => { if (!open) setClickedDate(null); }}
                >
                  <PopoverTrigger asChild>
                    <div>
                      <BankrollChart
                        data={bankroll.data?.curve ?? []}
                        initialBankroll={bankroll.data?.initial ?? 1000}
                        onDateClick={(date) => setClickedDate(date)}
                      />
                    </div>
                  </PopoverTrigger>
                  <PopoverContent className="bg-slate-800 border-slate-700 text-slate-100 w-80">
                    <div className="space-y-2">
                      <h3 className="text-sm font-semibold text-slate-100">
                        Bets on {clickedDate}
                      </h3>
                      {dateBets.isLoading ? (
                        <p className="text-xs text-slate-500">Loading...</p>
                      ) : dateBets.data?.data && dateBets.data.data.length > 0 ? (
                        <ul className="space-y-1">
                          {dateBets.data.data.slice(0, 5).map((bet) => (
                            <li
                              key={`${bet.tourney_id}-${bet.match_num}-${bet.player_id}`}
                              className="text-xs text-slate-300 flex justify-between"
                            >
                              <span className="truncate max-w-40">{bet.tourney_id}</span>
                              <span className={bet.outcome === 1 ? 'text-green-500' : 'text-red-500'}>
                                {bet.outcome === 1 ? 'W' : 'L'}
                              </span>
                              <span className={bet.pnl_kelly >= 0 ? 'text-green-500' : 'text-red-500'}>
                                {bet.pnl_kelly >= 0 ? '+' : ''}{bet.pnl_kelly.toFixed(2)}
                              </span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-xs text-slate-500">No bets found for this date.</p>
                      )}
                    </div>
                  </PopoverContent>
                </Popover>
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
