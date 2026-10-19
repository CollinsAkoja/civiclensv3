from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("CIVICLENS_DB", str(tmp_path / "app.db"))
    monkeypatch.setenv("CIVICLENS_DEMO", "1")
    monkeypatch.setenv("CIVICLENS_REVIEWER_PASSWORD", "secret123")
    monkeypatch.setenv("OLLAMA_HOST_URL", "http://127.0.0.1:9")  # nothing listens here: limited mode


def run():
    return AppTest.from_file(APP, default_timeout=60).run()


def login(at, password):
    at.text_input(key="reviewer_password").set_value(password)
    [b for b in at.button if b.label == "Log in"][0].click()
    return at.run()


def test_app_loads_and_dashboard_shows_demo_data(env):
    at = run()
    assert not at.exception
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Submitted"] == "60"
    assert any("Limited mode" in w.value for w in at.sidebar.warning)


def test_wrong_password_is_rejected(env):
    at = login(run(), "nope")
    assert not at.exception
    assert "Incorrect password." in [e.value for e in at.error]
    assert not at.session_state["reviewer_ok"] if "reviewer_ok" in at.session_state else True


def test_correct_password_unlocks_reviewer_tools(env):
    at = login(run(), "secret123")
    assert not at.exception
    assert at.session_state["reviewer_ok"] is True
    assert len(at.get("download_button")) == 2


def test_reviewer_area_is_disabled_without_a_configured_password(env, monkeypatch):
    monkeypatch.delenv("CIVICLENS_REVIEWER_PASSWORD")
    at = run()
    assert any("Reviewer access is switched off" in w.value for w in at.warning)
    assert not at.get("download_button")


def test_submitting_a_report_end_to_end(env):
    at = run()
    at.text_input[0].set_value("Blocked drain on Market Road")
    at.text_area[0].set_value("The drain is blocked with refuse and the road floods whenever it rains.")
    at.text_input[1].set_value("Bwari")
    at.text_input[2].set_value("Dutse")
    at.button[0].click().run()
    assert not at.exception and not at.error
    assert any("saved" in s.value for s in at.success)
    assert any("AI-suggested category" in i.value for i in at.info)
