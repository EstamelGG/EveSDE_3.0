#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prepare release assets for GitHub Actions.
"""

from evesde.paths import PROJECT_ROOT
import argparse
import json
import os
import shutil
import tarfile
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from evesde.utils.single_db import get_db_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare EVE SDE release assets")
    parser.add_argument("--build-number", required=True)
    parser.add_argument("--final-build-number", required=True)
    parser.add_argument("--patch-version", required=True)
    parser.add_argument("--release-date", required=True)
    parser.add_argument("--github-repository", required=True)
    return parser.parse_args()


def load_config() -> Dict[str, Any]:
    with (PROJECT_ROOT / "config.json").open("r", encoding="utf-8") as f:
        return json.load(f)


def release_dir(config: Dict[str, Any]) -> Path:
    d = PROJECT_ROOT / config["paths"].get("release_output", "output/release")
    d.mkdir(parents=True, exist_ok=True)
    return d


def output(name: str, value: str) -> None:
    github_output = os.environ.get("GITHUB_OUTPUT")
    if not github_output:
        print(f"{name}={value}")
        return

    with open(github_output, "a", encoding="utf-8") as f:
        if "\n" in value:
            f.write(f"{name}<<EOF\n{value}\nEOF\n")
        else:
            f.write(f"{name}={value}\n")


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_zip(path: Path, min_size_mb: int = 0) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing release asset: {path}")

    size_mb = path.stat().st_size // 1024 // 1024
    if size_mb < min_size_mb:
        raise RuntimeError(f"{path.name} is too small: {size_mb} MB")

    with zipfile.ZipFile(path, "r") as zf:
        bad_file = zf.testzip()
    if bad_file:
        raise RuntimeError(f"{path.name} is corrupted at {bad_file}")


def add_directory_to_zip(zipf: zipfile.ZipFile, root: Path, excludes: Iterable[Path]) -> None:
    exclude_set = {path.resolve() for path in excludes}
    for path in sorted(root.rglob("*")):
        if path.is_dir() or path.resolve() in exclude_set:
            continue
        zipf.write(path, path.relative_to(root).as_posix())


def create_release_archives(config: Dict[str, Any]) -> Dict[str, Path]:
    """单库架构：output/sde 整包进 sde.zip，另附 icons.zip，产物写入 output/release。"""
    out = release_dir(config)
    sde_output = PROJECT_ROOT / config["paths"].get("sde_output", "output/sde")
    icons_source = PROJECT_ROOT / config["paths"].get("icons_output", "output/icons") / "icons.zip"
    icons_zip = out / "icons.zip"
    sde_zip = out / "sde.zip"
    db_path = get_db_path(config)

    if not icons_source.exists():
        raise FileNotFoundError("output/icons/icons.zip was not generated")
    if not db_path.exists():
        raise FileNotFoundError(f"Missing database: {db_path}")
    shutil.copy2(icons_source, icons_zip)

    with zipfile.ZipFile(sde_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
        add_directory_to_zip(zipf, sde_output, excludes=())

    assets = {"icons": icons_zip, "sde": sde_zip}
    ensure_zip(icons_zip, min_size_mb=1)
    ensure_zip(sde_zip, min_size_mb=5)
    return assets


def github_api_json(url: str) -> Optional[Any]:
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "EVE-SDE-Processor",
    }
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def download_text(url: str) -> str:
    headers = {"User-Agent": "EVE-SDE-Processor"}
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def latest_release(repository: str) -> Optional[Dict[str, Any]]:
    latest = github_api_json(f"https://api.github.com/repos/{repository}/releases/latest")
    if latest and not latest.get("draft") and not latest.get("prerelease"):
        return latest

    releases = github_api_json(f"https://api.github.com/repos/{repository}/releases")
    if not releases:
        return None

    valid = [
        release for release in releases
        if not release.get("draft") and not release.get("prerelease")
    ]
    return max(valid, key=lambda release: release.get("id", 0), default=None)


def next_icon_version(repository: str, icons_sha: str) -> int:
    release = latest_release(repository)
    if not release:
        return 1

    metadata_asset = next(
        (asset for asset in release.get("assets", []) if asset.get("name") == "metadata.json"),
        None,
    )
    if not metadata_asset:
        raise RuntimeError("Latest release exists but has no metadata.json")

    old_metadata = json.loads(download_text(metadata_asset["browser_download_url"]))
    old_icon_sha = old_metadata.get("icon_sha256")
    old_icon_version = old_metadata.get("icon_version")
    if not old_icon_sha or old_icon_version is None:
        raise RuntimeError("Latest metadata.json is missing icon fields")

    return int(old_icon_version) + (1 if old_icon_sha != icons_sha else 0)


def write_metadata(
    args: argparse.Namespace,
    repository: str,
    assets: Dict[str, Path],
) -> Dict[str, Any]:
    icons_sha = sha256_file(assets["icons"])
    sde_sha = sha256_file(assets["sde"])

    metadata = {
        "icon_version": next_icon_version(repository, icons_sha),
        "icon_sha256": icons_sha,
        "sde_sha256": sde_sha,
        "build_number": int(args.build_number),
        "patch_number": int(args.patch_version),
        "release_date": args.release_date,
        "extra_db": {},
    }

    metadata_path = assets["sde"].parent / "metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return metadata


def find_whats_new(final_build_number: str, config: Dict[str, Any]) -> Optional[Path]:
    whats_new_dir = PROJECT_ROOT / config["paths"].get("whats_new", "output/whats_new")
    if not whats_new_dir.exists():
        return None
    return next(iter(sorted(whats_new_dir.glob(f"whats_new_*_{final_build_number}.md"))), None)


def write_release_notes(
    args: argparse.Namespace,
    metadata: Dict[str, Any],
    timestamp: str,
    whats_new: Optional[Path],
    compare_exists: bool,
    out_dir: Path,
) -> Path:
    notes_path = out_dir / f"release_notes_{args.final_build_number}.md"
    compare_url = (
        f"https://raw.githubusercontent.com/{args.github_repository}/main/history/"
        f"release_compare_{args.final_build_number}_{timestamp}.md"
    )

    lines = [
        f"# EVE SDE Build {args.final_build_number}",
        "",
        "## 构建信息",
        f"- **Build Number**: {args.build_number}",
        f"- **Icon Version**: {metadata['icon_version']}",
        f"- **Release Date**: {args.release_date}",
    ]
    if args.patch_version != "0":
        lines.insert(4, f"- **Patch Version**: {args.patch_version}")

    lines.extend([
        "",
        "## 版本元数据",
        "",
        "```json",
        json.dumps(metadata, ensure_ascii=False, indent=2),
        "```",
        "",
        "## 详细报告",
    ])

    if compare_exists:
        lines.append(f"- [版本比较报告]({compare_url})")
    if whats_new:
        try:
            rel = whats_new.relative_to(PROJECT_ROOT).as_posix()
        except ValueError:
            rel = f"output/whats_new/{whats_new.name}"
        whats_new_url = (
            f"https://raw.githubusercontent.com/{args.github_repository}/main/{rel}"
        )
        lines.append(f"- [物品变更报告]({whats_new_url})")
    if not compare_exists and not whats_new:
        lines.append("- 本次未生成附加报告")

    lines.extend([
        "",
        "## 下载文件",
        f"- **sde-build-{args.final_build_number}-all.tar.gz**: 全量包",
        "- **sde.zip**: SDE 数据包（单库 item_db.sqlite + localization + maps + texts.zip）",
        "- **icons.zip**: 图标包",
        "- **metadata.json**: 版本元数据和哈希信息",
    ])
    if whats_new:
        lines.append(f"- **{whats_new.name}**: 物品变更报告")

    notes_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return notes_path


def create_tarball(final_build_number: str, files: List[Path], out_dir: Path) -> Path:
    tar_path = out_dir / f"sde-build-{final_build_number}-all.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        for file_path in files:
            tar.add(file_path, arcname=file_path.name)
    return tar_path


def main() -> None:
    args = parse_args()
    config = load_config()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = release_dir(config)

    assets = create_release_archives(config)
    metadata = write_metadata(args, args.github_repository, assets)
    whats_new = find_whats_new(args.final_build_number, config)
    compare_file = out / f"release_compare_{args.final_build_number}.md"
    # also accept legacy root-level compare from older builds
    if not compare_file.exists():
        legacy = PROJECT_ROOT / f"release_compare_{args.final_build_number}.md"
        if legacy.exists():
            shutil.copy2(legacy, compare_file)

    notes = write_release_notes(
        args,
        metadata,
        timestamp,
        whats_new,
        compare_file.exists(),
        out,
    )

    release_files = [
        assets["sde"],
        assets["icons"],
        out / "metadata.json",
    ]
    tarball = create_tarball(
        args.final_build_number,
        release_files + ([whats_new] if whats_new else []),
        out,
    )
    release_files.append(tarball)
    if whats_new:
        release_files.append(whats_new)

    compare_name = f"release_compare_{args.final_build_number}_{timestamp}.md"

    output("release-files", "\n".join(str(path.relative_to(PROJECT_ROOT)) for path in release_files))
    output("release-notes", str(notes.relative_to(PROJECT_ROOT)))
    output("tar-name", tarball.name)
    output("timestamp", timestamp)
    output("icon-version", str(metadata["icon_version"]))
    output("whats-new-exists", "true" if whats_new else "false")
    output("whats-new-name", str(whats_new.relative_to(PROJECT_ROOT)) if whats_new else "")
    output("whats-new-basename", whats_new.name if whats_new else "")
    output("compare-exists", "true" if compare_file.exists() else "false")
    output("compare-path", str(compare_file.resolve()) if compare_file.exists() else "")
    output("compare-new-filename", compare_name if compare_file.exists() else "")

    print("[+] Release assets ready")
    print(f"    icon_version: {metadata['icon_version']}")
    print(f"    files: {len(release_files)}")
    if whats_new:
        print(f"    whats_new: {whats_new.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
