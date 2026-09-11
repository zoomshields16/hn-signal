"""Settings. Pulled from .env, with local defaults."""

import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://zoomshields@localhost:5432/hn")
POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", "300"))
HN_API_BASE = "https://hacker-news.firebaseio.com/v0"
