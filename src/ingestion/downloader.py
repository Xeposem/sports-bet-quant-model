"""
Download CSV files from the JeffSackmann/tennis_atp GitHub repository.

Exports:
- download_match_file(year, dest_dir) -> str
- download_player_file(dest_dir) -> str
- download_rankings_file(decade, dest_dir) -> str
- get_available_years(start, end) -> list[int]
"""
import os
import requests

BASE_URL = "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master"


def download_match_file(year: int, dest_dir: str) -> str:
    """
    Download the ATP tour-level singles match CSV for a given year.

    Args:
        year: The season year (e.g., 2024).
        dest_dir: Directory where the file will be written.

    Returns:
        Absolute path to the downloaded file.

    Raises:
        requests.exceptions.HTTPError: If the server returns a non-200 status.
    """
    filename = f"atp_matches_{year}.csv"
    url = f"{BASE_URL}/{filename}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    dest_path = os.path.join(dest_dir, filename)
    with open(dest_path, "wb") as f:
        f.write(response.content)
    return dest_path


def download_player_file(dest_dir: str) -> str:
    """
    Download the ATP player biographical file (atp_players.csv).

    Args:
        dest_dir: Directory where the file will be written.

    Returns:
        Absolute path to the downloaded file.

    Raises:
        requests.exceptions.HTTPError: If the server returns a non-200 status.
    """
    filename = "atp_players.csv"
    url = f"{BASE_URL}/{filename}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    dest_path = os.path.join(dest_dir, filename)
    with open(dest_path, "wb") as f:
        f.write(response.content)
    return dest_path


def download_rankings_file(decade: str, dest_dir: str) -> str:
    """
    Download a rankings CSV for a given decade.

    Args:
        decade: Decade suffix used by Sackmann (e.g., "20s" for 2020s,
                "10s" for 2010s, "00s" for 2000s, "90s" for 1990s).
        dest_dir: Directory where the file will be written.

    Returns:
        Absolute path to the downloaded file.

    Raises:
        requests.exceptions.HTTPError: If the server returns a non-200 status.
    """
    filename = f"atp_rankings_{decade}.csv"
    url = f"{BASE_URL}/{filename}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    dest_path = os.path.join(dest_dir, filename)
    with open(dest_path, "wb") as f:
        f.write(response.content)
    return dest_path


def get_available_years(start: int = 1991, end: int = 2026) -> list:
    """
    Return a list of years for which the ATP match CSV exists at the Sackmann repository.

    Uses HTTP HEAD requests to check file availability without downloading content.

    Args:
        start: First year to check (inclusive). Defaults to 1991.
        end: Last year to check (inclusive). Defaults to 2026.

    Returns:
        List of integer years where the CSV exists (status code 200).
    """
    available = []
    for year in range(start, end + 1):
        filename = f"atp_matches_{year}.csv"
        url = f"{BASE_URL}/{filename}"
        try:
            response = requests.head(url, timeout=5)
            if response.status_code == 200:
                available.append(year)
        except requests.exceptions.RequestException:
            # Network error — skip this year
            pass
    return available
