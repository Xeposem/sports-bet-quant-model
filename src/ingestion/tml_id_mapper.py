"""
TML player ID translation layer and DataFrame normalisation.

Translates TML alphanumeric player IDs (e.g. "CD85") to synthetic integer IDs
starting at 900000, stored persistently in a tml_id_map SQLite table.
Synthetic IDs start at 900000 to avoid collisions with Sackmann IDs (~max 230000).

Exports:
- build_id_map(player_csv_path, conn) -> int
- resolve_player_id(tml_id, conn) -> int
- normalise_tml_dataframe(df, conn) -> pd.DataFrame
"""
import sqlite3

import pandas as pd


def _get_next_synthetic_id(conn: sqlite3.Connection) -> int:
    """
    Return the next available synthetic integer ID for a new TML player.

    If the tml_id_map table is empty, returns 900000. Otherwise returns MAX(player_id) + 1.
    """
    row = conn.execute("SELECT MAX(player_id) FROM tml_id_map").fetchone()
    if row[0] is None:
        return 900000
    return row[0] + 1


def build_id_map(player_csv_path: str, conn: sqlite3.Connection) -> int:
    """
    Load ATP_Database.csv and populate the tml_id_map table.

    Creates the table if it does not exist. Idempotent: existing rows are never
    overwritten; only new TML IDs get synthetic integers assigned.

    Synthetic IDs start at 900000 and are assigned sequentially. This places them
    well above the Sackmann player_id range (~230000 max) to prevent collisions.

    Args:
        player_csv_path: Path to ATP_Database.csv downloaded by tml_downloader.
        conn: Open SQLite connection.

    Returns:
        Number of newly inserted rows.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tml_id_map (
            tml_id    TEXT PRIMARY KEY,
            player_id INTEGER UNIQUE,
            name      TEXT
        )
        """
    )

    df = pd.read_csv(player_csv_path, dtype=str)
    next_id = _get_next_synthetic_id(conn)
    inserted = 0

    for _, row in df.iterrows():
        tml_id = row.get("id", "")
        if tml_id is None:
            continue
        tml_id = str(tml_id).strip()
        if not tml_id:
            continue

        name = row.get("atpname") or row.get("player", "") or ""

        existing = conn.execute(
            "SELECT player_id FROM tml_id_map WHERE tml_id=?", (tml_id,)
        ).fetchone()

        if not existing:
            conn.execute(
                "INSERT OR IGNORE INTO tml_id_map (tml_id, player_id, name) VALUES (?,?,?)",
                (tml_id, next_id, str(name).strip()),
            )
            next_id += 1
            inserted += 1

    conn.commit()
    return inserted


def resolve_player_id(tml_id: str, conn: sqlite3.Connection) -> int:
    """
    Return the synthetic integer player_id for a TML alphanumeric ID.

    Args:
        tml_id: TML alphanumeric player ID (e.g. "CD85").
        conn: Open SQLite connection with tml_id_map populated.

    Returns:
        Synthetic integer player_id (>= 900000).

    Raises:
        KeyError: If tml_id is not present in tml_id_map.
    """
    row = conn.execute(
        "SELECT player_id FROM tml_id_map WHERE tml_id=?", (tml_id,)
    ).fetchone()
    if row:
        return row[0]
    raise KeyError(f"TML player ID '{tml_id}' not found in tml_id_map")


def normalise_tml_dataframe(df: pd.DataFrame, conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Replace TML alphanumeric winner_id/loser_id with synthetic integer IDs.

    Translates each value in winner_id and loser_id columns via resolve_player_id.
    NaN/None values are preserved as None. All other columns are unchanged.

    Args:
        df: DataFrame loaded from a TML match CSV (winner_id/loser_id are strings).
        conn: Open SQLite connection with tml_id_map populated.

    Returns:
        New DataFrame with winner_id/loser_id replaced by integers.
    """
    df = df.copy()
    df["winner_id"] = df["winner_id"].apply(
        lambda x: resolve_player_id(str(x).strip(), conn) if pd.notna(x) else None
    )
    df["loser_id"] = df["loser_id"].apply(
        lambda x: resolve_player_id(str(x).strip(), conn) if pd.notna(x) else None
    )
    return df
