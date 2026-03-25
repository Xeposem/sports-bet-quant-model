import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { PropScanCard } from '../../api/types';
import { useSubmitPropLine } from '../../hooks/useProps';

interface ScanRow {
  player_name: string;
  stat_type: 'aces' | 'games_won' | 'double_faults';
  line_value: number;
  direction: 'over' | 'under';
  checked: boolean;
}

interface PropScanPreviewProps {
  cards: PropScanCard[];
  onClose: () => void;
}

function statLabel(statType: string): string {
  if (statType === 'aces') return 'Aces';
  if (statType === 'games_won') return 'Games Won';
  if (statType === 'double_faults') return 'Double Faults';
  return statType;
}

export function PropScanPreview({ cards, onClose }: PropScanPreviewProps) {
  const today = new Date().toISOString().split('T')[0];
  const submitPropLine = useSubmitPropLine();

  const [rows, setRows] = useState<ScanRow[]>(() =>
    cards.flatMap((card) =>
      card.directions.map((direction) => ({
        player_name: card.player_name,
        stat_type: card.stat_type,
        line_value: card.line_value,
        direction,
        checked: true,
      }))
    )
  );
  const [isSubmitting, setIsSubmitting] = useState(false);

  const checkedCount = rows.filter((r) => r.checked).length;
  const allChecked = checkedCount === rows.length;

  const toggleRow = (index: number) => {
    setRows((prev) =>
      prev.map((r, i) => (i === index ? { ...r, checked: !r.checked } : r))
    );
  };

  const toggleAll = () => {
    const next = !allChecked;
    setRows((prev) => prev.map((r) => ({ ...r, checked: next })));
  };

  const handleSubmit = async () => {
    const selected = rows.filter((r) => r.checked);
    if (selected.length === 0) return;

    setIsSubmitting(true);
    let successCount = 0;
    const errors: string[] = [];

    for (const row of selected) {
      try {
        await submitPropLine.mutateAsync({
          player_name: row.player_name,
          stat_type: row.stat_type,
          line_value: row.line_value,
          direction: row.direction,
          match_date: today,
        });
        successCount++;
      } catch (err) {
        errors.push(
          `${row.player_name} ${row.stat_type} ${row.direction}: ${err instanceof Error ? err.message : 'Unknown error'}`
        );
      }
    }

    setIsSubmitting(false);

    if (successCount > 0) {
      toast.success(`Submitted ${successCount} prop line${successCount > 1 ? 's' : ''} successfully`);
    }
    if (errors.length > 0) {
      toast.error(`${errors.length} failed: ${errors[0]}`);
    }

    if (errors.length === 0) {
      onClose();
    }
  };

  return (
    <Card className="border-slate-700 bg-slate-800/50">
      <CardHeader>
        <CardTitle className="text-base text-slate-100">
          Review Extracted Props ({rows.length} row{rows.length !== 1 ? 's' : ''})
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700">
                <th className="pb-2 pr-3 text-left">
                  <input
                    type="checkbox"
                    checked={allChecked}
                    onChange={toggleAll}
                    aria-label="Select all"
                    className="cursor-pointer"
                  />
                </th>
                <th className="pb-2 pr-3 text-left text-xs uppercase tracking-wider text-slate-400">
                  Player Name
                </th>
                <th className="pb-2 pr-3 text-left text-xs uppercase tracking-wider text-slate-400">
                  Stat Type
                </th>
                <th className="pb-2 pr-3 text-left text-xs uppercase tracking-wider text-slate-400">
                  Line
                </th>
                <th className="pb-2 text-left text-xs uppercase tracking-wider text-slate-400">
                  Direction
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr
                  key={i}
                  className={`border-b border-slate-700/50 ${
                    i % 2 === 0 ? 'bg-slate-800/50' : ''
                  }`}
                >
                  <td className="py-2 pr-3">
                    <input
                      type="checkbox"
                      checked={row.checked}
                      onChange={() => toggleRow(i)}
                      aria-label={`Select ${row.player_name} ${row.direction}`}
                      className="cursor-pointer"
                    />
                  </td>
                  <td className="py-2 pr-3 text-slate-100">{row.player_name}</td>
                  <td className="py-2 pr-3 text-slate-300">{statLabel(row.stat_type)}</td>
                  <td className="py-2 pr-3 text-slate-300">{row.line_value}</td>
                  <td className="py-2">
                    {row.direction === 'over' ? (
                      <Badge className="bg-green-500/20 text-green-400 border-green-500/30">
                        Over
                      </Badge>
                    ) : (
                      <Badge className="bg-amber-500/20 text-amber-400 border-amber-500/30">
                        Under
                      </Badge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-4 flex items-center gap-3">
          <Button
            onClick={handleSubmit}
            disabled={checkedCount === 0 || isSubmitting}
            className="bg-green-600 hover:bg-green-700 text-white"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Submitting...
              </>
            ) : (
              `Submit Selected (${checkedCount})`
            )}
          </Button>
          <Button
            variant="outline"
            onClick={onClose}
            disabled={isSubmitting}
            className="border-slate-600 text-slate-300"
          >
            Cancel
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
