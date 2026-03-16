"""
Score parsing, match classification, retirement normalization, and date conversion.

Exports:
- MATCH_DTYPES: dict — full 44-column dtype map for Sackmann CSV loading
- classify_match(score) -> str
- normalize_retirement_stats(row) -> pd.Series
- clean_match_dataframe(df) -> tuple[pd.DataFrame, pd.DataFrame]
"""
import pandas as pd

# ---------------------------------------------------------------------------
# Full 44-column dtype map for pd.read_csv on Sackmann atp_matches_YYYY.csv
# ---------------------------------------------------------------------------
MATCH_DTYPES = {
    "tourney_id": str,
    "tourney_name": str,
    "surface": str,
    "draw_size": "Int64",
    "tourney_level": str,
    "tourney_date": str,          # Keep as str; parse to ISO date manually
    "match_num": "Int64",
    "winner_id": "Int64",
    "winner_seed": "Int64",       # nullable — many unseeded players
    "winner_entry": str,
    "winner_name": str,
    "winner_hand": str,
    "winner_ht": "Int64",         # nullable
    "winner_ioc": str,
    "winner_age": float,
    "winner_rank": "Int64",       # nullable — unranked players possible
    "winner_rank_points": "Int64",
    "loser_id": "Int64",
    "loser_seed": "Int64",
    "loser_entry": str,
    "loser_name": str,
    "loser_hand": str,
    "loser_ht": "Int64",
    "loser_ioc": str,
    "loser_age": float,
    "loser_rank": "Int64",
    "loser_rank_points": "Int64",
    "score": str,
    "best_of": "Int64",
    "round": str,
    "minutes": "Int64",           # nullable — not always recorded
    "w_ace": "Int64",
    "w_df": "Int64",
    "w_svpt": "Int64",
    "w_1stIn": "Int64",
    "w_1stWon": "Int64",
    "w_2ndWon": "Int64",
    "w_SvGms": "Int64",
    "w_bpSaved": "Int64",
    "w_bpFaced": "Int64",
    "l_ace": "Int64",
    "l_df": "Int64",
    "l_svpt": "Int64",
    "l_1stIn": "Int64",
    "l_1stWon": "Int64",
    "l_2ndWon": "Int64",
    "l_SvGms": "Int64",
    "l_bpSaved": "Int64",
    "l_bpFaced": "Int64",
}

# Serve stat columns used for retirement normalization and stats_missing flag
_SERVE_STAT_COLS = [
    "w_ace", "w_df", "w_svpt", "w_1stIn", "w_1stWon", "w_2ndWon",
    "w_SvGms", "w_bpSaved", "w_bpFaced",
    "l_ace", "l_df", "l_svpt", "l_1stIn", "l_1stWon", "l_2ndWon",
    "l_SvGms", "l_bpSaved", "l_bpFaced",
]

_STATS_MISSING_COLS = ["w_ace", "w_df", "w_svpt", "l_ace", "l_df", "l_svpt"]

# Expected serve games: 12 for best-of-3, 20 for best-of-5
_EXPECTED_SV_GAMES = {3: 12, 5: 20}


def classify_match(score) -> str:
    """
    Classify a match based on its score string.

    Returns one of: 'completed', 'retirement', 'walkover', 'default', 'unknown'.

    Args:
        score: Raw score value from Sackmann CSV. May be None or non-string.
    """
    if not isinstance(score, str) or not score.strip():
        return "unknown"
    score_upper = score.strip().upper()
    if score_upper == "W/O":
        return "walkover"
    if score_upper == "DEF":
        return "default"
    if score_upper.endswith("RET"):
        return "retirement"
    return "completed"


def normalize_retirement_stats(row: pd.Series) -> pd.Series:
    """
    Scale serve statistics proportionally for a retirement match.

    Uses (expected_sv_games / played_sv_games) as a scale factor to project
    truncated stats to a full-match estimate. The stats_normalized flag should
    be set separately by the caller.

    Args:
        row: A single match row as a pd.Series.

    Returns:
        The row with stat columns scaled, or the original row if played_sv_games==0.
    """
    best_of = row.get("best_of")
    expected_sv_games = _EXPECTED_SV_GAMES.get(best_of, 12)

    w_sv = row.get("w_SvGms") or 0
    l_sv = row.get("l_SvGms") or 0
    played_sv_games = (w_sv if w_sv and not _is_na(w_sv) else 0) + \
                      (l_sv if l_sv and not _is_na(l_sv) else 0)

    if played_sv_games == 0:
        return row  # Cannot normalize — no serve game data

    scale = expected_sv_games / played_sv_games
    row = row.copy()
    for col in _SERVE_STAT_COLS:
        val = row.get(col)
        if val is not None and not _is_na(val):
            row[col] = round(val * scale)
    return row


def _is_na(val) -> bool:
    """Return True if value is NaN/NA (handles pandas NA and float nan)."""
    try:
        return pd.isna(val)
    except (TypeError, ValueError):
        return False


def clean_match_dataframe(df: pd.DataFrame):
    """
    Clean a raw Sackmann match DataFrame.

    Steps:
    1. Normalize column set to exactly MATCH_DTYPES keys (fills missing with NaN)
    2. Convert tourney_date from YYYYMMDD string to ISO "YYYY-MM-DD"
    3. Classify match type via classify_match
    4. Set retirement_flag=1 for retirements
    5. Split excluded = walkovers + defaults
    6. Normalize retirement stats, set stats_normalized=1
    7. Add tour="ATP" column
    8. Compute stats_missing flag

    Args:
        df: Raw DataFrame loaded from a Sackmann CSV.

    Returns:
        (cleaned_df, excluded_df): cleaned_df has no walkovers/defaults;
        excluded_df contains only walkovers and defaults.
    """
    # 1. Normalize column set
    df = df.reindex(columns=list(MATCH_DTYPES.keys()))

    # 2. Convert tourney_date
    df = df.copy()
    df["tourney_date"] = pd.to_datetime(
        df["tourney_date"].astype(str), format="%Y%m%d", errors="coerce"
    ).dt.strftime("%Y-%m-%d")

    # 3. Classify match types
    df["match_type"] = df["score"].apply(classify_match)

    # 4. Retirement flag
    df["retirement_flag"] = (df["match_type"] == "retirement").astype(int)

    # 5. Separate excluded
    excluded_mask = df["match_type"].isin(["walkover", "default"])
    excluded_df = df[excluded_mask].copy()
    cleaned_df = df[~excluded_mask].copy()

    # 6. Initialize stats_normalized column
    cleaned_df["stats_normalized"] = 0

    # Apply normalization to retirement rows
    retirement_mask = cleaned_df["match_type"] == "retirement"
    if retirement_mask.any():
        normalized_rows = cleaned_df.loc[retirement_mask].apply(
            normalize_retirement_stats, axis=1
        )
        # Update only the numeric stat columns to avoid FutureWarning on dtype mismatch
        for col in _SERVE_STAT_COLS:
            if col in cleaned_df.columns:
                cleaned_df.loc[retirement_mask, col] = normalized_rows[col]
        cleaned_df.loc[retirement_mask, "stats_normalized"] = 1

    # 7. Tour column
    cleaned_df["tour"] = "ATP"

    # 8. stats_missing flag: 1 if all of the 6 key stat columns are NaN
    present_cols = [c for c in _STATS_MISSING_COLS if c in cleaned_df.columns]
    if present_cols:
        cleaned_df["stats_missing"] = cleaned_df[present_cols].isnull().all(axis=1).astype(int)
    else:
        cleaned_df["stats_missing"] = 1

    return cleaned_df, excluded_df
