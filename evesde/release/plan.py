"""一次查询确定整个构建使用的版本和比较基线。"""
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re

from evesde.build_prep import get_latest_sde_info
from evesde.github import GitHub, repository_name


@dataclass(frozen=True)
class BuildPlan:
    build_number: str
    final_build_number: str
    patch_version: str
    release_date: str
    build_key: str | None
    repository: str
    previous_release: dict | None
    client_data: dict
    should_build: bool = True
    debug: bool = False

    def __post_init__(self):
        if not re.fullmatch(r"[0-9]+", self.build_number):
            raise ValueError("无效的 CCP 构建号")
        patch = int(self.patch_version)
        expected = f"{self.build_number}.{patch:02d}" if patch else self.build_number
        if not 0 <= patch <= 99 or self.final_build_number != expected:
            raise ValueError("补丁号与最终构建号不一致")
        if not self.release_date:
            raise ValueError("SDE 版本信息缺少 releaseDate")

    def save(self, filename: Path):
        filename.parent.mkdir(parents=True, exist_ok=True)
        filename.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, filename: Path):
        return cls(**json.loads(filename.read_text(encoding="utf-8")))


def create_plan(config, *, patch=False, debug=False, skip_version_check=False, check_release=True):
    info = get_latest_sde_info(config, skip_version_check=skip_version_check)
    if not info:
        raise RuntimeError("无法确定 SDE 版本信息")
    build = str(info["build_number"]).split(".", 1)[0]
    repository = repository_name(config)
    github = GitHub(repository)
    final, patch_number, should_build = build, 0, True
    if check_release and not debug and github.release(build):
        if patch:
            # 一次分页取出已占用的补丁号，避免顺序请求 99 个标签。
            tags = {r["tag_name"] for r in github.pages("releases")}
            for candidate in range(1, 100):
                final = f"{build}.{candidate:02d}"
                if f"sde-build-{final}" not in tags:
                    patch_number = candidate
                    break
            else:
                raise RuntimeError("已达到补丁版本上限（99）")
        else:
            should_build = False
    previous = github.latest_release() if should_build else None
    return BuildPlan(build, final, str(patch_number), info["release_date"], info.get("key"),
                     repository, previous, info["client_data"], should_build, debug)
