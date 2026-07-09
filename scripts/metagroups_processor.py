#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MetaGroups处理器模块
处理EVE物品衍生组数据并存储到数据库
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, Any, List
import scripts.jsonl_loader as jsonl_loader


class MetaGroupsProcessor:
    """EVE MetaGroups处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化MetaGroups处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.sde_input_path = self.project_root / config["paths"]["sde_input"]
        
        # 缓存数据
        self.metagroups_data = {}
    
    def load_metagroups_data(self):
        """加载MetaGroups数据"""
        print("[+] 加载MetaGroups数据...")
        
        # 加载MetaGroups数据
        metagroups_file = self.sde_input_path / "metaGroups.jsonl"
        if metagroups_file.exists():
            metagroups_list = jsonl_loader.load_jsonl(str(metagroups_file))
            self.metagroups_data = {item['_key']: item for item in metagroups_list}
            print(f"[+] 加载了 {len(self.metagroups_data)} 个MetaGroups")
        else:
            print(f"[x] MetaGroups文件不存在: {metagroups_file}")
    
    def create_metagroups_table(self, cursor: sqlite3.Cursor):
        """创建MetaGroups表"""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metaGroups (
                metagroup_id INTEGER NOT NULL PRIMARY KEY,
                name TEXT
            )
        ''')
    
    def process_metagroups_to_db(self, cursor: sqlite3.Cursor, lang: str = 'en'):
        """处理MetaGroups数据并插入数据库"""
        print(f"[+] 开始处理MetaGroups数据 (语言: {lang})...")
        
        # 清空现有数据
        cursor.execute('DELETE FROM metaGroups')
        
        metagroups_batch = []
        
        for metagroup_id, metagroup_data in self.metagroups_data.items():
            # 获取多语言名称
            name_dict = metagroup_data.get('name', {})
            name = name_dict.get(lang, name_dict.get('en', ''))
            
            metagroups_batch.append((metagroup_id, name))
        
        # 批量插入数据
        if metagroups_batch:
            cursor.executemany('''
                INSERT OR REPLACE INTO metaGroups (
                    metagroup_id, name
                ) VALUES (?, ?)
            ''', metagroups_batch)
        
        # 统计信息
        cursor.execute('SELECT COUNT(*) FROM metaGroups')
        metagroups_count = cursor.fetchone()[0]
        print(f"[+] MetaGroups数据处理完成: {metagroups_count} 个")
    
    def process_metagroups_to_db_all(self, cursor: sqlite3.Cursor, lang: str = 'en'):
        """
        处理所有MetaGroups数据并插入数据库
        
        Args:
            cursor: 数据库游标
            lang: 数据库使用的语言代码
        """
        print(f"[+] 开始处理MetaGroups数据 (语言: {lang})...")
        start_time = time.time()
        
        # 创建表
        self.create_metagroups_table(cursor)
        
        # 处理数据
        self.process_metagroups_to_db(cursor, lang)
        
        end_time = time.time()
        print(f"[+] MetaGroups数据处理完成，耗时: {end_time - start_time:.2f} 秒")
    
    def update_all_databases(self, config):
        """更新所有语言的数据库"""
        project_root = Path(__file__).parent.parent
        db_output_path = project_root / config["paths"]["db_output"]
        languages = config.get("languages", ["en"])
        
        # 加载MetaGroups数据
        self.load_metagroups_data()
        
        # 为每种语言创建数据库并处理数据
        for lang in languages:
            db_filename = db_output_path / f'item_db_{lang}.sqlite'
            
            print(f"\n[+] 处理数据库: {db_filename}")
            
            try:
                conn = sqlite3.connect(str(db_filename))
                cursor = conn.cursor()
                
                # 处理MetaGroups数据
                self.process_metagroups_to_db_all(cursor, lang)
                
                # 提交事务
                conn.commit()
                conn.close()
                
                print(f"[+] 数据库 {lang} 更新完成")
                
            except Exception as e:
                print(f"[x] 处理数据库 {db_filename} 时出错: {e}")


def main(config=None):
    """主函数"""
    print("[+] MetaGroups处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = MetaGroupsProcessor(config)
    processor.update_all_databases(config)
    
    print("\n[+] MetaGroups处理器完成")


if __name__ == "__main__":
    main()
