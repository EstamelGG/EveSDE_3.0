"""
游戏资源缓存下载模块（兼容层）
实现已迁移至 utils.eve_client
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.eve_client import (  # noqa: F401
    EveClient,
    EveClientError,
    IndexEntry,
    SharedCache,
    CacheDownloader,
    CacheError,
    get_eve_client,
    set_eve_client,
)
