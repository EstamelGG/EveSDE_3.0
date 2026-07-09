#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试物品详细信息提取器
"""

import sys
from pathlib import Path

# 添加scripts目录到Python路径
sys.path.append(str(Path(__file__).parent / "scripts"))

from scripts.item_detail_extractor import ItemDetailExtractor

def test_extractor():
    """测试提取器功能"""
    
    # 测试数据库路径（需要根据实际情况调整）
    db_path = '/Users/gg/Documents/GitHub/EVE-Nexus/EVE Nexus/utils/sde/db/item_db_zh.sqlite'
    output_dir = "./test_output"
    
    if not Path(db_path).exists():
        print(f"[!] 数据库文件不存在: {db_path}")
        print("[!] 请先运行SDE构建脚本生成数据库")
        return
    
    try:
        # 创建提取器
        extractor = ItemDetailExtractor(db_path, output_dir)
        
        # 测试获取已发布物品列表
        print("=== 测试获取已发布物品列表 ===")
        type_ids = extractor.get_published_type_ids()
        print(f"找到 {len(type_ids)} 个已发布物品")
        
        if type_ids:
            # 测试获取单个物品信息
            print(f"\n=== 测试获取单个物品信息 (type_id: {639}) ===")
            item_data = extractor.get_item_detail(639)
            if item_data:
                print(f"物品名称: {item_data['name']}")
                print(f"分类: {item_data['category_name']}")
                print(f"属性数量: {len(item_data['attributes'])}")
                print(f"特性数量: {len(item_data['traits'])}")
                
                # 测试保存文件
                print(f"\n=== 测试保存物品信息 ===")
                if extractor.save_item_detail(item_data):
                    print("保存成功")
                else:
                    print("保存失败")
            else:
                print("获取物品信息失败")
        
        print("\n=== 测试完成 ===")
        
    except Exception as e:
        print(f"[x] 测试失败: {e}")

if __name__ == "__main__":
    test_extractor()
