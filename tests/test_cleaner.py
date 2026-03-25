"""
Tests for src/ingestion/cleaner.py

Covers:
- classify_match for all score types
- normalize_retirement_stats scaling logic
- clean_match_dataframe: date conversion, columns added, exclusions, flags
- MATCH_DTYPES has 44 expected keys
"""
import pytest
import pandas as pd

from src.ingestion.cleaner import (
    classify_match,
    normalize_retirement_stats,
    clean_match_dataframe,
    MATCH_DTYPES,
)


class TestClassifyMatch:
    def test_completed_normal_score(self):
        assert classify_match("6-3 6-4") == "completed"

    def test_completed_three_sets(self):
        assert classify_match("6-3 3-6 6-1") == "completed"

    def test_retirement_ret_suffix(self):
        assert classify_match("6-3 3-6 6-1 RET") == "retirement"

    def test_retirement_lowercase(self):
        assert classify_match("6-3 ret") == "retirement"

    def test_walkover_exact(self):
        assert classify_match("W/O") == "walkover"

    def test_walkover_lowercase(self):
        assert classify_match("w/o") == "walkover"

    def test_default_exact(self):
        assert classify_match("DEF") == "default"

    def test_default_lowercase(self):
        assert classify_match("def") == "default"

    def test_empty_string_returns_unknown(self):
        assert classify_match("") == "unknown"

    def test_none_returns_unknown(self):
        assert classify_match(None) == "unknown"

    def test_whitespace_only_returns_unknown(self):
        assert classify_match("   ") == "unknown"

    def test_retirement_partial_score_with_ret(self):
        """Score with just one set and RET is still a retirement."""
        assert classify_match("6-2 RET") == "retirement"


class TestNormalizeRetirementStats:
    def _make_row(self, best_of, w_SvGms, l_SvGms, w_ace=10, l_ace=5):
        """Helper to build a pd.Series with the fields needed for normalization."""
        data = {
            "best_of": best_of,
            "w_SvGms": w_SvGms,
            "l_SvGms": l_SvGms,
            "w_ace": w_ace,
            "w_df": 2,
            "w_svpt": 50,
            "w_1stIn": 30,
            "w_1stWon": 20,
            "w_2ndWon": 10,
            "w_bpSaved": 1,
            "w_bpFaced": 2,
            "l_ace": l_ace,
            "l_df": 1,
            "l_svpt": 30,
            "l_1stIn": 18,
            "l_1stWon": 12,
            "l_2ndWon": 6,
            "l_bpSaved": 0,
            "l_bpFaced": 3,
        }
        return pd.Series(data)

    def test_scales_stats_proportionally_best_of_3(self):
        """
        best_of=3: expected=12 serve games.
        If w_SvGms=4, l_SvGms=4 -> played=8, scale=12/8=1.5
        w_ace=10 -> 10 * 1.5 = 15
        """
        row = self._make_row(best_of=3, w_SvGms=4, l_SvGms=4, w_ace=10, l_ace=4)
        result = normalize_retirement_stats(row)
        assert result["w_ace"] == round(10 * 1.5)  # 15
        assert result["l_ace"] == round(4 * 1.5)   # 6

    def test_scales_stats_proportionally_best_of_5(self):
        """
        best_of=5: expected=20 serve games.
        If w_SvGms=5, l_SvGms=5 -> played=10, scale=20/10=2.0
        w_ace=5 -> 5 * 2.0 = 10
        """
        row = self._make_row(best_of=5, w_SvGms=5, l_SvGms=5, w_ace=5, l_ace=2)
        result = normalize_retirement_stats(row)
        assert result["w_ace"] == 10
        assert result["l_ace"] == 4

    def test_returns_row_unchanged_when_played_sv_games_zero(self):
        """If played_sv_games=0 (no serve game data), row is returned unchanged."""
        row = self._make_row(best_of=3, w_SvGms=0, l_SvGms=0, w_ace=10)
        result = normalize_retirement_stats(row)
        assert result["w_ace"] == 10

    def test_handles_none_sv_games(self):
        """If w_SvGms or l_SvGms is None/NaN, treat as 0 (no served games)."""
        import numpy as np
        data = {
            "best_of": 3,
            "w_SvGms": None,
            "l_SvGms": None,
            "w_ace": 10,
            "w_df": 2,
            "w_svpt": 50,
            "w_1stIn": 30,
            "w_1stWon": 20,
            "w_2ndWon": 10,
            "w_bpSaved": 1,
            "w_bpFaced": 2,
            "l_ace": 5,
            "l_df": 1,
            "l_svpt": 30,
            "l_1stIn": 18,
            "l_1stWon": 12,
            "l_2ndWon": 6,
            "l_bpSaved": 0,
            "l_bpFaced": 3,
        }
        row = pd.Series(data)
        result = normalize_retirement_stats(row)
        # played_sv_games = 0 -> return unchanged
        assert result["w_ace"] == 10

    def test_skips_nan_stat_columns(self):
        """Stats that are NaN are not scaled (no division on NaN)."""
        import numpy as np
        row = self._make_row(best_of=3, w_SvGms=4, l_SvGms=4)
        row["w_ace"] = None  # NaN stat
        result = normalize_retirement_stats(row)
        # NaN stays NaN — not scaled to a number
        assert result["w_ace"] is None or pd.isna(result["w_ace"])


