#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prepare release assets for GitHub Actions.
"""

from utils.single_db import get_db_path
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


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRIMARY_LANGS = {"en", "zh"}


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


def create_release_archives(config: Dict[str, Any], extra_langs: List[str]) -> Dict[str, Path]:
    output_sde = PROJECT_ROOT / "output_sde"
    icons_source = PROJECT_ROOT / "output_icons" / "icons.zip"
    icons_zip = PROJECT_ROOT / "icons.zip"
    sde_zip = PROJECT_ROOT / "sde.zip"

    if not icons_source.exists():
        raise FileNotFoundError("output_icons/icons.zip was not generated")
    shutil.copy2(icons_source, icons_zip)

    db_dir = output_sde / "db"
    extra_dbs = {
        lang: db_dir / get_db_path(config).name
        for lang in extra_langs
    }
    missing = [str(path) for path in extra_dbs.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing language databases: " + ", ".join(missing))

    with zipfile.ZipFile(sde_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
        add_directory_to_zip(zipf, output_sde, extra_dbs.values())

    assets = {
        "icons": icons_zip,
        "sde": sde_zip,
    }

    for lang, db_path in extra_dbs.items():
        zip_path = PROJECT_ROOT / f"sde_db_{lang}.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
            zipf.write(db_path, db_path.name)
        assets[f"sde_db_{lang}"] = zip_path

    ensure_zip(icons_zip, min_size_mb=1)
    ensure_zip(sde_zip, min_size_mb=5)
    for lang in extra_langs:
        ensure_zip(assets[f"sde_db_{lang}"])

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
    extra_langs: List[str],
) -> Dict[str, Any]:
    icons_sha = sha256_file(assets["icons"])
    sde_sha = sha256_file(assets["sde"])
    extra_db = {
        lang: {
            "file": f"sde_db_{lang}.zip",
            "sha256": sha256_file(assets[f"sde_db_{lang}"]),
        }
        for lang in extra_langs
    }

    metadata = {
        "icon_version": next_icon_version(repository, icons_sha),
        "icon_sha256": icons_sha,
        "sde_sha256": sde_sha,
        "build_number": int(args.build_number),
        "patch_number": int(args.patch_version),
        "release_date": args.release_date,
        "extra_db": extra_db,
    }

    metadata_path = PROJECT_ROOT / "metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return metadata


def find_whats_new(final_build_number: str) -> Optional[Path]:
    whats_new_dir = PROJECT_ROOT / "whats_new"
    if not whats_new_dir.exists():
        return None
    return next(iter(sorted(whats_new_dir.glob(f"whats_new_*_{final_build_number}.md"))), None)


def write_release_notes(
    args: argparse.Namespace,
    metadata: Dict[str, Any],
    timestamp: str,
    whats_new: Optional[Path],
    extra_langs: List[str],
    compare_exists: bool,
) -> Path:
    notes_path = PROJECT_ROOT / f"release_notes_{args.final_build_number}.md"
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
        whats_new_url = (
            f"https://raw.githubusercontent.com/{args.github_repository}/main/whats_new/"
            f"{whats_new.name}"
        )
        lines.append(f"- [物品变更报告]({whats_new_url})")
    if not compare_exists and not whats_new:
        lines.append("- 本次未生成附加报告")


    extra_names = " / ".join(f"**{lang}**" for lang in extra_langs)
    lines.extend([
        "",
        "## 下载文件",
        f"- **sde-build-{args.final_build_number}-all.tar.gz**: 全量包",
        "- **sde.zip**: SDE 数据包（en/zh + localization + maps）",
        "- **icons.zip**: 图标包",
        f"- **sde_db_*.zip**: 其他语言数据库（{extra_names}）",
        "- **metadata.json**: 版本元数据和哈希信息",
    ])
    if whats_new:
        lines.append(f"- **{whats_new.name}**: 物品变更报告")

    notes_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return notes_path


def create_tarball(final_build_number: str, files: List[Path]) -> Path:
    tar_path = PROJECT_ROOT / f"sde-build-{final_build_number}-all.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        for file_path in files:
            tar.add(file_path, arcname=file_path.name)
    return tar_path


def main() -> None:
    args = parse_args()
    config = load_config()
    languages = config.get("languages", [])
    extra_langs = [lang for lang in languages if lang not in PRIMARY_LANGS]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    assets = create_release_archives(config, extra_langs)
    metadata = write_metadata(args, args.github_repository, assets, extra_langs)
    whats_new = find_whats_new(args.final_build_number)
    compare_file = PROJECT_ROOT / f"release_compare_{args.final_build_number}.md"
    notes = write_release_notes(
        args,
        metadata,
        timestamp,
        whats_new,
        extra_langs,
        compare_file.exists(),
    )

    release_files = [
        assets["sde"],
        assets["icons"],
        *(assets[f"sde_db_{lang}"] for lang in extra_langs),
        PROJECT_ROOT / "metadata.json",
    ]
    tarball = create_tarball(
        args.final_build_number,
        release_files + ([whats_new] if whats_new else []),
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
