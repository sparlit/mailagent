import importlib
import os
import pytest


def _reload_config(env_overrides=None):
    """Re-import src.config after optionally setting environment variables."""
    import src.config as config_module
    if env_overrides:
        with pytest.MonkeyPatch().context() as mp:
            for key, val in env_overrides.items():
                mp.setenv(key, val)
            importlib.reload(config_module)
            # Capture values before the context manager exits and env is restored
            result = {
                "DASHBOARD_ENABLED": config_module.DASHBOARD_ENABLED,
                "DASHBOARD_PORT": config_module.DASHBOARD_PORT,
                "DRY_RUN": config_module.DRY_RUN,
                "CHECK_INTERVAL": config_module.CHECK_INTERVAL,
                "MAX_WORKERS": config_module.MAX_WORKERS,
            }
        importlib.reload(config_module)  # restore to defaults
        return result
    importlib.reload(config_module)
    return {
        "DASHBOARD_ENABLED": config_module.DASHBOARD_ENABLED,
        "DASHBOARD_PORT": config_module.DASHBOARD_PORT,
        "DRY_RUN": config_module.DRY_RUN,
        "CHECK_INTERVAL": config_module.CHECK_INTERVAL,
        "MAX_WORKERS": config_module.MAX_WORKERS,
    }


# ---------------------------------------------------------------------------
# Defaults (new config vars added in this PR)
# ---------------------------------------------------------------------------

def test_dashboard_enabled_default_is_true(monkeypatch):
    monkeypatch.delenv("DASHBOARD_ENABLED", raising=False)
    import src.config as cfg
    importlib.reload(cfg)
    assert cfg.DASHBOARD_ENABLED is True


def test_dashboard_port_default_is_5000(monkeypatch):
    monkeypatch.delenv("DASHBOARD_PORT", raising=False)
    import src.config as cfg
    importlib.reload(cfg)
    assert cfg.DASHBOARD_PORT == 5000


def test_dry_run_default_is_false(monkeypatch):
    monkeypatch.delenv("DRY_RUN", raising=False)
    import src.config as cfg
    importlib.reload(cfg)
    assert cfg.DRY_RUN is False


# ---------------------------------------------------------------------------
# Env-var overrides
# ---------------------------------------------------------------------------

def test_dashboard_enabled_env_false(monkeypatch):
    monkeypatch.setenv("DASHBOARD_ENABLED", "false")
    import src.config as cfg
    importlib.reload(cfg)
    assert cfg.DASHBOARD_ENABLED is False


def test_dashboard_enabled_env_true_explicit(monkeypatch):
    monkeypatch.setenv("DASHBOARD_ENABLED", "True")
    import src.config as cfg
    importlib.reload(cfg)
    assert cfg.DASHBOARD_ENABLED is True


def test_dashboard_enabled_case_insensitive_false(monkeypatch):
    monkeypatch.setenv("DASHBOARD_ENABLED", "FALSE")
    import src.config as cfg
    importlib.reload(cfg)
    assert cfg.DASHBOARD_ENABLED is False


def test_dashboard_port_env_override(monkeypatch):
    monkeypatch.setenv("DASHBOARD_PORT", "8080")
    import src.config as cfg
    importlib.reload(cfg)
    assert cfg.DASHBOARD_PORT == 8080


def test_dry_run_env_true(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")
    import src.config as cfg
    importlib.reload(cfg)
    assert cfg.DRY_RUN is True


def test_dry_run_env_false_explicit(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "False")
    import src.config as cfg
    importlib.reload(cfg)
    assert cfg.DRY_RUN is False


def test_dry_run_case_insensitive_true(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "TRUE")
    import src.config as cfg
    importlib.reload(cfg)
    assert cfg.DRY_RUN is True


# ---------------------------------------------------------------------------
# Boundary / type check
# ---------------------------------------------------------------------------

def test_dashboard_port_is_int(monkeypatch):
    monkeypatch.delenv("DASHBOARD_PORT", raising=False)
    import src.config as cfg
    importlib.reload(cfg)
    assert isinstance(cfg.DASHBOARD_PORT, int)


def test_dashboard_enabled_is_bool(monkeypatch):
    monkeypatch.delenv("DASHBOARD_ENABLED", raising=False)
    import src.config as cfg
    importlib.reload(cfg)
    assert isinstance(cfg.DASHBOARD_ENABLED, bool)


def test_dry_run_is_bool(monkeypatch):
    monkeypatch.delenv("DRY_RUN", raising=False)
    import src.config as cfg
    importlib.reload(cfg)
    assert isinstance(cfg.DRY_RUN, bool)