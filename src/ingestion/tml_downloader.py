"""
Download CSV files from the Tennismylife/TML-Database GitHub repository.

Exports:
- download_tml_match_file(year, dest_dir) -> str
- download_tml_player_file(dest_dir) -> str
- TML_BASE_URL
- TML_PLAYER_FILE
"""
import os
import requests

TML_BASE_URL = "https://raw.githubusercontent.com/Tennismylife/TML-Database/master"
TML_PLAYER_FILE = "ATP_Database.csv"


def download_tml_match_file(year: int, dest_dir: str) -> str:
    """
    Download the TML ATP match CSV for a given year.

    TML uses YYYY.csv (not atp_matches_YYYY.csv like Sackmann). The output file
    is prefixed with "tml_" to avoid collisions with Sackmann files in the same directory.

    Args:
        year: The season year (e.g., 2025).
        dest_dir: Directory where the file will be written.

    Returns:
        Absolute path to the downloaded file.

    Raises:
        requests.exceptions.HTTPError: If the server returns a non-200 status.
    """
    filename = f"{year}.csv"
    url = f"{TML_BASE_URL}/{filename}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    dest_path = os.path.join(dest_dir, f"tml_{year}.csv")
    with open(dest_path, "wb") as f:
        f.write(response.content)
    return os.path.abspath(dest_path)


def download_tml_player_file(dest_dir: str) -> str:
    """
    Download the TML player biographical file (ATP_Database.csv).

    Args:
        dest_dir: Directory where the file will be written.

    Returns:
        Absolute path to the downloaded file.

    Raises:
        requests.exceptions.HTTPError: If the server returns a non-200 status.
    """
    url = f"{TML_BASE_URL}/{TML_PLAYER_FILE}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    dest_path = os.path.join(dest_dir, TML_PLAYER_FILE)
    with open(dest_path, "wb") as f:
        f.write(response.content)
    return os.path.abspath(dest_path)
