"""
PrizePicks screenshot OCR scanner for automatic ATP prop extraction.

Segments a PrizePicks screenshot into individual prop cards, runs Tesseract OCR
on each card, parses player name / line value / stat type / directions, and
fuzzy-matches player names against the ATP players table.

Key exports:
  - scan_image_bytes(image_bytes, db_path) -> dict

Platform note: Tesseract 5.4 is configured for Windows installation path.
On other platforms, set TESSERACT_CMD environment variable to override.
"""
from __future__ import annotations

import os
import re
import sqlite3
from typing import Optional

import cv2
import numpy as np
from PIL import Image

import pytesseract
from rapidfuzz import fuzz, process

# ---------------------------------------------------------------------------
# Tesseract configuration (Windows installation defaults)
# Override via env vars for portability to other platforms.
# ---------------------------------------------------------------------------
_TESSERACT_CMD = os.environ.get(
    "TESSERACT_CMD",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
)
pytesseract.pytesseract.tesseract_cmd = _TESSERACT_CMD
os.environ.setdefault("TESSDATA_PREFIX", r"C:\Program Files\Tesseract-OCR\tessdata")

# ---------------------------------------------------------------------------
# Stat type keyword patterns — handles OCR noise like "toraicameswon"
# ---------------------------------------------------------------------------
_STAT_PATTERNS = {
    "games_won": r"(game|gam|cam|cane|cames)",
    "aces": r"\bace",
    "double_faults": r"(fault|double)",
}

# Words to exclude from secondary player name heuristic
_NOISE_WORDS = {"More", "Less", "Player", "CRETE", "ATP", "WTA", "Games", "Aces", "Double", "Faults"}


# ---------------------------------------------------------------------------
# Card segmentation helpers
# ---------------------------------------------------------------------------

def _find_separator_bands(profile: np.ndarray, threshold: float = 10.0) -> list[tuple[int, int]]:
    """
    Find bands where mean brightness is below threshold (dark card separators).

    Parameters
    ----------
    profile : np.ndarray
        1D array of mean brightness values per row or column.
    threshold : float
        Brightness threshold below which a position is considered dark.

    Returns
    -------
    list of (start_idx, end_idx) tuples for each contiguous dark band.
    """
    dark = np.where(profile < threshold)[0]
    if len(dark) == 0:
        return []
    groups: list[list[int]] = []
    for i, pos in enumerate(dark):
        if i == 0 or pos - dark[i - 1] > 1:
            groups.append([pos])
        else:
            groups[-1].append(pos)
    return [(g[0], g[-1]) for g in groups]


