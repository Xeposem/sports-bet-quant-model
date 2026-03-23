"""
Unit tests for src/props/scanner.py — OCR card segmentation and parsing functions.

Tests cover:
- _extract_player_name: primary regex + secondary heuristic + None fallback
- _extract_line_value: stat pattern matching + half-point preference + None fallback
- _extract_directions: Less/More detection + defaults
- _fuzzy_match_player: match found, OCR noise tolerance, no-match threshold
- _find_separator_bands: dark band detection on known brightness profile
- scan_image_bytes: bad image raises ValueError

Integration test (Task 2):
- test_scan_endpoint: POST /props/scan returns PropScanResponse JSON
"""
from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Helper: minimal 1x1 white PNG in bytes (no external libs needed for RED phase)
# ---------------------------------------------------------------------------

def _make_valid_png() -> bytes:
    """Create a valid white PNG (50x50) as bytes using numpy + cv2."""
    import cv2
    import numpy as np
    # Create a 50x50 white BGR image
    img = np.full((50, 50, 3), 255, dtype=np.uint8)
    success, buf = cv2.imencode(".png", img)
    assert success
    return buf.tobytes()


# ---------------------------------------------------------------------------
# _extract_player_name
# ---------------------------------------------------------------------------

class TestExtractPlayerName:
    def test_primary_marker(self):
        from src.props.scanner import _extract_player_name
        result = _extract_player_name(["some junk", "@ Novak Djokovic - Player", "vs Someone"])
        assert result == "Novak Djokovic"

    def test_secondary_heuristic(self):
        from src.props.scanner import _extract_player_name
        result = _extract_player_name(["tht", "eee", "Belinda Bencic", "CRETE"])
        assert result == "Belinda Bencic"

    def test_none_no_match(self):
        from src.props.scanner import _extract_player_name
        result = _extract_player_name(["More", "Less", "123"])
        assert result is None

    def test_primary_with_equals_sign(self):
        from src.props.scanner import _extract_player_name
        result = _extract_player_name(["@ Rafael Nadal = Player", "vs Djokovic"])
        assert result == "Rafael Nadal"

    def test_strips_leading_garbage(self):
        from src.props.scanner import _extract_player_name
        result = _extract_player_name(["@# Carlos Alcaraz - Player"])
        assert result == "Carlos Alcaraz"


# ---------------------------------------------------------------------------
# _extract_line_value
# ---------------------------------------------------------------------------

class TestExtractLineValue:
    def test_games_won(self):
        from src.props.scanner import _extract_line_value
        val, stat = _extract_line_value(["@ 9.5 toraicames won"])
        assert val == 9.5
        assert stat == "games_won"

    def test_aces(self):
        from src.props.scanner import _extract_line_value
        val, stat = _extract_line_value(["@ 4.5 Aces"])
        assert val == 4.5
        assert stat == "aces"

    def test_double_faults(self):
        from src.props.scanner import _extract_line_value
        val, stat = _extract_line_value(["2 3.5 double fault"])
        assert val == 3.5
        assert stat == "double_faults"

    def test_prefers_half_point(self):
        from src.props.scanner import _extract_line_value
        val, stat = _extract_line_value(["2 9.5 tera cames won"])
        assert val == 9.5
        assert stat == "games_won"

    def test_none_no_numbers(self):
        from src.props.scanner import _extract_line_value
        val, stat = _extract_line_value(["More", "Less"])
        assert val is None
        assert stat is None

    def test_cam_variant(self):
        from src.props.scanner import _extract_line_value
        val, stat = _extract_line_value(["@ 12.5 cam won"])
        assert val == 12.5
        assert stat == "games_won"

    def test_fault_variant(self):
        from src.props.scanner import _extract_line_value
        val, stat = _extract_line_value(["@ 3.5 fault"])
        assert val == 3.5
        assert stat == "double_faults"


# ---------------------------------------------------------------------------
# _extract_directions
# ---------------------------------------------------------------------------

class TestExtractDirections:
    def test_both(self):
        from src.props.scanner import _extract_directions
        result = _extract_directions("Less ... More")
        assert "over" in result
        assert "under" in result

    def test_more_only(self):
        from src.props.scanner import _extract_directions
        result = _extract_directions("More only")
        assert result == ["over"]
        assert "under" not in result

    def test_less_only(self):
        from src.props.scanner import _extract_directions
        result = _extract_directions("Less only")
        assert result == ["under"]
        assert "over" not in result

    def test_neither_defaults_to_both(self):
        from src.props.scanner import _extract_directions
        result = _extract_directions("some text with no buttons")
        assert "over" in result
        assert "under" in result


# ---------------------------------------------------------------------------
# _fuzzy_match_player
# ---------------------------------------------------------------------------

