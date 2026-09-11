import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://zoomshields@localhost:5432/hn")
TOP_N = int(os.environ.get("HN_TOP_N", "100"))
POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", "300"))
HN_API_BASE = "https://hacker-news.firebaseio.com/v0"
