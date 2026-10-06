"""同一次构建共享上一版 Release 及附件，不依赖前次运行的磁盘缓存。"""
import json
import zipfile
from pathlib import Path

from evesde.github import GitHub


class ReleaseBaseline:
    def __init__(self, repository: str, release: dict | None, directory: Path):
        self.github = GitHub(repository)
        self.release = release
        self.directory = directory
        self.downloads = {}
        self._sde_directory = None

    def asset(self, name: str, *, required=False) -> Path | None:
        if name in self.downloads:
            return self.downloads[name]
        assets = (self.release or {}).get("assets", [])
        asset = next((a for a in assets if a["name"] == name), None)
        if asset is None:
            if required:
                raise RuntimeError(f"上一版 Release 缺少 {name}")
            return None
        destination = self.github.download_asset(asset, self.directory / name)
        self.downloads[name] = destination
        return destination

    def sde_directory(self):
        if self._sde_directory is None:
            destination = self.directory / "sde_old"
            with zipfile.ZipFile(self.asset("sde.zip", required=True)) as archive:
                archive.extractall(destination)
            self._sde_directory = destination
        return self._sde_directory

    def metadata(self):
        if self.release is None:
            return None
        return json.loads(self.asset("metadata.json", required=True).read_text(encoding="utf-8"))