class TestCleanMatchDataframe:
    def test_converts_tourney_date_to_iso(self, sample_match_df):
        """tourney_date is converted from YYYYMMDD string to YYYY-MM-DD."""
        cleaned, _ = clean_match_dataframe(sample_match_df)
        for date_val in cleaned["tourney_date"]:
            import re
            assert re.match(r"^\d{4}-\d{2}-\d{2}$", str(date_val)), (
                f"Expected ISO date, got '{date_val}'"
            )

    def test_adds_match_type_column(self, sample_match_df):
        """clean_match_dataframe adds 'match_type' column."""
        cleaned, _ = clean_match_dataframe(sample_match_df)
        assert "match_type" in cleaned.columns

    def test_adds_retirement_flag_column(self, sample_match_df):
        """clean_match_dataframe adds 'retirement_flag' column."""
        cleaned, _ = clean_match_dataframe(sample_match_df)
        assert "retirement_flag" in cleaned.columns

    def test_adds_stats_normalized_column(self, sample_match_df):
        """clean_match_dataframe adds 'stats_normalized' column."""
        cleaned, _ = clean_match_dataframe(sample_match_df)
        assert "stats_normalized" in cleaned.columns

    def test_adds_stats_missing_column(self, sample_match_df):
        """clean_match_dataframe adds 'stats_missing' column."""
        cleaned, _ = clean_match_dataframe(sample_match_df)
        assert "stats_missing" in cleaned.columns

    def test_adds_tour_column(self, sample_match_df):
        """clean_match_dataframe adds 'tour' column with value 'ATP'."""
        cleaned, _ = clean_match_dataframe(sample_match_df)
        assert "tour" in cleaned.columns
        assert (cleaned["tour"] == "ATP").all()

    def test_excludes_walkovers(self, sample_match_df):
        """Walkover rows are excluded from cleaned output."""
        cleaned, excluded = clean_match_dataframe(sample_match_df)
        walkover_in_cleaned = cleaned[cleaned["score"].str.upper() == "W/O"] if "score" in cleaned.columns else pd.DataFrame()
        assert len(walkover_in_cleaned) == 0, "Walkovers should be excluded from cleaned df"

    def test_excludes_defaults(self, sample_match_df):
        """Default rows are excluded from cleaned output."""
        cleaned, excluded = clean_match_dataframe(sample_match_df)
        default_in_cleaned = cleaned[cleaned["score"].str.upper() == "DEF"] if "score" in cleaned.columns else pd.DataFrame()
        assert len(default_in_cleaned) == 0, "Defaults should be excluded from cleaned df"

    def test_excluded_df_contains_walkovers_and_defaults(self, sample_match_df):
        """The excluded DataFrame contains walkovers and defaults."""
        _, excluded = clean_match_dataframe(sample_match_df)
        assert len(excluded) == 2  # 1 walkover + 1 default in sample_match_df

    def test_sets_stats_normalized_for_retirement_rows(self, sample_match_df):
        """Retirement rows have stats_normalized=1."""
        cleaned, _ = clean_match_dataframe(sample_match_df)
        retirement_rows = cleaned[cleaned["match_type"] == "retirement"]
        assert len(retirement_rows) >= 1
        assert (retirement_rows["stats_normalized"] == 1).all()

    def test_sets_stats_missing_flag(self, sample_match_df):
        """Rows where all of [w_ace, w_df, w_svpt, l_ace, l_df, l_svpt] are NaN get stats_missing=1."""
        cleaned, _ = clean_match_dataframe(sample_match_df)
        # Row 4 in sample_match_df (match_num=5) has all stats NaN
        missing_rows = cleaned[cleaned["stats_missing"] == 1]
        assert len(missing_rows) >= 1

    def test_retirement_flag_set_for_retirement_matches(self, sample_match_df):
        """Rows classified as retirement have retirement_flag=1."""
        cleaned, _ = clean_match_dataframe(sample_match_df)
        retirement_rows = cleaned[cleaned["match_type"] == "retirement"]
        assert (retirement_rows["retirement_flag"] == 1).all()

    def test_non_retirement_rows_have_flag_zero(self, sample_match_df):
        """Non-retirement rows have retirement_flag=0."""
        cleaned, _ = clean_match_dataframe(sample_match_df)
        non_ret = cleaned[cleaned["match_type"] != "retirement"]
        assert (non_ret["retirement_flag"] == 0).all()


class TestMatchDtypes:
    def test_has_44_keys(self):
        """MATCH_DTYPES has exactly 49 expected column keys.

        The ATP match CSV has 49 columns as documented in RESEARCH.md
        Pattern 1. The plan references '44' but the actual dtype map has 49 entries.
        """
        assert len(MATCH_DTYPES) == 49

    def test_contains_required_columns(self):
        """MATCH_DTYPES contains all expected column names."""
        required = [
            "tourney_id", "tourney_name", "surface", "draw_size", "tourney_level",
            "tourney_date", "match_num", "winner_id", "winner_seed", "winner_entry",
            "winner_name", "winner_hand", "winner_ht", "winner_ioc", "winner_age",
            "winner_rank", "winner_rank_points", "loser_id", "loser_seed", "loser_entry",
            "loser_name", "loser_hand", "loser_ht", "loser_ioc", "loser_age",
            "loser_rank", "loser_rank_points", "score", "best_of", "round", "minutes",
            "w_ace", "w_df", "w_svpt", "w_1stIn", "w_1stWon", "w_2ndWon", "w_SvGms",
            "w_bpSaved", "w_bpFaced", "l_ace", "l_df", "l_svpt", "l_1stIn",
            "l_1stWon", "l_2ndWon", "l_SvGms", "l_bpSaved", "l_bpFaced",
        ]
        missing = [col for col in required if col not in MATCH_DTYPES]
        assert not missing, f"MATCH_DTYPES missing keys: {missing}"
