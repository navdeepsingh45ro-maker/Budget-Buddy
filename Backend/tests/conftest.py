import os
import sys
import tempfile
from pathlib import Path

# Must run before anything imports `database`: point every test at a throwaway
# SQLite file so tests can never touch the real Backend/database.db.
_db_file = Path(tempfile.mkdtemp()) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_db_file}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production-0123456789")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

import database  # noqa: E402

assert "test.db" in str(database.engine.url), "Tests must not run against the real database"

import services.insight_updater as insight_updater  # noqa: E402
import services.monthly_report as monthly_report  # noqa: E402
from services.gemini_client import GeminiUnavailable  # noqa: E402


@pytest.fixture(autouse=True)
def no_real_ai_tips(monkeypatch):
    """Background insight refreshes must never call the real Gemini API in tests."""
    monkeypatch.setattr(insight_updater, "generate_coach_tip", lambda insight, summary: "Stub tip")


@pytest.fixture(autouse=True)
def no_real_ai_reports(monkeypatch):
    """Report commentary must never call the real Gemini API in tests (tests override this)."""
    def offline(prompt, temperature=0):
        raise GeminiUnavailable("AI disabled in tests")
    monkeypatch.setattr(monthly_report, "generate_json", offline)


@pytest.fixture(autouse=True)
def no_real_gemini_connection(monkeypatch):
    """Safety net: any Gemini call a test forgot to stub fails offline instead of using the real API."""
    import services.gemini_client as gemini_client

    def blocked():
        raise GeminiUnavailable("Real Gemini API is blocked in tests")
    monkeypatch.setattr(gemini_client, "_get_client", blocked)


@pytest.fixture(autouse=True)
def push_calls(monkeypatch):
    """Never contact real push services in tests. Records what would be sent; runs deliveries synchronously."""
    import services.push_service as push_service
    calls = []

    def fake_webpush(subscription_info, data, **kwargs):
        import json
        calls.append({"endpoint": subscription_info["endpoint"], **json.loads(data)})

    monkeypatch.setattr(push_service, "webpush", fake_webpush)
    monkeypatch.setattr(push_service, "_run_in_background", lambda fn, *args: fn(*args))
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "test-public-key")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "test-private-key")
    monkeypatch.setattr(push_service, "is_quiet_hours", lambda now=None: False)  # daytime unless a test says otherwise
    return calls


@pytest.fixture(autouse=True)
def fresh_rate_limits():
    """Every test starts with empty rate-limit counters."""
    from services import rate_limit
    rate_limit.reset_all()