class TestFuzzyMatchPlayer:
    def test_exact_match(self):
        from src.props.scanner import _fuzzy_match_player
        players = {"Novak Djokovic": 1, "Rafael Nadal": 2}
        result = _fuzzy_match_player("Novak Djokovic", players)
        assert result == "Novak Djokovic"

    def test_ocr_noise_match(self):
        from src.props.scanner import _fuzzy_match_player
        players = {"Novak Djokovic": 1}
        result = _fuzzy_match_player("Novak Djokavic", players)
        assert result == "Novak Djokovic"

    def test_no_match_below_threshold(self):
        from src.props.scanner import _fuzzy_match_player
        players = {"Novak Djokovic": 1}
        result = _fuzzy_match_player("Unknown Player XYZ", players)
        assert result is None


# ---------------------------------------------------------------------------
# _find_separator_bands
# ---------------------------------------------------------------------------

class TestFindSeparatorBands:
    def test_known_dark_bands(self):
        from src.props.scanner import _find_separator_bands
        # Create a profile: mostly bright (200), with dark bands at [5..9] and [20..24]
        profile = np.full(30, 200.0)
        profile[5:10] = 5.0  # dark band at indices 5-9
        profile[20:25] = 3.0  # dark band at indices 20-24

        bands = _find_separator_bands(profile, threshold=10.0)
        assert len(bands) == 2
        assert bands[0] == (5, 9)
        assert bands[1] == (20, 24)

    def test_no_dark_bands(self):
        from src.props.scanner import _find_separator_bands
        profile = np.full(30, 200.0)
        bands = _find_separator_bands(profile, threshold=10.0)
        assert bands == []

    def test_single_pixel_band(self):
        from src.props.scanner import _find_separator_bands
        profile = np.full(10, 200.0)
        profile[5] = 5.0
        bands = _find_separator_bands(profile, threshold=10.0)
        assert len(bands) == 1
        assert bands[0] == (5, 5)


# ---------------------------------------------------------------------------
# scan_image_bytes — error handling
# ---------------------------------------------------------------------------

class TestScanImageBytes:
    def test_bad_image_raises_value_error(self):
        from src.props.scanner import scan_image_bytes
        with pytest.raises(ValueError, match="Could not decode image"):
            scan_image_bytes(b"not an image", ":memory:")

    def test_valid_tiny_image_tesseract_not_found(self):
        """A valid image with Tesseract mocked as not found returns tesseract_not_found status."""
        from src.props.scanner import scan_image_bytes
        import pytesseract

        png_bytes = _make_valid_png()
        # Mock at the module level where scanner.py imported pytesseract
        with patch("src.props.scanner.pytesseract.image_to_string",
                   side_effect=pytesseract.TesseractNotFoundError()):
            result = scan_image_bytes(png_bytes, ":memory:")

        assert result["status"] == "tesseract_not_found"
        assert result["cards"] == []


# ---------------------------------------------------------------------------
# Integration test: POST /props/scan endpoint (Task 2)
# ---------------------------------------------------------------------------

class TestScanEndpoint:
    """Integration tests for POST /api/v1/props/scan endpoint."""

    @pytest.mark.asyncio
    async def test_scan_endpoint_returns_cards(self, async_client):
        """POST /props/scan with a valid image returns 200 and cards list."""
        import cv2
        import numpy as np

        # Create a valid 50x50 white PNG
        img = np.full((50, 50, 3), 255, dtype=np.uint8)
        success, buf = cv2.imencode(".png", img)
        assert success
        png_bytes = buf.tobytes()

        # Mock scan_image_bytes to return one card without touching Tesseract
        mock_result = {
            "status": "ok",
            "cards": [
                {
                    "player_name": "Test Player",
                    "stat_type": "aces",
                    "line_value": 5.5,
                    "directions": ["over"],
                }
            ],
        }
        with patch("src.props.scanner.scan_image_bytes", return_value=mock_result):
            response = await async_client.post(
                "/api/v1/props/scan",
                files={"file": ("screenshot.png", png_bytes, "image/png")},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert len(data["cards"]) == 1
        assert data["cards"][0]["player_name"] == "Test Player"
        assert data["cards"][0]["stat_type"] == "aces"
        assert data["cards"][0]["line_value"] == 5.5
        assert data["cards"][0]["directions"] == ["over"]

    @pytest.mark.asyncio
    async def test_scan_endpoint_rejects_non_image(self, async_client):
        """POST /props/scan with non-image content_type returns 422."""
        response = await async_client.post(
            "/api/v1/props/scan",
            files={"file": ("data.txt", b"hello world", "text/plain")},
        )
        assert response.status_code == 422
        body = response.json()
        # App uses custom error format: {"error": ..., "message": ...}
        error_text = body.get("detail", "") or body.get("message", "")
        assert "image" in error_text.lower()
