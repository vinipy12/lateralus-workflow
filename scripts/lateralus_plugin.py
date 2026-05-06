#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PLUGIN_NAME = "lateralus-workflow"
DEFAULT_REPOSITORY_URL = "https://github.com/vinipy12/lateralus-workflow.git"
DEFAULT_REF = "main"
DEFAULT_MARKETPLACE_NAME = "lateralus-local"
DEFAULT_MARKETPLACE_DISPLAY_NAME = "Lateralus Local"
SYNC_EXCLUDED_PARTS = {".git", ".venv", "__pycache__", ".pytest_cache"}


@dataclass(frozen=True)
class GitUpdateResult:
    path: Path
    status: str
    before: str | None = None
    after: str | None = None
    detail: str | None = None


def home_dir(env: dict[str, str] | None = None) -> Path:
    values = env or os.environ
    return Path(values.get("HOME", str(Path.home()))).expanduser()


def codex_home(env: dict[str, str] | None = None) -> Path:
    values = env or os.environ
    return Path(values.get("CODEX_HOME", str(home_dir(values) / ".codex"))).expanduser()


def default_plugin_dir(env: dict[str, str] | None = None) -> Path:
    return codex_home(env) / "plugins" / PLUGIN_NAME


def default_marketplace_path(env: dict[str, str] | None = None) -> Path:
    values = env or os.environ
    root = codex_home(values).parent if values.get("CODEX_HOME") else home_dir(values)
    return root / ".agents" / "plugins" / "marketplace.json"


def marketplace_root(marketplace_path: Path) -> Path:
    resolved = marketplace_path.expanduser()
    if (
        resolved.name == "marketplace.json"
        and resolved.parent.name == "plugins"
        and resolved.parent.parent.name == ".agents"
    ):
        return resolved.parent.parent.parent
    return resolved.parent


def marketplace_source_path(plugin_dir: Path, marketplace_path: Path) -> str:
    root = marketplace_root(marketplace_path).resolve()
    plugin_path = plugin_dir.expanduser().resolve()
    try:
        relative = plugin_path.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"plugin dir must live inside marketplace root {root} for a portable local source path"
        ) from exc
    return f"./{relative.as_posix()}"


def build_marketplace_entry(plugin_dir: Path, marketplace_path: Path) -> dict[str, Any]:
    return {
        "name": PLUGIN_NAME,
        "source": {
            "source": "local",
            "path": marketplace_source_path(plugin_dir, marketplace_path),
        },
        "policy": {
            "installation": "AVAILABLE",
            "authentication": "ON_INSTALL",
        },
        "category": "Productivity",
    }


def load_marketplace(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "name": DEFAULT_MARKETPLACE_NAME,
            "interface": {"displayName": DEFAULT_MARKETPLACE_DISPLAY_NAME},
            "plugins": [],
        }
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"marketplace must be a JSON object: {path}")
    payload.setdefault("name", DEFAULT_MARKETPLACE_NAME)
    interface = payload.setdefault("interface", {})
    if isinstance(interface, dict):
        interface.setdefault("displayName", DEFAULT_MARKETPLACE_DISPLAY_NAME)
    else:
        payload["interface"] = {"displayName": DEFAULT_MARKETPLACE_DISPLAY_NAME}
    plugins = payload.setdefault("plugins", [])
    if not isinstance(plugins, list):
        raise ValueError(f"marketplace plugins must be a list: {path}")
    return payload


def upsert_marketplace_entry(marketplace: dict[str, Any], entry: dict[str, Any]) -> bool:
    plugins = marketplace.setdefault("plugins", [])
    for index, existing in enumerate(plugins):
        if isinstance(existing, dict) and existing.get("name") == entry["name"]:
            changed = existing != entry
            plugins[index] = entry
            return changed
    plugins.append(entry)
    return True


