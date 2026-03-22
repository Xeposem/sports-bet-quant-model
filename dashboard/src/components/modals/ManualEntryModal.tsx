import { useState } from 'react';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  useOddsList,
  useSubmitOdds,
  useDeleteOdds,
  usePropLinesList,
  useDeletePropLine,
} from '@/hooks/useManualEntry';
import { useSubmitPropLine } from '@/hooks/useProps';
import type { OddsEntry } from '@/api/types';

interface ManualEntryModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type EntryType = 'odds' | 'prop';

const EMPTY_ODDS = {
  player_a: '',
  player_b: '',
  odds_a: '',
  odds_b: '',
  match_date: '',
  bookmaker: 'pinnacle',
};

const EMPTY_PROP = {
  player_name: '',
  stat_type: 'aces' as const,
  line_value: '',
  direction: 'over' as const,
  match_date: '',
};

const PAGE_SIZE = 10;

export function ManualEntryModal({ open, onOpenChange }: ManualEntryModalProps) {
  const [entryType, setEntryType] = useState<EntryType>('odds');
  const [oddsForm, setOddsForm] = useState(EMPTY_ODDS);
  const [propForm, setPropForm] = useState(EMPTY_PROP);
  const [oddsPendingDeleteId, setOddsPendingDeleteId] = useState<string | null>(null);
  const [propPendingDeleteId, setPropPendingDeleteId] = useState<number | null>(null);
  const [oddsPage, setOddsPage] = useState(0);
  const [propPage, setPropPage] = useState(0);

  const oddsList = useOddsList();
  const propLinesList = usePropLinesList();
  const submitOdds = useSubmitOdds();
  const deleteOdds = useDeleteOdds();
  const submitPropLine = useSubmitPropLine();
  const deletePropLine = useDeletePropLine();

  function hasUnsavedInput(): boolean {
    if (entryType === 'odds') {
      return Object.entries(oddsForm).some(([k, v]) => k !== 'bookmaker' && v !== '');
    }
    return Object.entries(propForm).some(([k, v]) =>
      k !== 'stat_type' && k !== 'direction' && v !== ''
    );
  }

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen && hasUnsavedInput()) {
      if (!window.confirm('Discard changes?')) return;
    }
    onOpenChange(nextOpen);
  }

  function switchType(type: EntryType) {
    setEntryType(type);
    setOddsForm(EMPTY_ODDS);
    setPropForm(EMPTY_PROP);
  }

  function handleOddsSubmit(e: React.FormEvent) {
    e.preventDefault();
    const entry: OddsEntry = {
      player_a: oddsForm.player_a,
      player_b: oddsForm.player_b,
      odds_a: parseFloat(oddsForm.odds_a),
      odds_b: parseFloat(oddsForm.odds_b),
      match_date: oddsForm.match_date,
      bookmaker: oddsForm.bookmaker,
    };
    submitOdds.mutate(entry, {
      onSuccess: () => {
        toast('Match odds saved');
        setOddsForm(EMPTY_ODDS);
      },
      onError: (err) => {
        toast.error(
          err.message?.includes('404') || err.message?.toLowerCase().includes('not found')
            ? 'Player not found. Check player names and try again.'
            : 'Failed to save entry. Check that player names are valid and try again.'
        );
      },
    });
  }

  function handlePropSubmit(e: React.FormEvent) {
    e.preventDefault();
    submitPropLine.mutate(
      {
        player_name: propForm.player_name,
        stat_type: propForm.stat_type,
        line_value: parseFloat(propForm.line_value),
        direction: propForm.direction,
        match_date: propForm.match_date,
      },
      {
        onSuccess: () => {
          toast('Prop line saved');
          setPropForm(EMPTY_PROP);
        },
        onError: () => {
          toast.error('Failed to save prop line. Check the player name and try again.');
        },
      }
    );
  }

  const inputClass =
    'w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent';
  const labelClass = 'block text-xs text-slate-400 mb-1';

  const oddsRows = oddsList.data?.data ?? [];
  const propRows = propLinesList.data?.data ?? [];

  const oddsPageRows = oddsRows.slice(oddsPage * PAGE_SIZE, (oddsPage + 1) * PAGE_SIZE);
  const propPageRows = propRows.slice(propPage * PAGE_SIZE, (propPage + 1) * PAGE_SIZE);

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="bg-slate-900 border-slate-700 text-slate-100 max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-slate-100">Enter Data</DialogTitle>
        </DialogHeader>

        {/* Type toggle */}
        <div className="flex bg-slate-800 rounded p-1 gap-1">
          <button
            type="button"
            onClick={() => switchType('odds')}
            className={`flex-1 rounded px-3 py-1.5 text-sm font-medium transition-colors ${
              entryType === 'odds'
                ? 'bg-green-500 text-white'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Match Odds
          </button>
          <button
            type="button"
            onClick={() => switchType('prop')}
            className={`flex-1 rounded px-3 py-1.5 text-sm font-medium transition-colors ${
              entryType === 'prop'
                ? 'bg-green-500 text-white'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Prop Line
          </button>
        </div>

        {/* Match Odds form */}
        {entryType === 'odds' && (
          <form onSubmit={handleOddsSubmit} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={labelClass}>Player A</label>
                <input
                  type="text"
                  required
                  placeholder="Player A name"
                  value={oddsForm.player_a}
                  onChange={(e) => setOddsForm({ ...oddsForm, player_a: e.target.value })}
                  className={inputClass}
                />
              </div>
              <div>
                <label className={labelClass}>Player B</label>
                <input
                  type="text"
                  required
                  placeholder="Player B name"
                  value={oddsForm.player_b}
                  onChange={(e) => setOddsForm({ ...oddsForm, player_b: e.target.value })}
                  className={inputClass}
                />
              </div>
              <div>
                <label className={labelClass}>Odds A</label>
                <input
                  type="number"
                  required
                  step="0.01"
                  min="1.01"
                  placeholder="Decimal odds A"
                  value={oddsForm.odds_a}
                  onChange={(e) => setOddsForm({ ...oddsForm, odds_a: e.target.value })}
                  className={inputClass}
                />
              </div>
              <div>
                <label className={labelClass}>Odds B</label>
                <input
                  type="number"
                  required
                  step="0.01"
                  min="1.01"
                  placeholder="Decimal odds B"
                  value={oddsForm.odds_b}
                  onChange={(e) => setOddsForm({ ...oddsForm, odds_b: e.target.value })}
                  className={inputClass}
                />
              </div>
              <div>
                <label className={labelClass}>Match Date</label>
                <input
                  type="date"
                  required
                  value={oddsForm.match_date}
                  onChange={(e) => setOddsForm({ ...oddsForm, match_date: e.target.value })}
                  className={inputClass}
                />
              </div>
              <div>
                <label className={labelClass}>Bookmaker</label>
                <input
                  type="text"
                  required
                  value={oddsForm.bookmaker}
                  onChange={(e) => setOddsForm({ ...oddsForm, bookmaker: e.target.value })}
                  className={inputClass}
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={submitOdds.isPending}
              className="bg-green-500 hover:bg-green-600 text-white font-semibold px-4 py-2 rounded disabled:opacity-50"
            >
              Save Entry
            </button>
          </form>
        )}

        {/* Prop Line form */}
        {entryType === 'prop' && (
          <form onSubmit={handlePropSubmit} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={labelClass}>Player Name</label>
                <input
                  type="text"
                  required
                  placeholder="Player name"
                  value={propForm.player_name}
                  onChange={(e) => setPropForm({ ...propForm, player_name: e.target.value })}
                  className={inputClass}
                />
              </div>
              <div>
                <label className={labelClass}>Stat Type</label>
                <select
                  required
                  value={propForm.stat_type}
                  onChange={(e) =>
                    setPropForm({
                      ...propForm,
                      stat_type: e.target.value as 'aces' | 'games_won' | 'double_faults',
                    })
                  }
                  className={inputClass}
                >
                  <option value="aces">Aces</option>
                  <option value="games_won">Games Won</option>
                  <option value="double_faults">Double Faults</option>
                </select>
              </div>
              <div>
                <label className={labelClass}>Line Value</label>
                <input
                  type="number"
                  required
                  step="0.5"
                  min="0"
                  placeholder="Line value"
                  value={propForm.line_value}
                  onChange={(e) => setPropForm({ ...propForm, line_value: e.target.value })}
                  className={inputClass}
                />
              </div>
              <div>
                <label className={labelClass}>Direction</label>
                <select
                  required
                  value={propForm.direction}
                  onChange={(e) =>
                    setPropForm({
                      ...propForm,
                      direction: e.target.value as 'over' | 'under',
                    })
                  }
                  className={inputClass}
                >
                  <option value="over">Over</option>
                  <option value="under">Under</option>
                </select>
              </div>
              <div>
                <label className={labelClass}>Match Date</label>
                <input
                  type="date"
                  required
                  value={propForm.match_date}
                  onChange={(e) => setPropForm({ ...propForm, match_date: e.target.value })}
                  className={inputClass}
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={submitPropLine.isPending}
              className="bg-green-500 hover:bg-green-600 text-white font-semibold px-4 py-2 rounded disabled:opacity-50"
            >
              Save Entry
            </button>
          </form>
        )}

        {/* CRUD Table: Entered Odds */}
        <div className="mt-4 space-y-2">
          <h3 className="text-sm font-semibold text-slate-300">Entered Odds</h3>
          {oddsRows.length === 0 ? (
            <div className="text-slate-500 text-sm py-3">
              <p className="font-medium">No entries yet</p>
              <p>Add match odds or prop lines using the form above.</p>
            </div>
          ) : (
            <>
              <table className="w-full text-xs text-slate-300">
                <thead>
                  <tr className="border-b border-slate-700 text-slate-400">
                    <th className="text-left py-1.5 pr-2">Bookmaker</th>
                    <th className="text-left py-1.5 pr-2">Odds A</th>
                    <th className="text-left py-1.5 pr-2">Odds B</th>
                    <th className="text-left py-1.5 pr-2">Date</th>
                    <th className="text-left py-1.5">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {oddsPageRows.map((row) => {
                    const key = `${row.tourney_id}-${row.match_num}`;
                    const isPending = oddsPendingDeleteId === key;
                    return (
                      <tr key={key} className="border-b border-slate-800">
                        <td className="py-1.5 pr-2">{row.bookmaker}</td>
                        <td className="py-1.5 pr-2">{row.decimal_odds_a}</td>
                        <td className="py-1.5 pr-2">{row.decimal_odds_b}</td>
                        <td className="py-1.5 pr-2">{row.imported_at?.slice(0, 10)}</td>
                        <td className="py-1.5">
                          {isPending ? (
                            <span className="text-slate-400 text-xs">
                              Delete this entry? This cannot be undone.{' '}
                              <button
                                type="button"
                                onClick={() => {
                                  deleteOdds.mutate(
                                    { tourney_id: row.tourney_id, match_num: row.match_num },
                                    { onSuccess: () => setOddsPendingDeleteId(null) }
                                  );
                                }}
                                className="text-red-400 hover:text-red-300 font-medium"
                              >
                                Delete
                              </button>
                              {' / '}
                              <button
                                type="button"
                                onClick={() => setOddsPendingDeleteId(null)}
                                className="text-slate-400 hover:text-slate-200"
                              >
                                Keep Entry
                              </button>
                            </span>
                          ) : (
                            <button
                              type="button"
                              onClick={() => setOddsPendingDeleteId(key)}
                              className="text-red-400 hover:text-red-300 text-xs"
                            >
                              Delete
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {oddsRows.length > PAGE_SIZE && (
                <div className="flex gap-2 pt-1">
                  <button
                    type="button"
                    disabled={oddsPage === 0}
                    onClick={() => setOddsPage((p) => p - 1)}
                    className="text-xs text-slate-400 hover:text-slate-200 disabled:opacity-40"
                  >
                    Prev
                  </button>
                  <span className="text-xs text-slate-500">
                    {oddsPage + 1}/{Math.ceil(oddsRows.length / PAGE_SIZE)}
                  </span>
                  <button
                    type="button"
                    disabled={(oddsPage + 1) * PAGE_SIZE >= oddsRows.length}
                    onClick={() => setOddsPage((p) => p + 1)}
                    className="text-xs text-slate-400 hover:text-slate-200 disabled:opacity-40"
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          )}
        </div>

        {/* CRUD Table: Entered Prop Lines */}
        <div className="mt-4 space-y-2">
          <h3 className="text-sm font-semibold text-slate-300">Entered Prop Lines</h3>
          {propRows.length === 0 ? (
            <div className="text-slate-500 text-sm py-3">
              <p className="font-medium">No entries yet</p>
              <p>Add match odds or prop lines using the form above.</p>
            </div>
          ) : (
            <>
              <table className="w-full text-xs text-slate-300">
                <thead>
                  <tr className="border-b border-slate-700 text-slate-400">
                    <th className="text-left py-1.5 pr-2">Player</th>
                    <th className="text-left py-1.5 pr-2">Stat</th>
                    <th className="text-left py-1.5 pr-2">Line</th>
                    <th className="text-left py-1.5 pr-2">Direction</th>
                    <th className="text-left py-1.5 pr-2">Date</th>
                    <th className="text-left py-1.5">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {propPageRows.map((row) => {
                    const isPending = propPendingDeleteId === row.id;
                    return (
                      <tr key={row.id} className="border-b border-slate-800">
                        <td className="py-1.5 pr-2">{row.player_name}</td>
                        <td className="py-1.5 pr-2">{row.stat_type}</td>
                        <td className="py-1.5 pr-2">{row.line_value}</td>
                        <td className="py-1.5 pr-2">{row.direction}</td>
                        <td className="py-1.5 pr-2">{row.match_date}</td>
                        <td className="py-1.5">
                          {isPending ? (
                            <span className="text-slate-400 text-xs">
                              Delete this entry? This cannot be undone.{' '}
                              <button
                                type="button"
                                onClick={() => {
                                  deletePropLine.mutate(
                                    { lineId: row.id },
                                    { onSuccess: () => setPropPendingDeleteId(null) }
                                  );
                                }}
                                className="text-red-400 hover:text-red-300 font-medium"
                              >
                                Delete
                              </button>
                              {' / '}
                              <button
                                type="button"
                                onClick={() => setPropPendingDeleteId(null)}
                                className="text-slate-400 hover:text-slate-200"
                              >
                                Keep Entry
                              </button>
                            </span>
                          ) : (
                            <button
                              type="button"
                              onClick={() => setPropPendingDeleteId(row.id)}
                              className="text-red-400 hover:text-red-300 text-xs"
                            >
                              Delete
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {propRows.length > PAGE_SIZE && (
                <div className="flex gap-2 pt-1">
                  <button
                    type="button"
                    disabled={propPage === 0}
                    onClick={() => setPropPage((p) => p - 1)}
                    className="text-xs text-slate-400 hover:text-slate-200 disabled:opacity-40"
                  >
                    Prev
                  </button>
                  <span className="text-xs text-slate-500">
                    {propPage + 1}/{Math.ceil(propRows.length / PAGE_SIZE)}
                  </span>
                  <button
                    type="button"
                    disabled={(propPage + 1) * PAGE_SIZE >= propRows.length}
                    onClick={() => setPropPage((p) => p + 1)}
                    className="text-xs text-slate-400 hover:text-slate-200 disabled:opacity-40"
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
