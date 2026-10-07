#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prepare release assets for GitHub Actions.
"""

from evesde.paths import PROJECT_ROOT
from evesde.github import output
from evesde.release.baseline import ReleaseBaseline
from evesde.utils.downloads import validate_zip
import sqlite3
from contextlib import closing
from evesde.release.plan import BuildPlan
import json
import tarfile
import zipfile
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def release_dir(config: Dict[str, Any]) -> Path:
    """发布打包输出目录：output/release/。"""
    d = PROJECT_ROOT / config["paths"]["release_output"]
    d.mkdir(parents=True, exist_ok=True)
    return d


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

    validate_zip(path)


def add_directory_to_zip(zipf: zipfile.ZipFile, root: Path, excludes: Iterable[Path]) -> None:
    exclude_set = {path.resolve() for path in excludes}
    for path in sorted(root.rglob("*")):
        if path.is_dir() or path.resolve() in exclude_set:
            continue
        zipf.write(path, path.relative_to(root).as_posix())


def create_release_archives(config: Dict[str, Any], json_report: Optional[Path] = None) -> Dict[str, Path]:
    """从 output/ 读取制品，在 output/release/ 写出 sde.zip。"""
    paths = config["paths"]
    out = release_dir(config)
    icons_source = PROJECT_ROOT / paths["icons_output"] / "icons.zip"
    sde_dir = PROJECT_ROOT / paths["sde_output"]
    sde_zip = out / "sde.zip"
    db_path = sde_dir / "db" / "item_db.sqlite"

    if not icons_source.is_file():
        raise FileNotFoundError(f"缺少 {icons_source}")
    if not db_path.is_file():
        raise FileNotFoundError(f"缺少 {db_path}")

    with closing(sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)) as conn:
        if conn.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
            raise RuntimeError("SQLite 完整性检查失败")
        if not conn.execute("SELECT 1 FROM types LIMIT 1").fetchone():
            raise RuntimeError("types 表为空")
    ensure_zip(sde_dir / "texts.zip")
    for lang in ("en", "zh"):
        directory = PROJECT_ROOT / paths[f"item_detail_{lang}"]
        if not any(directory.glob("item_*.json")):
            raise RuntimeError(f"物品详情目录缺失或为空: {directory}")

    with zipfile.ZipFile(sde_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
        add_directory_to_zip(zipf, sde_dir, excludes=(sde_dir / "whats_new.json",))
        if json_report is not None:
            zipf.write(json_report, "whats_new.json")

    assets = {"icons": icons_source, "sde": sde_zip}
    ensure_zip(icons_source, min_size_mb=1)
    ensure_zip(sde_zip, min_size_mb=5)
    return assets


def next_icon_version(baseline: ReleaseBaseline, icons_sha: str) -> int:
    old = baseline.metadata()
    if old is None:
        return 1
    if not old.get("icon_sha256") or old.get("icon_version") is None:
        raise RuntimeError("上一版 metadata.json 缺少图标字段")
    return int(old["icon_version"]) + (old["icon_sha256"] != icons_sha)


def write_metadata(
    args: BuildPlan,
    baseline: ReleaseBaseline,
    assets: Dict[str, Path],
) -> Dict[str, Any]:
    icons_sha = sha256_file(assets["icons"])
    sde_sha = sha256_file(assets["sde"])

    metadata = {
        "icon_version": next_icon_version(baseline, icons_sha),
        "icon_sha256": icons_sha,
        "sde_sha256": sde_sha,
        "build_number": int(args.build_number),
        "patch_number": int(args.patch_version),
        "release_date": args.release_date,
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


def repo_raw_url(repository: str, path: str) -> str:
    """仓库内已提交文件的 raw 访问链接。path 为相对 main 的路径。"""
    return f"https://raw.githubusercontent.com/{repository}/main/{path.lstrip('/')}"


def write_release_notes(
    args: BuildPlan,
    metadata: Dict[str, Any],
    timestamp: str,
    whats_new: Optional[Path],
    compare_exists: bool,
    out_dir: Path,
) -> Path:
    notes_path = out_dir / f"release_notes_{args.final_build_number}.md"
    # CI 会把报告提交到 history/、output/whats_new/，链接必须指向这两处
    compare_url = repo_raw_url(
        args.repository,
        f"history/release_compare_{args.final_build_number}_{timestamp}.md",
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
        whats_new_url = repo_raw_url(
            args.repository,
            f"output/whats_new/{whats_new.name}",
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
        lines.append("- **sde.zip 内的 whats_new.json**: 机器可读变更（ID 与 old/new 文本）")

    notes_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return notes_path


def create_tarball(final_build_number: str, files: List[Path], out_dir: Path) -> Path:
    tar_path = out_dir / f"sde-build-{final_build_number}-all.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        for file_path in files:
            tar.add(file_path, arcname=file_path.name)
    return tar_path


def prepare_release(config, plan, baseline, whats_new=None):
    report_files = [whats_new] if whats_new else []
    json_report = whats_new.with_name("whats_new.json") if whats_new else None
    for report in report_files + ([json_report] if json_report else []):
        if not report.is_file():
            raise FileNotFoundError(f"变更报告未完整生成: {report}")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = release_dir(config)
    assets = create_release_archives(config, json_report)
    metadata = write_metadata(plan, baseline, assets)
    compare_file = out / f"release_compare_{plan.final_build_number}.md"
    # 超过仓库单文件限制的报告不生成指向 main 的失效链接。
    compare_exists = compare_file.is_file() and compare_file.stat().st_size <= 90_000_000
    if compare_file.is_file() and not compare_exists:
        print("[!] 版本比较报告超过 90 MB，跳过入库链接")
    notes = write_release_notes(plan, metadata, timestamp, whats_new, compare_exists, out)
    release_files = [assets["sde"], assets["icons"], out / "metadata.json"]
    tarball = create_tarball(plan.final_build_number, release_files + report_files, out)
    release_files.append(tarball)
    release_files.extend(report_files)

    def relative(filename):
        return filename.resolve().relative_to(PROJECT_ROOT).as_posix()

    history_files = []
    if compare_exists:
        history_files.append({"source": relative(compare_file),
                              "destination": f"history/release_compare_{plan.final_build_number}_{timestamp}.md"})
    for report in report_files:
        history_files.append({"source": relative(report), "destination": f"output/whats_new/{report.name}"})
    detail_directories = [{"source": config["paths"][f"item_detail_{lang}"],
                           "destination": f"output/item_detail/{lang}"} for lang in ("en", "zh")]
    manifest = {"build_number": plan.final_build_number, "debug": plan.debug,
                "files": [relative(f) for f in release_files], "notes": relative(notes),
                "history_files": history_files, "detail_directories": detail_directories}
    manifest_path = out / "release-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output("release-files", "\n".join(manifest["files"]))
    output("release-notes", manifest["notes"])
    output("manifest", relative(manifest_path))
    return manifest


def main():
    from evesde.cli import main as cli
    import sys
    return cli(["package", *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
