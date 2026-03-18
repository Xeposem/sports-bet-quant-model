import { useRef, useEffect } from 'react';
import { createChart, BaselineSeries, ColorType } from 'lightweight-charts';
import type { BankrollPoint } from '../../api/types';
import { EmptyState } from '../shared/EmptyState';

interface BankrollChartProps {
  data: BankrollPoint[];
  initialBankroll: number;
  onDateClick?: (date: string) => void;
}

export function BankrollChart({ data, initialBankroll, onDateClick }: BankrollChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || data.length === 0) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 280,
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
      timeScale: { borderColor: '#334155' },
      rightPriceScale: { borderColor: '#334155' },
    });

    const series = chart.addSeries(BaselineSeries, {
      baseValue: { type: 'price', price: initialBankroll },
      topLineColor: '#22c55e',
      topFillColor1: 'rgba(34, 197, 94, 0.1)',
      topFillColor2: 'rgba(34, 197, 94, 0.02)',
      bottomLineColor: '#ef4444',
      bottomFillColor1: 'rgba(239, 68, 68, 0.02)',
      bottomFillColor2: 'rgba(239, 68, 68, 0.1)',
      lineWidth: 2,
    });

    series.setData(data.map(p => ({ time: p.date, value: p.bankroll })));

    chart.subscribeClick((param) => {
      if (param.time && onDateClick) {
        onDateClick(String(param.time));
      }
    });

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
  }, [data, initialBankroll, onDateClick]);

  if (data.length === 0) {
    return (
      <EmptyState
        heading="Bankroll curve unavailable"
        body="No backtest data found. Run a backtest to see the equity curve."
      />
    );
  }

  return (
    <div
      ref={containerRef}
      role="img"
      aria-label="Bankroll equity curve over time"
      style={{ height: 280, width: '100%' }}
    />
  );
}
