"""
游戏资源缓存下载模块（兼容层）
实现已迁移至 evesde.utils.eve_client
"""

from evesde.utils.eve_client import (  # noqa: F401
    EveClient,
    EveClientError,
    IndexEntry,
    SharedCache,
    CacheDownloader,
    CacheError,
    get_eve_client,
    set_eve_client,
)
