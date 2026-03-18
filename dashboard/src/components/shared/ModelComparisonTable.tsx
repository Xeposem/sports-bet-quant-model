import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
import type { ModelMetrics } from '../../api/types';

interface ModelComparisonTableProps {
  models: ModelMetrics[];
  selectedModel: string | null;
  onSelectModel: (modelVersion: string) => void;
}

function formatDecimal(value: number | null, decimals: number): string {
  if (value === null || value === undefined) return 'N/A';
  return value.toFixed(decimals);
}

function formatRoi(value: number | null): string {
  if (value === null || value === undefined) return 'N/A';
  return `${value.toFixed(2)}%`;
}

function brierColor(value: number | null): string {
  if (value === null) return 'text-slate-500';
  if (value <= 0.20) return 'text-green-500';
  if (value <= 0.25) return 'text-amber-500';
  return 'text-red-500';
}

function roiColor(value: number | null): string {
  if (value === null) return 'text-slate-500';
  if (value > 0) return 'text-green-500';
  if (value < 0) return 'text-red-500';
  return 'text-slate-100';
}

export function ModelComparisonTable({
  models,
  selectedModel,
  onSelectModel,
}: ModelComparisonTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="text-xs uppercase tracking-wider text-slate-400">Model</TableHead>
          <TableHead className="text-xs uppercase tracking-wider text-slate-400">Brier Score</TableHead>
          <TableHead className="text-xs uppercase tracking-wider text-slate-400">Log Loss</TableHead>
          <TableHead className="text-xs uppercase tracking-wider text-slate-400">Calibration</TableHead>
          <TableHead className="text-xs uppercase tracking-wider text-slate-400">Kelly ROI</TableHead>
          <TableHead className="text-xs uppercase tracking-wider text-slate-400">Flat ROI</TableHead>
          <TableHead className="text-xs uppercase tracking-wider text-slate-400">Total Bets</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {models.map((model, idx) => {
          const isSelected = model.model_version === selectedModel;
          const rowClass = isSelected
            ? 'bg-slate-700 border-l-2 border-green-500 cursor-pointer'
            : `${idx % 2 === 0 ? 'bg-slate-800' : 'bg-slate-900'} hover:bg-slate-700 cursor-pointer`;

          return (
            <TableRow
              key={model.model_version}
              role="row"
              className={rowClass}
              onClick={() => onSelectModel(model.model_version)}
              aria-selected={isSelected}
              aria-label={isSelected ? `Selected model: ${model.model_version}` : undefined}
            >
              <TableCell className="text-slate-100 font-medium">{model.model_version}</TableCell>
              <TableCell className={model.brier_score === null ? 'text-slate-500' : brierColor(model.brier_score)}>
                {formatDecimal(model.brier_score, 4)}
              </TableCell>
              <TableCell className={model.log_loss === null ? 'text-slate-500' : 'text-slate-100'}>
                {formatDecimal(model.log_loss, 4)}
              </TableCell>
              <TableCell className={model.calibration_quality === null ? 'text-slate-500' : 'text-slate-100'}>
                {model.calibration_quality ?? 'N/A'}
              </TableCell>
              <TableCell className={roiColor(model.kelly_roi)}>
                {formatRoi(model.kelly_roi)}
              </TableCell>
              <TableCell className={roiColor(model.flat_roi)}>
                {formatRoi(model.flat_roi)}
              </TableCell>
              <TableCell className="text-slate-100">{model.total_bets}</TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
