"""Settings. Pulled from .env, with local defaults."""

import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://zoomshields@localhost:5432/hn")
HN_API_BASE = "https://hacker-news.firebaseio.com/v0"
