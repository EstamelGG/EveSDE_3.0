#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
本地化数据提取主控制脚本
"""

import os
import sys
from pathlib import Path

# 导入本地化处理模块
try:
    from localization_extractor import LocalizationExtractor
except:
    from localization.localization_extractor import LocalizationExtractor

try:
    from accounting_types_localizer import AccountingTypesLocalizer
except:
    from localization.accounting_types_localizer import AccountingTypesLocalizer

def main(eve_client=None):
    """主函数"""
    project_root = Path(__file__).parent.parent

    try:
        extractor = LocalizationExtractor(project_root, eve_client=eve_client)
        if not extractor.extract_all():
            return False
    except Exception as e:
        print(f"[x] 本地化数据提取失败: {e}")
        return False

    try:
        localizer = AccountingTypesLocalizer(project_root)
        if not localizer.localize_accounting_types():
            print("[x] 会计条目类型本地化失败")
            return False
    except Exception as e:
        print(f"[x] 会计条目类型本地化失败: {e}")
        return False

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
