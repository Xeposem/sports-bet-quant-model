"""
Tests for src/ingestion/tml_id_mapper.py

Covers:
- build_id_map creates tml_id_map table with correct rows
- build_id_map assigns synthetic IDs starting at 900000
- build_id_map is idempotent (calling twice produces same result)
- resolve_player_id returns integer >= 900000 for known TML ID
- resolve_player_id raises KeyError for unknown TML ID
- normalise_tml_dataframe replaces string winner_id/loser_id with integers
- normalise_tml_dataframe preserves all other columns unchanged
"""
import sqlite3
import io
import pandas as pd
import pytest

from src.ingestion.tml_id_mapper import (
    build_id_map,
    resolve_player_id,
    normalise_tml_dataframe,
)


# --- Fixtures ---

ATP_DATABASE_CSV_CONTENT = (
    '"id","player","atpname","birthdate","weight","height","turnedpro","birthplace","coaches","hand","backhand","ioc"\n'
    '"CD85","Pablo Carreno Busta","Carreno Busta P.",19910712,80,188,2009,"Gijon, Spain","Samuel Lopez",R,2H,ESP\n'
    '"S0H2","Alexander Shevchenko","Shevchenko A.",19980902,82,188,2017,"Moscow, Russia","",R,1H,RUS\n'
)


@pytest.fixture
def player_csv(tmp_path):
    """Write a minimal ATP_Database.csv to tmp_path and return its path."""
    csv_path = tmp_path / "ATP_Database.csv"
    csv_path.write_text(ATP_DATABASE_CSV_CONTENT, encoding="utf-8")
    return str(csv_path)


@pytest.fixture
def mem_conn():
    """Provide an in-memory SQLite connection."""
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()


# --- build_id_map tests ---

class TestBuildIdMap:
    def test_build_id_map_creates_table(self, player_csv, mem_conn):
        """build_id_map creates tml_id_map table with correct number of rows."""
        build_id_map(player_csv, mem_conn)
        count = mem_conn.execute("SELECT COUNT(*) FROM tml_id_map").fetchone()[0]
        assert count == 2

    def test_build_id_map_starts_at_900000(self, player_csv, mem_conn):
        """build_id_map assigns synthetic player_id starting at 900000."""
        build_id_map(player_csv, mem_conn)
        min_id = mem_conn.execute("SELECT MIN(player_id) FROM tml_id_map").fetchone()[0]
        assert min_id == 900000

    def test_build_id_map_assigns_sequential_ids(self, player_csv, mem_conn):
        """build_id_map assigns sequential IDs (900000, 900001, ...) for each player."""
        build_id_map(player_csv, mem_conn)
        ids = [row[0] for row in mem_conn.execute("SELECT player_id FROM tml_id_map ORDER BY player_id")]
        assert ids == [900000, 900001]

    def test_build_id_map_idempotent(self, player_csv, mem_conn):
        """Calling build_id_map twice with same CSV produces same rows and IDs."""
        build_id_map(player_csv, mem_conn)
        # Store first-pass assignments
        first_pass = dict(mem_conn.execute("SELECT tml_id, player_id FROM tml_id_map").fetchall())

        build_id_map(player_csv, mem_conn)
        # Row count unchanged
        count = mem_conn.execute("SELECT COUNT(*) FROM tml_id_map").fetchone()[0]
        assert count == 2

        # IDs unchanged
        second_pass = dict(mem_conn.execute("SELECT tml_id, player_id FROM tml_id_map").fetchall())
        assert first_pass == second_pass

    def test_build_id_map_stores_name(self, player_csv, mem_conn):
        """build_id_map stores player name in the name column."""
        build_id_map(player_csv, mem_conn)
        row = mem_conn.execute(
            "SELECT name FROM tml_id_map WHERE tml_id=?", ("CD85",)
        ).fetchone()
        assert row is not None
        assert row[0] is not None and len(row[0]) > 0

    def test_build_id_map_returns_inserted_count(self, player_csv, mem_conn):
        """build_id_map returns the number of newly inserted rows."""
        inserted = build_id_map(player_csv, mem_conn)
        assert inserted == 2

    def test_build_id_map_returns_zero_on_second_call(self, player_csv, mem_conn):
        """build_id_map returns 0 when no new rows are inserted (idempotent call)."""
        build_id_map(player_csv, mem_conn)
        inserted = build_id_map(player_csv, mem_conn)
        assert inserted == 0


# --- resolve_player_id tests ---

class TestResolvePlayerId:
    def test_resolve_player_id_returns_integer(self, player_csv, mem_conn):
        """resolve_player_id returns an int >= 900000 for a known TML ID."""
        build_id_map(player_csv, mem_conn)
        result = resolve_player_id("CD85", mem_conn)
        assert isinstance(result, int)
        assert result >= 900000

    def test_resolve_player_id_raises_on_unknown(self, player_csv, mem_conn):
        """resolve_player_id raises KeyError with the unknown ID in the message."""
        build_id_map(player_csv, mem_conn)
        with pytest.raises(KeyError, match="UNKNOWN"):
            resolve_player_id("UNKNOWN", mem_conn)

    def test_resolve_player_id_different_players_get_different_ids(self, player_csv, mem_conn):
        """Two different TML IDs resolve to different synthetic integers."""
        build_id_map(player_csv, mem_conn)
        id1 = resolve_player_id("CD85", mem_conn)
        id2 = resolve_player_id("S0H2", mem_conn)
        assert id1 != id2


# --- normalise_tml_dataframe tests ---

class TestNormaliseTMLDataframe:
    def _sample_df(self):
        return pd.DataFrame({
            "tourney_name": ["United Cup"],
            "surface": ["Hard"],
            "score": ["6-2 6-1"],
            "winner_id": ["CD85"],
            "loser_id": ["S0H2"],
        })

    def test_normalise_tml_dataframe_replaces_ids(self, player_csv, mem_conn):
        """normalise_tml_dataframe replaces string winner_id/loser_id with integers >= 900000."""
        build_id_map(player_csv, mem_conn)
        df = self._sample_df()
        result = normalise_tml_dataframe(df, mem_conn)
        # Use numbers.Integral to match both int and np.int64
        import numbers
        assert isinstance(result["winner_id"].iloc[0], numbers.Integral)
        assert isinstance(result["loser_id"].iloc[0], numbers.Integral)
        assert result["winner_id"].iloc[0] >= 900000
        assert result["loser_id"].iloc[0] >= 900000

    def test_normalise_tml_dataframe_preserves_other_columns(self, player_csv, mem_conn):
        """normalise_tml_dataframe does not alter columns other than winner_id and loser_id."""
        build_id_map(player_csv, mem_conn)
        df = self._sample_df()
        result = normalise_tml_dataframe(df, mem_conn)
        assert result["tourney_name"].iloc[0] == "United Cup"
        assert result["surface"].iloc[0] == "Hard"
        assert result["score"].iloc[0] == "6-2 6-1"

    def test_normalise_tml_dataframe_does_not_mutate_input(self, player_csv, mem_conn):
        """normalise_tml_dataframe returns a copy and does not mutate the input DataFrame."""
        build_id_map(player_csv, mem_conn)
        df = self._sample_df()
        original_winner_id = df["winner_id"].iloc[0]
        normalise_tml_dataframe(df, mem_conn)
        # Input should be unchanged
        assert df["winner_id"].iloc[0] == original_winner_id
