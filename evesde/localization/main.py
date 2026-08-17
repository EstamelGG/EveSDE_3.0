#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
本地化数据提取主控制脚本
"""

from evesde.paths import PROJECT_ROOT
import sys

try:
    from localization_extractor import LocalizationExtractor
except ImportError:
    from evesde.localization.localization_extractor import LocalizationExtractor


def main(eve_client=None):
    """提取客户端本地化数据。会计条目已改由官方 SDE 生成，不在此处处理。"""
    try:
        extractor = LocalizationExtractor(PROJECT_ROOT, eve_client=eve_client)
        return extractor.extract_all()
    except Exception as e:
        print(f"[x] 本地化数据提取失败: {e}")
        return False


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
