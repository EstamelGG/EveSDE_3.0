"""兼容旧导入路径；发布实现统一位于 evesde.release.comparison。"""
from evesde.release.comparison import *  # noqa: F401,F403

if __name__ == "__main__":
    from evesde.cli import main
    import sys
    raise SystemExit(main(["reports", *sys.argv[1:]]))
