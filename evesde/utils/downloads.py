"""构建内共用的流式文件下载与 ZIP 校验。"""
from pathlib import Path
import zipfile

from evesde.utils.http_client import get


def validate_zip(filename: Path) -> None:
    with zipfile.ZipFile(filename) as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise zipfile.BadZipFile(f"CRC 校验失败: {bad_member}")


def download_file(url: str, destination: Path, *, validate=None, **kwargs) -> Path:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    try:
        with get(url, stream=True, **kwargs) as response, partial.open("wb") as stream:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    stream.write(chunk)
        if validate:
            validate(partial)
        partial.replace(destination)
        return destination
    finally:
        partial.unlink(missing_ok=True)
