"""Settings. Pulled from .env, with local defaults."""

import os

from dotenv import load_dotenv

load_dotenv()

# No user in the URL, so Postgres uses whoever is logged in.
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost:5432/hn")
HN_API_BASE = "https://hacker-news.firebaseio.com/v0"
