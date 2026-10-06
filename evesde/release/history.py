"""将已验证的构建历史同步到独立 checkout；Git 操作集中于此。"""
import json
from pathlib import Path
import shutil
import subprocess

from evesde.github import output
from evesde.paths import PROJECT_ROOT


def inside(root: Path, relative: str) -> Path:
    root = root.resolve()
    candidate = (root / relative).resolve()
    if candidate == root or root not in candidate.parents:
        raise ValueError(f"路径超出工作目录: {relative}")
    return candidate


def sync_history(manifest_path: Path, checkout: Path, *, branch="main", push=False):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("debug"):
        raise ValueError("调试构建不能提交或推送历史")
    checkout = checkout.resolve()
    if checkout == PROJECT_ROOT or not (checkout / ".git").exists():
        raise ValueError("历史同步需要独立的 Git checkout")

    def git(*args):
        return subprocess.run(["git", "-C", str(checkout), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    if git("status", "--porcelain"):
        raise RuntimeError("历史 checkout 有未提交修改，无法同步")
    # 所有源文件和目标路径先校验，再执行任何复制。
    entries = []
    for entry in manifest["history_files"] + manifest["detail_directories"]:
        source = inside(PROJECT_ROOT, entry["source"])
        relative = Path(entry["destination"])
        is_detail = relative.as_posix() in ("output/item_detail/en", "output/item_detail/zh")
        allowed_report = (
            (relative.parent.as_posix() == "history" and relative.suffix == ".md")
            or (relative.parent.as_posix() == "output/whats_new" and relative.suffix in (".md", ".json"))
        )
        if not is_detail and not allowed_report:
            raise ValueError(f"不支持的历史目标: {relative}")
        destination = inside(checkout, relative.as_posix())
        if is_detail:
            if not source.is_dir() or not any(source.glob("item_*.json")):
                raise ValueError(f"物品详情缺失或为空: {source}")
        elif not source.is_file():
            raise FileNotFoundError(source)
        entries.append((source, destination, relative, is_detail))

    for source, destination, relative, is_detail in entries:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if is_detail:
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
        git("add", "--", relative.as_posix())
    if git("diff", "--cached", "--name-only"):
        git("-c", "user.name=github-actions[bot]", "-c", "user.email=github-actions[bot]@users.noreply.github.com",
            "commit", "-m", f"Update SDE data for build {manifest['build_number']} [skip ci]")
    if push:
        git("push", "origin", f"HEAD:{branch}")
    commit = git("rev-parse", "HEAD")
    output("commit", commit)
    return commit
