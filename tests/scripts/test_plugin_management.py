from __future__ import annotations

import importlib.util
import json
import subprocess
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


def _run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def test_marketplace_source_path_uses_codex_home_under_personal_root(tmp_path):
    plugin_script = _load_plugin_script()
    marketplace_path = tmp_path / ".agents" / "plugins" / "marketplace.json"
    plugin_dir = tmp_path / ".codex" / "plugins" / "lateralus-workflow"

    source_path = plugin_script.marketplace_source_path(plugin_dir, marketplace_path)

    assert source_path == "./.codex/plugins/lateralus-workflow"


def test_default_marketplace_path_tracks_explicit_codex_home_parent(tmp_path):
    plugin_script = _load_plugin_script()
    env = {
        "HOME": str(tmp_path / "home"),
        "CODEX_HOME": str(tmp_path / "custom-codex-home"),
    }

    marketplace_path = plugin_script.default_marketplace_path(env)
    plugin_dir = plugin_script.default_plugin_dir(env)

    assert marketplace_path == tmp_path / ".agents" / "plugins" / "marketplace.json"
    assert plugin_script.marketplace_source_path(plugin_dir, marketplace_path) == (
        "./custom-codex-home/plugins/lateralus-workflow"
    )


def test_write_marketplace_zero_arg_defaults_work_with_custom_codex_home(tmp_path, monkeypatch):
    plugin_script = _load_plugin_script()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "custom-codex-home"))

    exit_code = plugin_script.main(["write-marketplace"])

    marketplace_path = tmp_path / ".agents" / "plugins" / "marketplace.json"
    payload = json.loads(marketplace_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["plugins"][0]["source"]["path"] == "./custom-codex-home/plugins/lateralus-workflow"


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


def test_update_git_checkout_blocks_missing_source_checkout(tmp_path):
    plugin_script = _load_plugin_script()

    result = plugin_script.update_git_checkout(tmp_path / "missing-source", "main")

    assert result.status == "blocked"
    assert result.detail == "not a git checkout"


def test_update_git_checkout_blocks_non_fast_forward_divergence(tmp_path):
    plugin_script = _load_plugin_script()
    origin = tmp_path / "origin.git"
    seed = tmp_path / "seed"
    plugin_dir = tmp_path / "plugin"
    seed.mkdir()
    _run_git(tmp_path, "init", "--bare", str(origin))
    _run_git(seed, "init", "--initial-branch", "main")
    _run_git(seed, "config", "user.email", "test@example.com")
    _run_git(seed, "config", "user.name", "Test User")
    seed.joinpath("README.md").write_text("initial\n", encoding="utf-8")
    _run_git(seed, "add", "README.md")
    _run_git(seed, "commit", "-m", "initial")
    _run_git(seed, "remote", "add", "origin", str(origin))
    _run_git(seed, "push", "-u", "origin", "main")
    _run_git(origin, "symbolic-ref", "HEAD", "refs/heads/main")
    _run_git(tmp_path, "clone", str(origin), str(plugin_dir))
    _run_git(plugin_dir, "config", "user.email", "test@example.com")
    _run_git(plugin_dir, "config", "user.name", "Test User")

    seed.joinpath("remote.txt").write_text("remote\n", encoding="utf-8")
    _run_git(seed, "add", "remote.txt")
    _run_git(seed, "commit", "-m", "remote change")
    _run_git(seed, "push", "origin", "main")
    plugin_dir.joinpath("local.txt").write_text("local\n", encoding="utf-8")
    _run_git(plugin_dir, "add", "local.txt")
    _run_git(plugin_dir, "commit", "-m", "local change")

    check_result = plugin_script.update_git_checkout(plugin_dir, "main", check_only=True)
    update_result = plugin_script.update_git_checkout(plugin_dir, "main")

    assert check_result.status == "blocked"
    assert update_result.status == "blocked"
    assert "cannot fast-forward" in (update_result.detail or "")


def test_check_and_update_return_nonzero_when_source_checkout_is_missing(tmp_path, capsys):
    plugin_script = _load_plugin_script()

    for command in ("check", "update"):
        exit_code = plugin_script.main(
            [
                "--plugin-dir",
                str(tmp_path / ".codex" / "plugins" / f"missing-{command}"),
                "--codex-home",
                str(tmp_path / ".codex"),
                command,
            ]
        )
        captured = capsys.readouterr()

        assert exit_code == 1
        assert "blocked" in captured.out
        assert "not a git checkout" in captured.out
        assert "Restart Codex" not in captured.out


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
