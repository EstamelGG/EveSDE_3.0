#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
物品组处理器模块
处理EVE物品组数据并存储到数据库
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, Any, List
import scripts.jsonl_loader as jsonl_loader
import scripts.icon_finder as icon_finder


class GroupsProcessor:
    """EVE物品组处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化物品组处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
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
                name TEXT,
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
            
            # 获取英语名称作为回退值
            en_name = name_dict.get('en', '')
            
            # 获取所有语言的名称，如果不存在则回退到英语
            names = {
                'de': name_dict.get('de', en_name),
                'en': en_name,
                'es': name_dict.get('es', en_name),
                'fr': name_dict.get('fr', en_name),
                'ja': name_dict.get('ja', en_name),
                'ko': name_dict.get('ko', en_name),
                'ru': name_dict.get('ru', en_name),
                'zh': name_dict.get('zh', en_name)
            }
            
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
            
            # 获取当前语言的名称作为主要name，如果不存在则回退到英语
            name = names.get(lang, en_name)
            
            # 获取其他字段
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
                group_id, name,
                names['de'], names['en'], names['es'], names['fr'],
                names['ja'], names['ko'], names['ru'], names['zh'],
                iconID, categoryID, anchorable, anchored, fittableNonSingleton,
                published, useBasePrice, icon_filename
            ))
            
            # 批量插入
            if len(groups_batch) >= batch_size:
                cursor.executemany('''
                    INSERT OR REPLACE INTO groups (
                        group_id, name,
                        de_name, en_name, es_name, fr_name,
                        ja_name, ko_name, ru_name, zh_name,
                        iconID, categoryID, anchorable, anchored,
                        fittableNonSingleton, published, useBasePrice, icon_filename
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', groups_batch)
                groups_batch = []
        
        # 处理剩余的数据
        if groups_batch:
            cursor.executemany('''
                INSERT OR REPLACE INTO groups (
                    group_id, name,
                    de_name, en_name, es_name, fr_name,
                    ja_name, ko_name, ru_name, zh_name,
                    iconID, categoryID, anchorable, anchored,
                    fittableNonSingleton, published, useBasePrice, icon_filename
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', groups_batch)
        
        # 统计信息
        cursor.execute('SELECT COUNT(*) FROM groups')
        groups_count = cursor.fetchone()[0]
        
        end_time = time.time()
        print(f"[+] 物品组数据处理完成:")
        print(f"    - 组: {groups_count} 个")
        print(f"    - 耗时: {end_time - start_time:.2f} 秒")
    
    def update_all_databases(self, config):
        """更新所有语言的数据库"""
        project_root = Path(__file__).parent.parent
        db_output_path = project_root / config["paths"]["db_output"]
        languages = config.get("languages", ["en"])
        
        # 加载组数据
        self.load_groups_data()
        
        # 为每种语言创建数据库并处理数据
        for lang in languages:
            db_filename = db_output_path / f'item_db_{lang}.sqlite'
            
            print(f"\n[+] 处理数据库: {db_filename}")
            
            try:
                conn = sqlite3.connect(str(db_filename))
                cursor = conn.cursor()
                
                # 处理组数据
                self.process_groups_to_db(cursor, lang)
                
                # 提交事务
                conn.commit()
                conn.close()
                
                print(f"[+] 数据库 {lang} 更新完成")
                
            except Exception as e:
                print(f"[x] 处理数据库 {db_filename} 时出错: {e}")


def main(config=None):
    """主函数"""
    print("[+] 物品组处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = GroupsProcessor(config)
    processor.update_all_databases(config)
    
    print("\n[+] 物品组处理器完成")


if __name__ == "__main__":
    main()
