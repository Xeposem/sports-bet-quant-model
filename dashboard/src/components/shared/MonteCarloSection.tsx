import { useState } from 'react';
import { KpiCard } from './KpiCard';
import { EmptyState } from './EmptyState';
import { FanChart } from '../charts/FanChart';
import { HistogramChart } from '../charts/HistogramChart';
import { useSimulationResult, useRunSimulation } from '../../hooks/useSimulation';
import type { MonteCarloRequest } from '../../api/types';

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatCurrency(value: number): string {
  return `$${value.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function formatSharpe(value: number): string {
  return value.toFixed(2);
}

export function MonteCarloSection() {
  const [params, setParams] = useState<MonteCarloRequest>({
    n_seasons: 1000,
    initial_bankroll: 1000,
    kelly_fraction: 0.25,
    ev_threshold: 0,
  });

  const simulationResult = useSimulationResult();
  const runSimulation = useRunSimulation();

  const result = runSimulation.data ?? simulationResult.data;
  const hasResults = result != null;
  const isPending = runSimulation.isPending;

  function handleRun() {
    runSimulation.mutate(params);
  }

  return (
    <div className="mt-12">
      <h2 className="text-xl font-semibold text-slate-100 mb-6">Monte Carlo Simulation</h2>

      {/* Parameter form */}
      <div className="flex flex-wrap gap-4 items-end mb-6">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400 uppercase tracking-wider">Seasons</label>
          <input
            type="number"
            min={1000}
            max={10000}
            step={1000}
            value={params.n_seasons}
            onChange={(e) => setParams((p) => ({ ...p, n_seasons: Number(e.target.value) }))}
            className="bg-slate-800 border border-slate-700 text-slate-100 rounded px-3 py-2 w-28 focus:outline-none focus:border-slate-500"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400 uppercase tracking-wider">Initial Bankroll ($)</label>
          <input
            type="number"
            min={100}
            value={params.initial_bankroll}
            onChange={(e) => setParams((p) => ({ ...p, initial_bankroll: Number(e.target.value) }))}
            className="bg-slate-800 border border-slate-700 text-slate-100 rounded px-3 py-2 w-32 focus:outline-none focus:border-slate-500"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400 uppercase tracking-wider">Kelly Fraction</label>
          <select
            value={params.kelly_fraction}
            onChange={(e) => setParams((p) => ({ ...p, kelly_fraction: Number(e.target.value) }))}
            className="bg-slate-800 border border-slate-700 text-slate-100 rounded px-3 py-2 w-28 focus:outline-none focus:border-slate-500"
          >
            <option value={0.1}>0.1x</option>
            <option value={0.25}>0.25x</option>
            <option value={0.5}>0.5x</option>
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400 uppercase tracking-wider">EV Threshold (%)</label>
          <input
            type="number"
            min={0}
            max={20}
            step={0.5}
            value={params.ev_threshold}
            onChange={(e) => setParams((p) => ({ ...p, ev_threshold: Number(e.target.value) }))}
            className="bg-slate-800 border border-slate-700 text-slate-100 rounded px-3 py-2 w-28 focus:outline-none focus:border-slate-500"
          />
        </div>

        <button
          onClick={handleRun}
          disabled={isPending}
          className="bg-green-500 hover:bg-green-600 disabled:opacity-60 text-white font-semibold px-4 py-2 rounded flex items-center gap-2"
        >
          {isPending && (
            <span className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
          )}
          Run Simulation
        </button>
      </div>

      {/* Results or empty state */}
      {!hasResults && !isPending ? (
        <EmptyState
          heading="No simulation results"
          body="Configure parameters above and click Run Simulation to see P(ruin), expected bankroll, and confidence bands."
        />
      ) : hasResults ? (
        <>
          {/* KPI cards */}
          <div className="flex flex-wrap gap-6 mb-8">
            <KpiCard
              label="P(Ruin)"
              value={formatPercent(result.p_ruin)}
              trend={result.p_ruin > 0.1 ? 'negative' : 'positive'}
            />
            <KpiCard
              label="Expected Terminal"
              value={formatCurrency(result.expected_terminal)}
              trend={result.expected_terminal >= result.initial_bankroll ? 'positive' : 'negative'}
            />
            <KpiCard
              label="Sharpe Ratio"
              value={formatSharpe(result.sharpe_ratio)}
              trend={result.sharpe_ratio >= 1 ? 'positive' : result.sharpe_ratio < 0 ? 'negative' : 'neutral'}
            />
          </div>

          {/* Charts row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div>
              <p className="text-sm text-slate-400 mb-2">Bankroll Paths (Percentile Fan)</p>
              <FanChart paths={result.paths} />
            </div>
            <div>
              <p className="text-sm text-slate-400 mb-2">Terminal Bankroll Distribution</p>
              <HistogramChart
                distribution={result.terminal_distribution}
                initialBankroll={result.initial_bankroll}
              />
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
