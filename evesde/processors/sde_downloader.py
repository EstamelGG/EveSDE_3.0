"""SDE 数据准备：下载指定构建并解压，版本由应用层决定。"""
import shutil
import zipfile

from evesde.paths import load_config, path
from evesde.utils.downloads import download_file, validate_zip


def archive_path(config, build_number):
    build_number = str(build_number).split(".", 1)[0]
    return path("sde_zip", config) / f"eve-online-static-data-{build_number}-jsonl.zip"


def download_sde(config, build_number):
    build_number = str(build_number).split(".", 1)[0]
    url = config["urls"]["sde_download_template"].format(build_number=build_number)
    try:
        destination = download_file(url, archive_path(config, build_number), validate=validate_zip, timeout=60)
        return True, destination
    except Exception as exc:
        print(f"[x] SDE下载失败: {exc}")
        return False, None


def extract_sde(config, filename):
    try:
        destination = path("sde_input", config)
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(filename) as archive:
            archive.extractall(destination)
        return destination
    except Exception as exc:
        print(f"[x] SDE解压失败: {exc}")
        return False


def main(config=None, build_number=None):
    config = config if config is not None else load_config()
    if build_number is None:
        from evesde.build_prep import get_latest_sde_info
        info = get_latest_sde_info(config)
        if not info:
            return False
        build_number = info["build_number"]
    success, filename = download_sde(config, build_number)
    return bool(success and extract_sde(config, filename))


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