def write_marketplace(path: Path, plugin_dir: Path) -> bool:
    marketplace = load_marketplace(path)
    changed = upsert_marketplace_entry(marketplace, build_marketplace_entry(plugin_dir, path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(marketplace, indent=2) + "\n", encoding="utf-8")
    return changed


def find_installed_cache_dirs(codex_home_path: Path) -> list[Path]:
    cache_root = codex_home_path / "plugins" / "cache"
    if not cache_root.exists():
        return []
    candidates = cache_root.glob(f"*/{PLUGIN_NAME}/*")
    return sorted(
        path
        for path in candidates
        if path.is_dir() and (path / ".codex-plugin" / "plugin.json").exists()
    )


def ensure_source_checkout(plugin_dir: Path, repository_url: str, ref: str) -> None:
    if plugin_dir.exists():
        if not (plugin_dir / ".git").exists():
            raise ValueError(f"plugin dir exists but is not a git checkout: {plugin_dir}")
        return
    plugin_dir.parent.mkdir(parents=True, exist_ok=True)
    _run(["git", "clone", "--branch", ref, repository_url, str(plugin_dir)], cwd=None)


def update_git_checkout(path: Path, ref: str, *, check_only: bool = False) -> GitUpdateResult:
    if not (path / ".git").exists():
        return GitUpdateResult(path=path, status="blocked", detail="not a git checkout")

    dirty = _git(path, "status", "--porcelain")
    if dirty.strip():
        return GitUpdateResult(path=path, status="blocked", detail="checkout has local changes")

    before = _git(path, "rev-parse", "HEAD").strip()
    current_ref = _git(path, "rev-parse", "--abbrev-ref", "HEAD").strip()
    _git(path, "fetch", "--tags", "--prune", "origin")
    upstream = _git(path, "rev-parse", "--verify", f"origin/{ref}").strip()
    if before == upstream and current_ref == ref:
        return GitUpdateResult(path=path, status="up-to-date", before=before, after=before)
    if check_only:
        detail = None if current_ref == ref else f"checked out {current_ref}, target is {ref}"
        return GitUpdateResult(path=path, status="update-available", before=before, after=upstream, detail=detail)

    if current_ref != ref:
        if _git(path, "branch", "--list", ref).strip():
            _git(path, "switch", ref)
        else:
            _git(path, "switch", "--track", "-c", ref, f"origin/{ref}")
    _git(path, "pull", "--ff-only", "origin", ref)
    after = _git(path, "rev-parse", "HEAD").strip()
    return GitUpdateResult(path=path, status="updated", before=before, after=after)


def update_cache_copy(cache_dir: Path, source_dir: Path, ref: str, *, check_only: bool = False) -> GitUpdateResult:
    if (cache_dir / ".git").exists():
        return update_git_checkout(cache_dir, ref, check_only=check_only)
    return sync_snapshot_cache(cache_dir, source_dir, check_only=check_only)


def sync_snapshot_cache(cache_dir: Path, source_dir: Path, *, check_only: bool = False) -> GitUpdateResult:
    if not source_dir.exists():
        return GitUpdateResult(path=cache_dir, status="blocked", detail=f"source checkout missing: {source_dir}")
    if not cache_dir.exists():
        return GitUpdateResult(path=cache_dir, status="skipped", detail="cache dir missing")

    source_files = _file_digest_map(source_dir)
    cache_files = _file_digest_map(cache_dir)
    if source_files == cache_files:
        return GitUpdateResult(path=cache_dir, status="up-to-date", detail="snapshot cache")
    if check_only:
        return GitUpdateResult(path=cache_dir, status="update-available", detail="snapshot cache differs from source")

    _sync_tree(source_dir, cache_dir, source_files)
    return GitUpdateResult(path=cache_dir, status="synced", detail="snapshot cache")


def _file_digest_map(root: Path) -> dict[str, str]:
    digests: dict[str, str] = {}
    if not root.exists():
        return digests
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root)
        if _should_skip_sync_path(relative):
            continue
        digests[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digests


def _sync_tree(source_dir: Path, cache_dir: Path, source_files: dict[str, str]) -> None:
    cache_files = _file_digest_map(cache_dir)
    for relative_name in sorted(set(cache_files) - set(source_files), reverse=True):
        (cache_dir / relative_name).unlink()

    for relative_name in sorted(source_files):
        source_path = source_dir / relative_name
        target_path = cache_dir / relative_name
        if target_path.exists() and target_path.is_dir():
            shutil.rmtree(target_path)
        if target_path.parent.exists() and not target_path.parent.is_dir():
            target_path.parent.unlink()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)

    _remove_empty_dirs(cache_dir)


def _remove_empty_dirs(root: Path) -> None:
    directories = (item for item in root.rglob("*") if item.is_dir())
    for path in sorted(directories, key=lambda item: len(item.parts), reverse=True):
        if _should_skip_sync_path(path.relative_to(root)):
            continue
        try:
            path.rmdir()
        except OSError:
            pass


