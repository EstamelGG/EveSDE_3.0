#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dogma效果处理器模块
处理EVE Dogma效果数据并存储到数据库
包括效果、属性分类、属性单位等信息
"""

from evesde.paths import PROJECT_ROOT
from evesde.utils.single_db import get_db_path
from evesde.utils.wide_i18n import wide_texts, names_row
import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, Any, List
import evesde.processors.jsonl_loader as jsonl_loader


class DogmaEffectsProcessor:
    """EVE Dogma效果处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化Dogma效果处理器"""
        self.config = config
        self.project_root = PROJECT_ROOT
        self.sde_input_path = self.project_root / config["paths"]["sde_input"]
        
        # 缓存数据
        self.dogma_effects_data = {}
    
    def load_dogma_effects_data(self):
        """加载Dogma效果数据"""
        print("[+] 加载Dogma效果数据...")
        
        # 加载Dogma效果数据
        effects_file = self.sde_input_path / "dogmaEffects.jsonl"
        effects_list = jsonl_loader.load_jsonl(str(effects_file))
        self.dogma_effects_data = {item['_key']: item for item in effects_list}
        print(f"[+] 加载了 {len(self.dogma_effects_data)} 个Dogma效果")
    
    def create_dogma_effects_table(self, cursor: sqlite3.Cursor):
        """创建dogmaEffects表"""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dogmaEffects (
                effect_id INTEGER NOT NULL PRIMARY KEY,
                effect_category INTEGER,
                effect_name TEXT,
                de_name TEXT,
                en_name TEXT,
                es_name TEXT,
                fr_name TEXT,
                ja_name TEXT,
                ko_name TEXT,
                ru_name TEXT,
                zh_name TEXT,
                de_description TEXT,
                en_description TEXT,
                es_description TEXT,
                fr_description TEXT,
                ja_description TEXT,
                ko_description TEXT,
                ru_description TEXT,
                zh_description TEXT,
                published BOOLEAN,
                is_assistance BOOLEAN,
                is_offensive BOOLEAN,
                resistance_attribute_id INTEGER,
                modifier_info TEXT
            )
        ''')
    
    
    def process_dogma_effects_to_db(self, cursor: sqlite3.Cursor, lang: str = 'en'):
        """
        处理Dogma效果数据并插入数据库
        
        Args:
            cursor: 数据库游标
            lang: 数据库使用的语言代码
        """
        print(f"[+] 开始处理Dogma效果数据 (语言: {lang})...")
        start_time = time.time()
        
        # 创建表
        self.create_dogma_effects_table(cursor)
        
        # 清空现有数据
        cursor.execute('DELETE FROM dogmaEffects')
        
        # 处理Dogma效果数据
        effects_batch = []
        batch_size = 1000
        
        _fx_sql = '''
            INSERT OR REPLACE INTO dogmaEffects (
                effect_id, effect_category, effect_name,
                de_name, en_name, es_name, fr_name,
                ja_name, ko_name, ru_name, zh_name,
                de_description, en_description, es_description, fr_description,
                ja_description, ko_description, ru_description, zh_description,
                published, is_assistance, is_offensive, resistance_attribute_id, modifier_info
            ) VALUES ({ph})
        '''.format(ph=", ".join(["?"] * 24))

        for effect_id, effect_data in self.dogma_effects_data.items():
            # 获取基本字段
            # 新版本：effectName重命名为name
            effect_name = effect_data.get('name', effect_data.get('effectName', None))
            if isinstance(effect_name, dict):
                effect_name = effect_name.get('en', '')

            displays = wide_texts(effect_data.get('displayName'))
            descs = wide_texts(effect_data.get('description'))
            
            # 效果分类特殊处理
            if effect_name == "online":  # 打补丁修复
                effect_category = 4
            else:
                # 新版本：effectCategory重命名为effectCategoryID
                effect_category = effect_data.get('effectCategoryID', effect_data.get('effectCategory', None))
            
            published = effect_data.get('published', False)
            is_assistance = effect_data.get('isAssistance', False)
            is_offensive = effect_data.get('isOffensive', False)
            resistance_attribute_id = effect_data.get('resistanceAttributeID', None)
            
            # 处理modifierInfo字段，转换为JSON字符串
            modifier_info = effect_data.get('modifierInfo', None)
            modifier_info_json = json.dumps(modifier_info) if modifier_info is not None else None
            
            # 多语言字段处理
            effects_batch.append((
                effect_id, effect_category, effect_name,
                *names_row(displays), *names_row(descs),
                published, is_assistance, is_offensive, resistance_attribute_id, modifier_info_json
            ))
            
            # 批量插入
            if len(effects_batch) >= batch_size:
                cursor.executemany(_fx_sql, effects_batch)
                effects_batch = []

        if effects_batch:
            cursor.executemany(_fx_sql, effects_batch)
        
        # 统计信息
        cursor.execute('SELECT COUNT(*) FROM dogmaEffects')
        effects_count = cursor.fetchone()[0]
        
        end_time = time.time()
        print(f"[+] Dogma效果数据处理完成:")
        print(f"    - 效果: {effects_count} 个")
        print(f"    - 耗时: {end_time - start_time:.2f} 秒")
    
    def update_all_databases(self, config):
        """更新所有语言的数据库"""
        project_root = PROJECT_ROOT
        db_output_path = project_root / config["paths"]["db_output"]
        languages = config.get("languages", ["en"])
        
        # 加载Dogma效果数据
        self.load_dogma_effects_data()
        
        db_file = get_db_path(config)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        print(f"\n[+] 处理数据库: {db_file}")
        try:
            conn = sqlite3.connect(str(db_file))
            cursor = conn.cursor()
            self.process_dogma_effects_to_db(cursor, 'en')
            conn.commit()
            conn.close()
            print("[+] 单库更新完成")
        except Exception as e:
            print(f"[x] 处理数据库 {db_file} 时出错: {e}")


def main(config=None):
    """主函数"""
    print("[+] Dogma效果处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = PROJECT_ROOT / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = DogmaEffectsProcessor(config)
    processor.update_all_databases(config)
    
    print("\n[+] Dogma效果处理器完成")


if __name__ == "__main__":
    main()
