from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_SCRIPT_PATH = REPO_ROOT / "scripts" / "lateralus_plugin.py"


def _load_plugin_script():
    spec = importlib.util.spec_from_file_location("lateralus_plugin", PLUGIN_SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_marketplace_source_path_uses_codex_home_under_personal_root(tmp_path):
    plugin_script = _load_plugin_script()
    marketplace_path = tmp_path / ".agents" / "plugins" / "marketplace.json"
    plugin_dir = tmp_path / ".codex" / "plugins" / "lateralus-workflow"

    source_path = plugin_script.marketplace_source_path(plugin_dir, marketplace_path)

    assert source_path == "./.codex/plugins/lateralus-workflow"


def test_write_marketplace_upserts_lateralus_entry(tmp_path):
    plugin_script = _load_plugin_script()
    marketplace_path = tmp_path / ".agents" / "plugins" / "marketplace.json"
    plugin_dir = tmp_path / ".codex" / "plugins" / "lateralus-workflow"

    changed = plugin_script.write_marketplace(marketplace_path, plugin_dir)

    assert changed is True
    payload = json.loads(marketplace_path.read_text(encoding="utf-8"))
    assert payload["name"] == "lateralus-local"
    assert payload["interface"]["displayName"] == "Lateralus Local"
    assert payload["plugins"] == [
        {
            "name": "lateralus-workflow",
            "source": {
                "source": "local",
                "path": "./.codex/plugins/lateralus-workflow",
            },
            "policy": {
                "installation": "AVAILABLE",
                "authentication": "ON_INSTALL",
            },
            "category": "Productivity",
        }
    ]

    changed_again = plugin_script.write_marketplace(marketplace_path, plugin_dir)

    assert changed_again is False


def test_write_marketplace_preserves_other_plugins_and_replaces_existing_entry(tmp_path):
    plugin_script = _load_plugin_script()
    marketplace_path = tmp_path / ".agents" / "plugins" / "marketplace.json"
    marketplace_path.parent.mkdir(parents=True)
    marketplace_path.write_text(
        json.dumps(
            {
                "name": "custom-market",
                "interface": {"displayName": "Custom Market"},
                "plugins": [
                    {
                        "name": "other-plugin",
                        "source": {"source": "local", "path": "./plugins/other-plugin"},
                        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                        "category": "Productivity",
                    },
                    {
                        "name": "lateralus-workflow",
                        "source": {"source": "local", "path": "./plugins/lateralus-workflow"},
                        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                        "category": "Productivity",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    plugin_script.write_marketplace(marketplace_path, tmp_path / ".codex" / "plugins" / "lateralus-workflow")

    payload = json.loads(marketplace_path.read_text(encoding="utf-8"))
    assert payload["name"] == "custom-market"
    assert payload["interface"]["displayName"] == "Custom Market"
    assert [entry["name"] for entry in payload["plugins"]] == ["other-plugin", "lateralus-workflow"]
    assert payload["plugins"][1]["source"]["path"] == "./.codex/plugins/lateralus-workflow"


def test_find_installed_cache_dirs_returns_plugin_versions_only(tmp_path):
    plugin_script = _load_plugin_script()
    codex_home = tmp_path / ".codex"
    installed = codex_home / "plugins" / "cache" / "local-plugins" / "lateralus-workflow" / "0.1.0"
    installed.joinpath(".codex-plugin").mkdir(parents=True)
    installed.joinpath(".codex-plugin", "plugin.json").write_text("{}", encoding="utf-8")
    ignored = codex_home / "plugins" / "cache" / "local-plugins" / "other-plugin" / "0.1.0"
    ignored.joinpath(".codex-plugin").mkdir(parents=True)
    ignored.joinpath(".codex-plugin", "plugin.json").write_text("{}", encoding="utf-8")

    cache_dirs = plugin_script.find_installed_cache_dirs(codex_home)

    assert cache_dirs == [installed]


def test_sync_snapshot_cache_updates_non_git_cache_from_source(tmp_path):
    plugin_script = _load_plugin_script()
    source = tmp_path / "source"
    cache = tmp_path / "cache"
    source.joinpath(".codex-plugin").mkdir(parents=True)
    source.joinpath(".codex-plugin", "plugin.json").write_text('{"name": "lateralus-workflow"}', encoding="utf-8")
    source.joinpath("README.md").write_text("new docs\n", encoding="utf-8")
    source.joinpath(".git").mkdir()
    source.joinpath(".git", "HEAD").write_text("ignored", encoding="utf-8")
    cache.mkdir()
    cache.joinpath("README.md").write_text("old docs\n", encoding="utf-8")
    cache.joinpath("stale.txt").write_text("stale\n", encoding="utf-8")

    result = plugin_script.sync_snapshot_cache(cache, source)

    assert result.status == "synced"
    assert cache.joinpath("README.md").read_text(encoding="utf-8") == "new docs\n"
    assert cache.joinpath(".codex-plugin", "plugin.json").exists()
    assert not cache.joinpath("stale.txt").exists()
    assert not cache.joinpath(".git", "HEAD").exists()


def test_sync_snapshot_cache_check_reports_difference_without_writing(tmp_path):
    plugin_script = _load_plugin_script()
    source = tmp_path / "source"
    cache = tmp_path / "cache"
    source.mkdir()
    cache.mkdir()
    source.joinpath("README.md").write_text("new docs\n", encoding="utf-8")
    cache.joinpath("README.md").write_text("old docs\n", encoding="utf-8")

    result = plugin_script.sync_snapshot_cache(cache, source, check_only=True)

    assert result.status == "update-available"
    assert cache.joinpath("README.md").read_text(encoding="utf-8") == "old docs\n"


def test_install_returns_nonzero_when_source_update_is_blocked(tmp_path, monkeypatch, capsys):
    plugin_script = _load_plugin_script()
    plugin_dir = tmp_path / ".codex" / "plugins" / "lateralus-workflow"
    marketplace_path = tmp_path / ".agents" / "plugins" / "marketplace.json"

    monkeypatch.setattr(plugin_script, "ensure_source_checkout", lambda *args, **kwargs: None)
    monkeypatch.setattr(plugin_script, "write_marketplace", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        plugin_script,
        "update_git_checkout",
        lambda path, ref, check_only=False: plugin_script.GitUpdateResult(
            path=path,
            status="blocked",
            detail="checkout has local changes",
        ),
    )

    exit_code = plugin_script.main(
        [
            "--plugin-dir",
            str(plugin_dir),
            "--marketplace-path",
            str(marketplace_path),
            "install",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "blocked" in captured.out
    assert "Restart Codex" not in captured.out
    assert "Install blocked" in captured.err


def test_update_source_and_caches_syncs_snapshot_cache_after_source_update(tmp_path, monkeypatch):
    plugin_script = _load_plugin_script()
    codex_home = tmp_path / ".codex"
    source = codex_home / "plugins" / "lateralus-workflow"
    cache = codex_home / "plugins" / "cache" / "local-plugins" / "lateralus-workflow" / "0.1.0"
    source.joinpath(".codex-plugin").mkdir(parents=True)
    source.joinpath(".codex-plugin", "plugin.json").write_text("{}", encoding="utf-8")
    source.joinpath("README.md").write_text("new docs\n", encoding="utf-8")
    cache.joinpath(".codex-plugin").mkdir(parents=True)
    cache.joinpath(".codex-plugin", "plugin.json").write_text("{}", encoding="utf-8")
    cache.joinpath("README.md").write_text("old docs\n", encoding="utf-8")

    monkeypatch.setattr(
        plugin_script,
        "update_git_checkout",
        lambda path, ref, check_only=False: plugin_script.GitUpdateResult(path=path, status="up-to-date"),
    )

    results = plugin_script._update_source_and_caches(source, codex_home, "main", include_cache=True)

    assert [result.status for result in results] == ["up-to-date", "synced"]
    assert cache.joinpath("README.md").read_text(encoding="utf-8") == "new docs\n"