def _should_skip_sync_path(relative: Path) -> bool:
    return any(part in SYNC_EXCLUDED_PARTS for part in relative.parts)


def _git(cwd: Path, *args: str) -> str:
    return _run(["git", *args], cwd=cwd).stdout


def _run(command: list[str], *, cwd: Path | None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)


def _result_line(result: GitUpdateResult) -> str:
    detail = f" ({result.detail})" if result.detail else ""
    if result.before and result.after and result.before != result.after:
        return f"{result.status}: {result.path} {result.before[:12]} -> {result.after[:12]}{detail}"
    return f"{result.status}: {result.path}{detail}"


def _print_results(results: list[GitUpdateResult]) -> None:
    for result in results:
        print(_result_line(result))


def _blocked(results: list[GitUpdateResult]) -> bool:
    return any(result.status == "blocked" for result in results)


def _update_source_and_caches(
    plugin_dir: Path,
    codex_home_path: Path,
    ref: str,
    *,
    include_cache: bool,
    check_only: bool = False,
) -> list[GitUpdateResult]:
    source_result = update_git_checkout(plugin_dir, ref, check_only=check_only)
    results = [source_result]
    if source_result.status == "blocked":
        return results
    if include_cache:
        results.extend(
            update_cache_copy(cache_dir, plugin_dir, ref, check_only=check_only)
            for cache_dir in find_installed_cache_dirs(codex_home_path)
        )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install, check, and update the Lateralus Workflow Codex plugin.")
    parser.add_argument("--plugin-dir", type=Path, default=default_plugin_dir())
    parser.add_argument("--marketplace-path", type=Path, default=default_marketplace_path())
    parser.add_argument("--codex-home", type=Path, default=codex_home())
    parser.add_argument("--repo", default=DEFAULT_REPOSITORY_URL)
    parser.add_argument("--ref", default=DEFAULT_REF)
    subparsers = parser.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser("install", help="Clone or reuse the global checkout and write marketplace metadata.")
    install_parser.add_argument("--skip-cache-update", action="store_true")

    subparsers.add_parser("write-marketplace", help="Write only the personal marketplace entry.")

    check_parser = subparsers.add_parser("check", help="Check the source checkout and installed cache copies for updates.")
    check_parser.add_argument("--skip-cache", action="store_true")

    update_parser = subparsers.add_parser("update", help="Fast-forward the source checkout and installed cache copies.")
    update_parser.add_argument("--skip-cache", action="store_true")

    args = parser.parse_args(argv)

    plugin_dir = args.plugin_dir.expanduser()
    marketplace_path = args.marketplace_path.expanduser()
    codex_home_path = args.codex_home.expanduser()

    try:
        if args.command == "install":
            ensure_source_checkout(plugin_dir, args.repo, args.ref)
            write_marketplace(marketplace_path, plugin_dir)
            results = _update_source_and_caches(
                plugin_dir,
                codex_home_path,
                args.ref,
                include_cache=not args.skip_cache_update,
            )
            print(f"marketplace: {marketplace_path}")
            print(f"plugin source: {plugin_dir}")
            _print_results(results)
            if _blocked(results):
                print("Install blocked; resolve the issue above and rerun the command.", file=sys.stderr)
                return 1
            print("Restart Codex, open /plugins, install or re-enable Lateralus Workflow, then start a new thread.")
            return 0

        if args.command == "write-marketplace":
            write_marketplace(marketplace_path, plugin_dir)
            print(f"marketplace entry ready: {marketplace_path}")
            print(f"plugin source: {plugin_dir}")
            return 0

        if args.command == "check":
            results = _update_source_and_caches(
                plugin_dir,
                codex_home_path,
                args.ref,
                include_cache=not args.skip_cache,
                check_only=True,
            )
            _print_results(results)
            return 0 if not _blocked(results) else 1

        if args.command == "update":
            results = _update_source_and_caches(
                plugin_dir,
                codex_home_path,
                args.ref,
                include_cache=not args.skip_cache,
            )
            _print_results(results)
            if _blocked(results):
                print("Update blocked; resolve the issue above and rerun the command.", file=sys.stderr)
                return 1
            print("Restart Codex after updating installed plugin files.")
            return 0

    except (subprocess.CalledProcessError, OSError, ValueError) as exc:
        print(f"lateralus_plugin.py error: {exc}", file=sys.stderr)
        return 1

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
