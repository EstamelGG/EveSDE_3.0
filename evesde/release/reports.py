"""基于同一构建计划生成物品变更报告；不读取 Actions 环境变量。"""
import re
import zipfile
from pathlib import Path

from evesde.paths import path
from evesde.processors import item_changes_analyzer
from evesde.utils.downloads import download_file, validate_zip

REQUIRED_JSONL = ("types", "groups", "categories", "blueprints", "typeDogma", "dogmaAttributes")


def extract_build_number_from_tag(tag_name: str):
    match = re.fullmatch(r"sde-build-([0-9]+)(?:\.[0-9]+)?", tag_name)
    return match[1] if match else None


def verify_jsonl_files(directory: Path) -> bool:
    return all((directory / f"{name}.jsonl").is_file() for name in REQUIRED_JSONL)


def download_and_extract_jsonl(config, build_number, output_dir):
    try:
        destination = output_dir / f"eve-online-static-data-{build_number}-jsonl.zip"
        url = config["urls"]["sde_download_template"].format(build_number=build_number)
        download_file(url, destination, validate=validate_zip, timeout=300)
        extracted = output_dir / f"jsonl_{build_number}"
        with zipfile.ZipFile(destination) as archive:
            archive.extractall(extracted)
        destination.unlink()
        return extracted
    except Exception as exc:
        print(f"[x] 下载旧版 JSONL 失败: {exc}")
        return None


def generate_report(config, plan, baseline) -> Path | None:
    if baseline.release is None:
        print("[+] 首次发布，无上一版物品变更报告")
        return None
    previous = extract_build_number_from_tag(baseline.release.get("tag_name", ""))
    if previous is None:
        print("[!] 上一版不是 SDE 标签，跳过物品变更报告")
        return None
    current = path("sde_input", config)
    if not verify_jsonl_files(current):
        raise RuntimeError("当前构建的 JSONL 文件不完整")
    # 补丁版使用同一 CCP 数据；同次构建无需再下载一遍。
    old = current if previous == plan.build_number else download_and_extract_jsonl(
        config, previous, baseline.directory
    )
    if old is None or not verify_jsonl_files(old):
        raise RuntimeError("上一版 JSONL 文件不完整")
    destination = path("whats_new", config) / f"whats_new_{previous}_{plan.final_build_number}.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    current_icons = path("icons_output", config) / "icons.zip"
    try:
        old_icons = baseline.asset("icons.zip")
    except Exception as exc:
        print(f"[!] 上一版图标下载失败，跳过图标比较: {exc}")
        old_icons = None
    success = item_changes_analyzer.main(
        config, old, current, destination,
        old_icons_zip=old_icons, current_icons_zip=current_icons if current_icons.exists() else None,
        old_version=baseline.release["tag_name"].removeprefix("sde-build-"),
        new_version=plan.final_build_number,
    )
    if not success or not destination.is_file() or not destination.with_suffix(".json").is_file():
        raise RuntimeError("物品变更报告生成失败")
    return destination


def main():
    from evesde.cli import main as cli
    import sys
    return cli(["reports", *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
