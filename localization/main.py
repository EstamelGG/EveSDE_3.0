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

def main():
    """主函数"""
    localization_dir = Path(__file__).parent
    project_root = localization_dir.parent
    
    print("[+] EVE SDE 本地化数据提取器")
    print("=" * 50)
    print("[+] 从网络下载EVE客户端资源文件")
    print("[+] 仅使用在线资源，不依赖本地客户端")
    print("=" * 50)
    
    # 步骤1: 提取本地化数据
    print("\n[+] 预热步骤: 开始本地化数据提取...")
    try:
        extractor = LocalizationExtractor(project_root)
        success = extractor.extract_all()
        if not success:
            print("[x] 本地化数据提取失败，停止执行")
            return False
        print("[+] 本地化数据提取完成")
    except Exception as e:
        print(f"[x] 本地化数据提取时出错: {e}")
        return False
    
    # 步骤2: 处理会计条目类型本地化
    print("\n[+] 步骤2: 开始会计条目类型本地化...")
    try:
        localizer = AccountingTypesLocalizer(project_root)
        success = localizer.localize_accounting_types()
        if not success:
            print("[x] 会计条目类型本地化失败")
            return False
        print("[+] 会计条目类型本地化完成")
    except Exception as e:
        print(f"[x] 会计条目类型本地化时出错: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("[+] 所有本地化数据处理完成！")
    print(f"    本地化处理目录: {localization_dir / 'output'}")
    print(f"    最终输出目录: {project_root / 'output' / 'localization'}")
    print("\n生成的文件:")
    print("  - combined_localization.json: 所有语言的合并本地化数据 (localization/output/)")
    print("  - en_multi_lang_mapping.json: 英文到多种语言的映射 (localization/output/)")
    print("  - accountingentrytypes_localized.json: 会计条目类型的本地化数据 (output/localization/)")
    print("\n数据来源:")
    print("  - 本地化文本：从EVE在线服务器下载最新资源")
    print("  - 会计条目类型：从SDE Hoboleaks在线数据源获取")
    print("  - 无需本地EVE客户端安装，完全基于在线数据源")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
