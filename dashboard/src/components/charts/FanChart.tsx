import { useRef, useEffect } from 'react';
import { createChart, LineSeries, ColorType } from 'lightweight-charts';
import type { UTCTimestamp } from 'lightweight-charts';
import type { PercentilePath } from '../../api/types';

interface FanChartProps {
  paths: PercentilePath[];
}

const BASE_TIMESTAMP: UTCTimestamp = 1704067200 as UTCTimestamp; // Jan 1 2024

function syntheticTime(step: number): UTCTimestamp {
  return (BASE_TIMESTAMP + step * 86400) as UTCTimestamp;
}

export function FanChart({ paths }: FanChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || paths.length === 0) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 300,
      layout: {
        background: { type: ColorType.Solid, color: '#0f172a' },
        textColor: '#64748b',
      },
      grid: {
        vertLines: { color: '#1e293b' },
        horzLines: { color: '#1e293b' },
      },
      crosshair: {
        horzLine: { color: '#64748b' },
        vertLine: { color: '#64748b' },
      },
      timeScale: { borderColor: '#334155', visible: false },
      rightPriceScale: { borderColor: '#334155' },
    });

    // p50 median — bright white, solid
    const p50Series = chart.addSeries(LineSeries, {
      color: '#f8fafc',
      lineWidth: 2,
    });
    p50Series.setData(paths.map((p) => ({ time: syntheticTime(p.step), value: p.p50 })));

    // p75 — green 60% opacity
    const p75Series = chart.addSeries(LineSeries, {
      color: 'rgba(34,197,94,0.6)',
      lineWidth: 1,
    });
    p75Series.setData(paths.map((p) => ({ time: syntheticTime(p.step), value: p.p75 })));

    // p25 — green 60% opacity
    const p25Series = chart.addSeries(LineSeries, {
      color: 'rgba(34,197,94,0.6)',
      lineWidth: 1,
    });
    p25Series.setData(paths.map((p) => ({ time: syntheticTime(p.step), value: p.p25 })));

    // p95 — green 30% opacity, dashed (LineStyle.Dashed = 2)
    const p95Series = chart.addSeries(LineSeries, {
      color: 'rgba(34,197,94,0.3)',
      lineWidth: 1,
      lineStyle: 2,
    });
    p95Series.setData(paths.map((p) => ({ time: syntheticTime(p.step), value: p.p95 })));

    // p5 — green 30% opacity, dashed
    const p5Series = chart.addSeries(LineSeries, {
      color: 'rgba(34,197,94,0.3)',
      lineWidth: 1,
      lineStyle: 2,
    });
    p5Series.setData(paths.map((p) => ({ time: syntheticTime(p.step), value: p.p5 })));

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [paths]);

  return (
    <div
      ref={containerRef}
      className="h-[300px] w-full"
      role="img"
      aria-label="Monte Carlo fan chart showing bankroll percentile paths"
    />
  );
}
