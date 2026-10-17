"""Settings. Everything can be overridden with environment variables."""
import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("TREMOR_DATA", Path(__file__).resolve().parent / "data"))
DB_PATH = Path(os.environ.get("TREMOR_DB", DATA_DIR / "tremor.db"))
SHOTS_DIR = DATA_DIR / "shots"

MIN_INTERVAL_MIN = 15          # requirement: 15 min to 24 h
MAX_INTERVAL_MIN = 24 * 60
FETCH_TIMEOUT_S = 30
USER_AGENT = "TremorBot/0.1 (website change detector; public pages only)"

# Only for local tests: lets the app watch pages on localhost.
ALLOW_PRIVATE = os.environ.get("TREMOR_ALLOW_PRIVATE") == "1"