def _segment_cards(img: np.ndarray) -> list[np.ndarray]:
    """
    Segment a PrizePicks screenshot into individual card images.

    Detects near-black separator bands between cards. Falls back to a 4x5
    equal-division grid if insufficient bands are found.

    Parameters
    ----------
    img : np.ndarray
        BGR image array (from cv2.imdecode).

    Returns
    -------
    list of numpy arrays, one per card (cropped BGR image).
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    img_h, img_w = gray.shape

    # Row brightness profile: mean brightness per row
    row_profile = gray.mean(axis=1).astype(float)
    # Column brightness profile: mean brightness per column
    col_profile = gray.mean(axis=0).astype(float)

    row_bands = _find_separator_bands(row_profile)
    col_bands = _find_separator_bands(col_profile)

    # Need at least 2 separators in each axis to define grid boundaries
    if len(row_bands) < 2 or len(col_bands) < 2:
        # Fallback: equal-division grid (4 cols x 5 rows)
        n_cols, n_rows = 4, 5
        card_w = img_w // n_cols
        card_h = img_h // n_rows
        cards = []
        for row in range(n_rows):
            for col in range(n_cols):
                y0, y1 = row * card_h, (row + 1) * card_h
                x0, x1 = col * card_w, (col + 1) * card_w
                cards.append(img[y0:y1, x0:x1])
        return cards

    # Derive card boundaries from separator bands
    # Each card starts 1px after separator end, ends 1px before next separator start
    def _boundaries(bands: list[tuple[int, int]], max_dim: int) -> list[tuple[int, int]]:
        """Convert separator band list to (start, end) card boundary pairs."""
        boundaries = []
        for i in range(len(bands) - 1):
            card_start = bands[i][1] + 1
            card_end = bands[i + 1][0] - 1
            if card_end > card_start:
                boundaries.append((card_start, card_end))
        return boundaries

    row_boundaries = _boundaries(row_bands, img_h)
    col_boundaries = _boundaries(col_bands, img_w)

    if not row_boundaries or not col_boundaries:
        # Fallback to equal grid
        n_cols, n_rows = 4, 5
        card_w = img_w // n_cols
        card_h = img_h // n_rows
        cards = []
        for row in range(n_rows):
            for col in range(n_cols):
                y0, y1 = row * card_h, (row + 1) * card_h
                x0, x1 = col * card_w, (col + 1) * card_w
                cards.append(img[y0:y1, x0:x1])
        return cards

    cards = []
    for y0, y1 in row_boundaries:
        for x0, x1 in col_boundaries:
            cards.append(img[y0:y1, x0:x1])
    return cards


# ---------------------------------------------------------------------------
# Text parsing helpers
# ---------------------------------------------------------------------------

def _extract_player_name(lines: list[str]) -> Optional[str]:
    """
    Extract player name from OCR text lines.

    Primary: regex for '<name> - Player' or '<name> = Player' marker.
    Secondary fallback: first line with 2+ capitalized words, no digits,
    length 5-30, not a known noise word.

    Parameters
    ----------
    lines : list of str
        Lines of OCR text from a single card.

    Returns
    -------
    str or None
    """
    # Primary: look for '- Player' or '= Player' marker
    for line in lines:
        m = re.search(r"(.+?)\s*[-=]\s*Player", line, re.IGNORECASE)
        if m:
            name = re.sub(r"^[^a-zA-Z]+", "", m.group(1)).strip()
            if len(name) >= 3:
                return name

    # Secondary: find first line with 2+ capitalized words, no digits, length 5-30
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if any(c.isdigit() for c in stripped):
            continue
        if len(stripped) < 5 or len(stripped) > 30:
            continue
        words = stripped.split()
        if len(words) < 2:
            continue
        if all(w[0].isupper() for w in words if w):
            # Exclude known noise words (entire line must not be a noise word)
            if stripped not in _NOISE_WORDS and words[0] not in _NOISE_WORDS:
                return stripped

    return None


def _extract_line_value(lines: list[str]) -> tuple[Optional[float], Optional[str]]:
    """
    Extract line value and stat type from OCR text lines.

    Prefers .5 decimal values in the plausible 3.0-35.0 range.
    Handles OCR noise like 'toraicameswon' via keyword patterns.

    Parameters
    ----------
    lines : list of str

    Returns
    -------
    (line_value, stat_type) or (None, None)
    """
    for line in lines:
        nums = re.findall(r"\d+\.?\d*", line)
        if not nums:
            continue
        float_nums = [float(n) for n in nums]
        # Filter to plausible PrizePicks range
        plausible = [n for n in float_nums if 3.0 <= n <= 35.0]
        # Prefer .5 decimal values (PrizePicks standard)
        half_pt = [n for n in plausible if n % 1 == 0.5]

        line_lower = line.lower()
        for stat, pattern in _STAT_PATTERNS.items():
            if re.search(pattern, line_lower):
                candidates = half_pt or plausible or float_nums
                if candidates:
                    return candidates[0], stat

    return None, None


def _extract_directions(text: str) -> list[str]:
    """
    Determine available bet directions from card text.

    Returns list of "over" and/or "under" based on presence of "More"/"Less".
    Defaults to ["over", "under"] if neither found (ambiguous card).

    Parameters
    ----------
    text : str
        Full OCR text from a single card.

    Returns
    -------
    list of str — subset of ["over", "under"]
    """
    directions = []
    if "More" in text:
        directions.append("over")
    if "Less" in text:
        directions.append("under")
    if not directions:
        # Ambiguous — return both as default
        return ["over", "under"]
    return directions


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _load_player_names(db_path: str) -> dict[str, int]:
    """
    Load ATP player names from the database for fuzzy matching.

    Parameters
    ----------
    db_path : str
        Path to SQLite database. Use ':memory:' for an in-memory DB (returns {}).

    Returns
    -------
    dict mapping player_name -> player_id for all ATP players.
    """
    if db_path == ":memory:":
        return {}
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT DISTINCT player_id, player_name FROM players WHERE tour = 'ATP'"
        ).fetchall()
        return {row[1]: row[0] for row in rows}
    except Exception:
        return {}
    finally:
        conn.close()


def _fuzzy_match_player(
    name: str,
    players: dict[str, int],
    threshold: int = 80,
) -> Optional[str]:
    """
    Fuzzy-match an OCR-extracted name against ATP player names.

    Uses token_set_ratio for robustness against OCR noise and partial names.

    Parameters
    ----------
    name : str
        Player name as extracted by OCR (may have noise).
    players : dict
        Mapping of canonical player_name -> player_id.
    threshold : int
        Minimum similarity score (0-100) to accept a match.

    Returns
    -------
    Matched canonical name str, or None if score < threshold.
    """
    if not players:
        return None
    result = process.extractOne(
        name,
        list(players.keys()),
        scorer=fuzz.token_set_ratio,
    )
    if result is None:
        return None
    matched_name, score, _ = result
    return matched_name if score >= threshold else None


# ---------------------------------------------------------------------------
# OCR per card
# ---------------------------------------------------------------------------

def _ocr_card(card_img: np.ndarray) -> Optional[dict]:
    """
    Run OCR on a single card image and parse prop data.

    Parameters
    ----------
    card_img : np.ndarray
        BGR card image (cropped from full screenshot).

    Returns
    -------
    dict with keys: player_name, stat_type, line_value, directions
    or None if player_name or line_value could not be extracted.
    """
    # Guard against empty card slices (can happen with tiny fallback images)
    if card_img.size == 0 or card_img.shape[0] < 2 or card_img.shape[1] < 2:
        return None

    # Convert BGR numpy array to PIL Image for pytesseract
    pil_img = Image.fromarray(cv2.cvtColor(card_img, cv2.COLOR_BGR2RGB))
    text = pytesseract.image_to_string(pil_img, config="--psm 6")
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    player_name = _extract_player_name(lines)
    line_value, stat_type = _extract_line_value(lines)
    directions = _extract_directions(text)

    if player_name is None or line_value is None:
        return None

    return {
        "player_name": player_name,
        "stat_type": stat_type,
        "line_value": line_value,
        "directions": directions,
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def scan_image_bytes(image_bytes: bytes, db_path: str) -> dict:
    """
    Decode a PrizePicks screenshot, segment cards, run OCR, and return extracted props.

    Parameters
    ----------
    image_bytes : bytes
        Raw image bytes (JPEG, PNG, etc.) from a file upload.
    db_path : str
        Path to the SQLite database for ATP player fuzzy matching.

    Returns
    -------
    dict with keys:
        - "status": "ok" or "tesseract_not_found"
        - "cards": list of dicts with player_name, stat_type, line_value, directions

    Raises
    ------
    ValueError
        If image_bytes cannot be decoded as a valid image.
    """
    try:
        # Decode image from raw bytes
        arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Could not decode image — unsupported format or corrupt file")

        # Segment into individual cards
        cards = _segment_cards(img)

        # Load ATP player names for fuzzy matching
        atp_players = _load_player_names(db_path)

        # OCR + parse + fuzzy match each card
        results = []
        for card_img in cards:
            try:
                parsed = _ocr_card(card_img)
            except pytesseract.TesseractNotFoundError:
                raise  # Re-raise to be caught by outer handler
            if parsed is None:
                continue
            # Fuzzy match — silently skip non-ATP or unmatched players
            matched = _fuzzy_match_player(parsed["player_name"], atp_players)
            if matched is None and atp_players:
                continue
            result_name = matched if matched else parsed["player_name"]
            results.append({**parsed, "player_name": result_name})

        return {"status": "ok", "cards": results}

    except pytesseract.TesseractNotFoundError:
        return {"status": "tesseract_not_found", "cards": []}
