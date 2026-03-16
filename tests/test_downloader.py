"""
Tests for src/ingestion/downloader.py

Covers:
- download_match_file URL construction and file writing (mocked)
- download_match_file raises on HTTP 404
- download_player_file downloads atp_players.csv (mocked)
- get_available_years uses HEAD requests and returns correct list (mocked)
"""
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import pytest

from src.ingestion.downloader import (
    download_match_file,
    download_player_file,
    get_available_years,
    BASE_URL,
)


class TestDownloadMatchFile:
    def test_constructs_correct_url(self, tmp_path):
        """download_match_file requests the correct URL for a given year."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"tourney_id,match_num\n2024-001,1\n"
        mock_response.raise_for_status = MagicMock()

        with patch("src.ingestion.downloader.requests.get", return_value=mock_response) as mock_get:
            download_match_file(2024, str(tmp_path))

        expected_url = f"{BASE_URL}/atp_matches_2024.csv"
        mock_get.assert_called_once_with(expected_url, timeout=30)

    def test_writes_file_to_dest_dir(self, tmp_path):
        """download_match_file writes the CSV content to dest_dir/atp_matches_{year}.csv."""
        csv_content = b"tourney_id,match_num\n2024-001,1\n"
        mock_response = MagicMock()
        mock_response.content = csv_content
        mock_response.raise_for_status = MagicMock()

        with patch("src.ingestion.downloader.requests.get", return_value=mock_response):
            result_path = download_match_file(2023, str(tmp_path))

        expected_path = str(tmp_path / "atp_matches_2023.csv")
        assert result_path == expected_path
        assert Path(result_path).exists()
        assert Path(result_path).read_bytes() == csv_content

    def test_returns_dest_path(self, tmp_path):
        """download_match_file returns the full path to the written file."""
        mock_response = MagicMock()
        mock_response.content = b"col1\nval1\n"
        mock_response.raise_for_status = MagicMock()

        with patch("src.ingestion.downloader.requests.get", return_value=mock_response):
            result = download_match_file(2020, str(tmp_path))

        assert result == str(tmp_path / "atp_matches_2020.csv")

    def test_raises_on_404(self, tmp_path):
        """download_match_file raises an HTTPError when the server returns 404."""
        import requests as req_lib

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = req_lib.exceptions.HTTPError("404 Not Found")

        with patch("src.ingestion.downloader.requests.get", return_value=mock_response):
            with pytest.raises(req_lib.exceptions.HTTPError):
                download_match_file(1800, str(tmp_path))


class TestDownloadPlayerFile:
    def test_downloads_atp_players_csv(self, tmp_path):
        """download_player_file downloads atp_players.csv to dest_dir."""
        player_content = b"player_id,name_first\n12345,Roger\n"
        mock_response = MagicMock()
        mock_response.content = player_content
        mock_response.raise_for_status = MagicMock()

        with patch("src.ingestion.downloader.requests.get", return_value=mock_response) as mock_get:
            result = download_player_file(str(tmp_path))

        expected_url = f"{BASE_URL}/atp_players.csv"
        mock_get.assert_called_once_with(expected_url, timeout=30)
        assert result == str(tmp_path / "atp_players.csv")
        assert Path(result).read_bytes() == player_content


class TestGetAvailableYears:
    def test_returns_years_where_csv_exists(self):
        """get_available_years returns list of years that respond with 200 to HEAD requests."""
        def head_side_effect(url, timeout):
            mock_resp = MagicMock()
            # Return 200 for 2020, 2021; 404 for everything else
            if "2020" in url or "2021" in url:
                mock_resp.status_code = 200
            else:
                mock_resp.status_code = 404
            return mock_resp

        with patch("src.ingestion.downloader.requests.head", side_effect=head_side_effect):
            result = get_available_years(start=2020, end=2022)

        assert result == [2020, 2021]

    def test_empty_result_when_no_years_available(self):
        """get_available_years returns empty list if all HEAD requests return non-200."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("src.ingestion.downloader.requests.head", return_value=mock_response):
            result = get_available_years(start=1800, end=1802)

        assert result == []

    def test_uses_timeout_per_request(self):
        """get_available_years uses timeout=5 on each HEAD request."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("src.ingestion.downloader.requests.head", return_value=mock_response) as mock_head:
            get_available_years(start=2022, end=2023)

        for call_args in mock_head.call_args_list:
            assert call_args.kwargs.get("timeout") == 5 or call_args[1].get("timeout") == 5 or (len(call_args[0]) >= 2 and call_args[0][1] == 5)
