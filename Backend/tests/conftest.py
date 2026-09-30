import os
import sys
import tempfile
from pathlib import Path

# Must run before anything imports `database`: point every test at a throwaway
# SQLite file so tests can never touch the real Backend/database.db.
_db_file = Path(tempfile.mkdtemp()) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_db_file}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

import database  # noqa: E402

assert "test.db" in str(database.engine.url), "Tests must not run against the real database"

import services.insight_updater as insight_updater  # noqa: E402


@pytest.fixture(autouse=True)
def no_real_ai_tips(monkeypatch):
    """Background insight refreshes must never call the real Gemini API in tests."""
    monkeypatch.setattr(insight_updater, "generate_coach_tip", lambda insight, summary: "Stub tip")
