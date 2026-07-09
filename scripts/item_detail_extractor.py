#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
物品详细信息提取器
从SDE数据库中提取所有已发布物品的详细信息并保存为JSON文件
"""

import sqlite3
import json
import os
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
import time


class ItemDetailExtractor:
    """物品详细信息提取器"""
    
    def __init__(self, db_path: str, output_dir: str):
        """
        初始化提取器
        
        Args:
            db_path: 数据库文件路径
            output_dir: 输出目录路径
        """
        self.db_path = Path(db_path)
        self.output_dir = Path(output_dir)
        
        # 检查数据库文件是否存在
        if not self.db_path.exists():
            raise FileNotFoundError(f"数据库文件不存在: {self.db_path}")
        
        # 清空并重新创建输出目录
        if self.output_dir.exists():
            print(f"[+] 清空现有输出目录: {self.output_dir}")
            shutil.rmtree(self.output_dir)
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"[+] 初始化物品详细信息提取器")
        print(f"[+] 数据库路径: {self.db_path}")
        print(f"[+] 输出目录: {self.output_dir}")
    
    def get_published_type_ids(self) -> List[int]:
        """
        获取所有已发布物品的type_id
        排除categoryID为91和2118的物品
        
        Returns:
            list: 已发布物品的type_id列表
        """
        print("[+] 开始检索已发布物品...")
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            query = """
            SELECT type_id 
            FROM types 
            WHERE published = 1 
            AND NOT categoryID IN (91, 2118, 30, 2100)
            ORDER BY type_id
            """
            
            cursor.execute(query)
            type_ids = [row[0] for row in cursor.fetchall()]
            
            print(f"[+] 找到 {len(type_ids)} 个已发布物品")
            return type_ids
            
        except Exception as e:
            print(f"[x] 检索已发布物品失败: {e}")
            return []
        finally:
            conn.close()
    
    def get_item_detail(self, type_id: int) -> Optional[Dict[str, Any]]:
        """
        获取单个物品的详细信息
        
        Args:
            type_id: 物品类型ID
        
        Returns:
            dict: 物品详细信息字典，如果未找到则返回None
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            query = """
            SELECT 
                json_object(
                    'type_id', t.type_id,
                    'name', t.name,
                    'description', t.description,
                    'volume', t.volume,
                    'repackaged_volume', t.repackaged_volume,
                    'capacity', t.capacity,
                    'mass', t.mass,
                    'category_name', t.category_name,
                    'group_name', t.group_name,
                    'attributes', (
                        SELECT json_group_array(
                            json_object(
                                'attribute_name', da.name,
                                'value', ta.value,
                                'categoryID', da.categoryID,
                                'display_name', da.display_name,
                                'unit_name', da.unitName
                            )
                        )
                        FROM typeAttributes ta
                        LEFT JOIN dogmaAttributes da ON ta.attribute_id = da.attribute_id
                        WHERE ta.type_id = ?
                        ORDER BY ta.attribute_id
                    ),
                    'traits', (
                        SELECT json_group_array(json_object('content', content))
                        FROM traits 
                        WHERE typeid = ?
                        ORDER BY 
                            CASE 
                                WHEN bonus_type = 'roleBonuses' THEN 1
                                WHEN bonus_type = 'typeBonuses' THEN 2  
                                WHEN bonus_type = 'miscBonuses' THEN 3
                                ELSE 4
                            END,
                            COALESCE(importance, 999) ASC,
                            content ASC
                    )
                ) as item_data
            FROM types t
            WHERE t.type_id = ?;
            """
            
            cursor.execute(query, (type_id, type_id, type_id))
            result = cursor.fetchone()
            
            if result and result['item_data']:
                return json.loads(result['item_data'])
            else:
                return None
                
        except Exception as e:
            print(f"[!] 查询物品 {type_id} 失败: {e}")
            return None
        finally:
            conn.close()
    
    def save_item_detail(self, item_data: Dict[str, Any]) -> bool:
        """
        保存物品详细信息到JSON文件
        
        Args:
            item_data: 物品详细信息字典
        
        Returns:
            bool: 保存是否成功
        """
        try:
            type_id = item_data['type_id']
            filename = f"item_{type_id}.json"
            filepath = self.output_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(item_data, f, ensure_ascii=False, indent=2)
            
            return True
            
        except Exception as e:
            print(f"[!] 保存物品 {item_data.get('type_id', 'unknown')} 失败: {e}")
            return False
    
    def extract_all_items(self) -> bool:
        """
        提取所有已发布物品的详细信息
        
        Returns:
            bool: 提取是否成功
        """
        print("[+] 开始提取所有物品详细信息...")
        start_time = time.time()
        
        # 获取所有已发布物品的type_id
        type_ids = self.get_published_type_ids()
        if not type_ids:
            print("[x] 未找到已发布物品，提取终止")
            return False
        
        success_count = 0
        failed_count = 0
        
        # 逐个查询和保存物品信息
        for i, type_id in enumerate(type_ids, 1):
            if i % 100 == 0 or i == len(type_ids):
                print(f"[+] 进度: {i}/{len(type_ids)} ({i/len(type_ids)*100:.1f}%)")
            
            # 获取物品详细信息
            item_data = self.get_item_detail(type_id)
            if item_data:
                # 保存到文件
                if self.save_item_detail(item_data):
                    success_count += 1
                else:
                    failed_count += 1
            else:
                failed_count += 1
                print(f"[!] 物品 {type_id} 详细信息获取失败")
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"\n[+] 物品详细信息提取完成")
        print(f"[+] 总耗时: {duration:.2f} 秒")
        print(f"[+] 成功: {success_count} 个")
        print(f"[+] 失败: {failed_count} 个")
        print(f"[+] 成功率: {success_count/(success_count+failed_count)*100:.1f}%")
        
        return success_count > 0
    


def item_detail_extract(db_path: str, output_dir: str) -> bool:
    """
    物品详细信息提取主函数
    
    Args:
        db_path: 数据库文件路径
        output_dir: 输出目录路径
    
    Returns:
        bool: 提取是否成功
    """
    try:
        extractor = ItemDetailExtractor(db_path, output_dir)
        
        # 提取所有物品详细信息
        success = extractor.extract_all_items()
        
        return success
        
    except Exception as e:
        print(f"[x] 物品详细信息提取失败: {e}")
        return False


def main():
    """主函数 - 用于测试"""
    import sys
    
    if len(sys.argv) != 3:
        print("使用方法: python item_detail_extractor.py <数据库路径> <输出目录>")
        sys.exit(1)
    
    db_path = sys.argv[1]
    output_dir = sys.argv[2]
    
    success = item_detail_extract(db_path, output_dir)
    if success:
        print("[+] 物品详细信息提取成功")
    else:
        print("[x] 物品详细信息提取失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
