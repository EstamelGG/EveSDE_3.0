#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新分组图标脚本
如果某个分组的图标为category_default.png，则使用该分组中第一个物品的图标替代
"""

import sqlite3
import sys
from pathlib import Path
from typing import Dict, Any


def update_groups_with_icon_filename(cursor):
    """根据 group_id 从 types 表获取 icon_filename，并更新 groups 表"""
    print("[+] 开始更新分组图标...")
    
    # 使用单个JOIN查询获取所有需要的数据（参考old版本）
    cursor.execute('''
        WITH RankedIcons AS (
            SELECT 
                t.groupID,
                t.icon_filename,
                ROW_NUMBER() OVER (
                    PARTITION BY t.groupID 
                    ORDER BY 
                        CASE WHEN t.published = 1 THEN 0 ELSE 1 END,  -- 优先已发布
                        t.metaGroupID                                -- 然后按 metaGroupID 升序
                ) AS rn
            FROM types t
            WHERE t.icon_filename NOT IN (
                "category_default.png", 
                "type_default.png", 
                "items_73_16_50.png", 
                "items_7_64_15.png", 
                "icon_0_64.png"
            )
        )
        UPDATE groups
        SET icon_filename = COALESCE(
            (SELECT icon_filename 
             FROM RankedIcons 
             WHERE groupID = groups.group_id AND rn = 1),
            "category_default.png"
        );
    ''')
    
    # 获取更新统计
    cursor.execute('''
        SELECT 
            COUNT(*) as total_groups,
            SUM(CASE WHEN icon_filename = "category_default.png" THEN 1 ELSE 0 END) as default_icons,
            SUM(CASE WHEN icon_filename != "category_default.png" THEN 1 ELSE 0 END) as updated_icons
        FROM groups
    ''')
    
    stats = cursor.fetchone()
    print(f"[+] 分组图标更新完成:")
    print(f"    总分组数: {stats[0]}")
    print(f"    使用默认图标: {stats[1]}")
    print(f"    使用物品图标: {stats[2]}")


def update_all_icons(config: Dict[str, Any]):
    """更新所有数据库的分组图标"""
    project_root = Path(__file__).parent.parent
    db_output_path = project_root / config["paths"]["db_output"]
    languages = config.get("languages", ["en"])
    
    for lang in languages:
        db_filename = db_output_path / f'item_db_{lang}.sqlite'
        
        print(f"\n[+] 处理数据库: {db_filename}")
        
        try:
            conn = sqlite3.connect(str(db_filename))
            cursor = conn.cursor()
            
            # 更新分组图标
            update_groups_with_icon_filename(cursor)
            
            # 提交事务
            conn.commit()
            conn.close()
            
            print(f"[+] 数据库 {lang} 分组图标更新完成")
            
        except Exception as e:
            print(f"[x] 处理数据库 {db_filename} 时出错: {e}")


def main(config=None):
    """主函数"""
    print("[+] 分组图标更新脚本启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 执行图标更新
    update_all_icons(config)
    
    print("\n[+] 分组图标更新完成")


if __name__ == "__main__":
    main()
