"""
Tests for src/ingestion/tml_downloader.py

Covers:
- download_tml_match_file URL construction and file writing (mocked)
- download_tml_match_file raises on HTTP 404
- download_tml_player_file downloads ATP_Database.csv (mocked)
- TML_BASE_URL constant value
"""
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import requests

from src.ingestion.tml_downloader import (
    download_tml_match_file,
    download_tml_player_file,
    TML_BASE_URL,
)


class TestTMLBaseUrl:
    def test_tml_base_url_constant(self):
        """TML_BASE_URL must point to the Tennismylife TML-Database GitHub raw URL."""
        assert TML_BASE_URL == "https://raw.githubusercontent.com/Tennismylife/TML-Database/master"


class TestDownloadTMLMatchFile:
    def test_download_tml_match_file_writes_csv(self, tmp_path):
        """download_tml_match_file writes content to tml_{year}.csv in dest_dir."""
        csv_content = b"tourney_id,winner_id\n2025-9900,CD85\n"
        mock_response = MagicMock()
        mock_response.content = csv_content
        mock_response.raise_for_status = MagicMock()

        with patch("src.ingestion.tml_downloader.requests.get", return_value=mock_response) as mock_get:
            result = download_tml_match_file(2025, str(tmp_path))

        # Verify URL contains correct repo path
        called_url = mock_get.call_args[0][0]
        assert "Tennismylife/TML-Database/master/2025.csv" in called_url

        # Verify file written with tml_ prefix
        expected_path = str(tmp_path / "tml_2025.csv")
        assert result == expected_path
        assert Path(result).exists()
        assert Path(result).read_bytes() == csv_content

    def test_download_tml_match_file_raises_on_404(self, tmp_path):
        """download_tml_match_file raises requests.exceptions.HTTPError on 404."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")

        with patch("src.ingestion.tml_downloader.requests.get", return_value=mock_response):
            with pytest.raises(requests.exceptions.HTTPError):
                download_tml_match_file(1800, str(tmp_path))

    def test_download_tml_match_file_uses_timeout(self, tmp_path):
        """download_tml_match_file uses timeout=30 in requests.get call."""
        mock_response = MagicMock()
        mock_response.content = b"data"
        mock_response.raise_for_status = MagicMock()

        with patch("src.ingestion.tml_downloader.requests.get", return_value=mock_response) as mock_get:
            download_tml_match_file(2025, str(tmp_path))

        call_kwargs = mock_get.call_args
        assert call_kwargs[1].get("timeout") == 30 or (len(call_kwargs[0]) > 1 and call_kwargs[0][1] == 30)

    def test_download_tml_match_file_returns_absolute_path(self, tmp_path):
        """download_tml_match_file returns an absolute path."""
        mock_response = MagicMock()
        mock_response.content = b"data"
        mock_response.raise_for_status = MagicMock()

        with patch("src.ingestion.tml_downloader.requests.get", return_value=mock_response):
            result = download_tml_match_file(2025, str(tmp_path))

        assert os.path.isabs(result)


class TestDownloadTMLPlayerFile:
    def test_download_tml_player_file_writes_csv(self, tmp_path):
        """download_tml_player_file writes ATP_Database.csv to dest_dir."""
        player_content = b'"id","player","atpname"\n"CD85","Pablo Carreno Busta","Carreno Busta P."\n'
        mock_response = MagicMock()
        mock_response.content = player_content
        mock_response.raise_for_status = MagicMock()

        with patch("src.ingestion.tml_downloader.requests.get", return_value=mock_response) as mock_get:
            result = download_tml_player_file(str(tmp_path))

        # Verify URL contains ATP_Database.csv
        called_url = mock_get.call_args[0][0]
        assert "ATP_Database.csv" in called_url

        # Verify file written correctly
        expected_path = str(tmp_path / "ATP_Database.csv")
        assert result == expected_path
        assert Path(result).exists()
        assert Path(result).read_bytes() == player_content
