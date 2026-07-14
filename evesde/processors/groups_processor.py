#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
物品组处理器模块
处理EVE物品组数据并存储到数据库
"""

from evesde.paths import PROJECT_ROOT
from evesde.utils.single_db import get_db_path, open_item_db
from evesde.utils.wide_i18n import wide_texts, names_row
import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
import evesde.processors.jsonl_loader as jsonl_loader
import evesde.processors.icon_finder as icon_finder


class GroupsProcessor:
    """EVE物品组处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化物品组处理器"""
        self.config = config
        self.project_root = PROJECT_ROOT
        self.sde_input_path = self.project_root / config["paths"]["sde_input"]
        
        # 缓存数据
        self.groups_data = {}
        self.groups_icon_mapping = {}  # group_id -> icon_filename映射
        
        # 初始化图标查找器
        self.icon_finder = icon_finder.IconFinder(config)
    
    def load_groups_data(self):
        """加载物品组数据"""
        print("[+] 加载物品组数据...")
        
        # 加载组数据
        groups_file = self.sde_input_path / "groups.jsonl"
        groups_list = jsonl_loader.load_jsonl(str(groups_file))
        self.groups_data = {item['_key']: item for item in groups_list}
        print(f"[+] 加载了 {len(self.groups_data)} 个物品组")
        
        # 生成图标映射
        self._generate_icon_mappings()
    
    def _generate_icon_mappings(self):
        """生成物品组的图标映射"""
        print("[+] 生成物品组图标映射...")
        
        # 使用图标查找器生成映射
        self.groups_icon_mapping = self.icon_finder.generate_groups_icon_mapping(self.groups_data)
    
    def create_groups_table(self, cursor: sqlite3.Cursor):
        """创建groups表"""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                group_id INTEGER NOT NULL PRIMARY KEY,
                de_name TEXT,
                en_name TEXT,
                es_name TEXT,
                fr_name TEXT,
                ja_name TEXT,
                ko_name TEXT,
                ru_name TEXT,
                zh_name TEXT,
                iconID INTEGER,
                categoryID INTEGER,
                anchorable BOOLEAN,
                anchored BOOLEAN,
                fittableNonSingleton BOOLEAN,
                published BOOLEAN,
                useBasePrice BOOLEAN,
                icon_filename TEXT
            )
        ''')
    
    def process_groups_to_db(self, cursor: sqlite3.Cursor, lang: str = 'en'):
        """
        处理物品组数据并插入数据库
        
        Args:
            cursor: 数据库游标
            lang: 数据库使用的语言代码
        """
        print(f"[+] 开始处理物品组数据 (语言: {lang})...")
        start_time = time.time()
        
        # 创建表
        self.create_groups_table(cursor)
        
        # 清空现有数据
        cursor.execute('DELETE FROM groups')
        
        # 处理组数据
        groups_batch = []
        batch_size = 1000
        
        for group_id, group_data in self.groups_data.items():
            # 获取多语言名称
            name_dict = group_data.get('name', {})
            if not name_dict:
                continue

            names = wide_texts(name_dict)
            
            # 为特定group_id添加后缀
            suffix = ""
            if group_id == 1884:
                suffix = "(R4)"
            elif group_id == 1920:
                suffix = "(R8)"
            elif group_id == 1921:
                suffix = "(R16)"
            elif group_id == 1922:
                suffix = "(R32)"
            elif group_id == 1923:
                suffix = "(R64)"
            
            # 如果存在后缀，为所有语言添加后缀
            if suffix:
                for key in names:
                    if names[key]:  # 只有当名称不为空时才添加后缀
                        names[key] = names[key] + suffix
            
            if not names.get('en'):
                continue
            categoryID = group_data.get('categoryID', 0)
            iconID = group_data.get('iconID', 0)
            anchorable = group_data.get('anchorable', False)
            anchored = group_data.get('anchored', False)
            fittableNonSingleton = group_data.get('fittableNonSingleton', False)
            published = group_data.get('published', False)
            useBasePrice = group_data.get('useBasePrice', False)
            
            # 获取图标文件名（从生成的映射中获取）
            icon_filename = self.groups_icon_mapping.get(group_id, "category_default.png")
            
            groups_batch.append((
                group_id, *names_row(names),
                iconID, categoryID, anchorable, anchored, fittableNonSingleton,
                published, useBasePrice, icon_filename
            ))
            
            # 批量插入
            if len(groups_batch) >= batch_size:
                cursor.executemany('''
                    INSERT OR REPLACE INTO groups (
                        group_id,
                        de_name, en_name, es_name, fr_name,
                        ja_name, ko_name, ru_name, zh_name,
                        iconID, categoryID, anchorable, anchored,
                        fittableNonSingleton, published, useBasePrice, icon_filename
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', groups_batch)
                groups_batch = []
        
        # 处理剩余的数据
        if groups_batch:
            cursor.executemany('''
                INSERT OR REPLACE INTO groups (
                    group_id,
                    de_name, en_name, es_name, fr_name,
                    ja_name, ko_name, ru_name, zh_name,
                    iconID, categoryID, anchorable, anchored,
                    fittableNonSingleton, published, useBasePrice, icon_filename
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', groups_batch)
        
        # 统计信息
        cursor.execute('SELECT COUNT(*) FROM groups')
        groups_count = cursor.fetchone()[0]
        
        end_time = time.time()
        print(f"[+] 物品组数据处理完成:")
        print(f"    - 组: {groups_count} 个")
        print(f"    - 耗时: {end_time - start_time:.2f} 秒")
    
    def backfill_icons_from_types(self, cursor: sqlite3.Cursor) -> None:
        """用组内代表物品图标无条件覆盖 groups.icon_filename（与 2.0 一致）。"""
        print("[+] 回填分组图标（自 types）...")
        cursor.execute('''
            WITH RankedIcons AS (
                SELECT
                    t.groupID,
                    t.icon_filename,
                    ROW_NUMBER() OVER (
                        PARTITION BY t.groupID
                        ORDER BY
                            CASE WHEN t.published = 1 THEN 0 ELSE 1 END,
                            t.metaGroupID
                    ) AS rn
                FROM types t
                WHERE t.icon_filename NOT IN (
                    'category_default.png',
                    'type_default.png',
                    'items_73_16_50.png',
                    'items_7_64_15.png',
                    'icon_0_64.png'
                )
            )
            UPDATE groups
            SET icon_filename = COALESCE(
                (SELECT icon_filename
                 FROM RankedIcons
                 WHERE groupID = groups.group_id AND rn = 1),
                'category_default.png'
            );
        ''')
        cursor.execute('''
            SELECT
                COUNT(*) AS total_groups,
                SUM(CASE WHEN icon_filename = 'category_default.png' THEN 1 ELSE 0 END) AS default_icons,
                SUM(CASE WHEN icon_filename != 'category_default.png' THEN 1 ELSE 0 END) AS filled_icons
            FROM groups
        ''')
        total, default_icons, filled = cursor.fetchone()
        print(f"[+] 分组图标回填完成: 总计 {total}, 默认 {default_icons}, 已填 {filled}")

    def update_all_databases(self, config):
        """更新所有语言的数据库"""
        project_root = PROJECT_ROOT
        db_output_path = project_root / config["paths"]["db_output"]
        languages = config.get("languages", ["en"])
        
        # 加载组数据
        self.load_groups_data()
        
        db_file = get_db_path(config)
        print(f"\n[+] 处理数据库: {db_file}")
        try:
            with open_item_db(config) as conn:
                self.process_groups_to_db(conn.cursor(), 'en')
            print("[+] 单库更新完成")
        except Exception as e:
            print(f"[x] 处理数据库 {db_file} 时出错: {e}")


def backfill_group_icons(config: Optional[Dict[str, Any]] = None) -> bool:
    """types 写入后回填 groups 图标。"""
    if config is None:
        config_path = PROJECT_ROOT / "config.json"
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    with open_item_db(config) as conn:
        GroupsProcessor(config).backfill_icons_from_types(conn.cursor())
    return True


def main(config=None):
    """主函数"""
    print("[+] 物品组处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = PROJECT_ROOT / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = GroupsProcessor(config)
    processor.update_all_databases(config)
    
    print("\n[+] 物品组处理器完成")


if __name__ == "__main__":
    main()
