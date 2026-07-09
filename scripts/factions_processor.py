#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
派系处理器模块
处理EVE派系数据并存储到数据库
"""

import json
import sqlite3
import time
import os
from pathlib import Path
from utils.http_client import get
from typing import Dict, Any, List
import scripts.jsonl_loader as jsonl_loader


class FactionsProcessor:
    """EVE派系处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化派系处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.sde_input_path = self.project_root / config["paths"]["sde_input"]
        self.custom_icons_path = self.project_root / "custom_icons"
        
        # 确保自定义图标目录存在
        self.custom_icons_path.mkdir(parents=True, exist_ok=True)
        
        # 缓存数据
        self.factions_data = {}
    
    def load_factions_data(self):
        """加载派系数据"""
        print("[+] 加载派系数据...")
        
        # 加载派系数据
        factions_file = self.sde_input_path / "factions.jsonl"
        if factions_file.exists():
            factions_list = jsonl_loader.load_jsonl(str(factions_file))
            self.factions_data = {item['_key']: item for item in factions_list}
            print(f"[+] 加载了 {len(self.factions_data)} 个派系")
        else:
            print(f"[x] 派系文件不存在: {factions_file}")
    
    def download_faction_icons(self):
        """下载派系图标"""
        print("[+] 开始下载派系图标...")
        
        # 下载默认图标
        default_icon_path = self.custom_icons_path / "corporations_default.png"
        if not default_icon_path.exists():
            self._download_default_icon(default_icon_path)
        
        # 过滤出需要下载的派系图标
        faction_ids_to_download = []
        for faction_id in self.factions_data.keys():
            faction_ids_to_download.append(faction_id)
        
        if not faction_ids_to_download:
            print("[+] 所有派系图标已存在，跳过下载")
            return
        
        print(f"[+] 准备下载 {len(faction_ids_to_download)} 个派系图标...")
        
        # 下载图标
        success_count = 0
        for faction_id in faction_ids_to_download:
            if self._download_single_faction_icon(faction_id, default_icon_path):
                success_count += 1
        
        print(f"[+] 派系图标下载完成: {success_count}/{len(faction_ids_to_download)} 成功")
    
    def _download_single_faction_icon(self, faction_id: int, default_icon_path: Path) -> bool:
        """下载单个派系图标"""
        icon_url = f"https://images.evetech.net/corporations/{faction_id}/logo"
        icon_path = self.custom_icons_path / f"faction_{faction_id}.png"
        
        try:
            response = get(icon_url, timeout=10, verify=False)
            
            # 保存图标
            with open(icon_path, 'wb') as f:
                f.write(response.content)
            
            print(f"[+] 成功下载图标: {icon_url} -> faction_{faction_id}")
            return True
            
        except Exception as e:
            print(f"[x] 下载 faction_{faction_id} 失败: {str(e)}")
        
        # 如果所有重试都失败，使用默认图标
        try:
            import shutil
            shutil.copy2(default_icon_path, icon_path)
            print(f"[!] 使用默认图标: faction_{faction_id}")
            return False
        except Exception as e:
            print(f"[x] 复制默认图标失败 faction_{faction_id}: {str(e)}")
            return False
    
    def _download_default_icon(self, default_icon_path: Path):
        """下载默认图标"""
        try:
            response = get("https://images.evetech.net/corporations/1/logo", timeout=10, verify=False)
            
            with open(default_icon_path, 'wb') as f:
                f.write(response.content)
            
            print("[+] 下载默认图标成功")
            return True
            
        except Exception as e:
            print(f"[x] 下载默认图标失败: {str(e)}")
            return False
    
    def create_factions_table(self, cursor: sqlite3.Cursor):
        """创建派系表"""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS factions (
                id INTEGER NOT NULL PRIMARY KEY,
                name TEXT,
                de_name TEXT,
                en_name TEXT,
                es_name TEXT,
                fr_name TEXT,
                ja_name TEXT,
                ko_name TEXT,
                ru_name TEXT,
                zh_name TEXT,
                description TEXT,
                shortDescription TEXT,
                iconName TEXT
            )
        ''')
    
    def process_factions_to_db(self, cursor: sqlite3.Cursor, lang: str = 'en'):
        """处理派系数据并插入数据库"""
        print(f"[+] 开始处理派系数据 (语言: {lang})...")
        
        # 清空现有数据
        cursor.execute('DELETE FROM factions')
        
        factions_batch = []
        batch_size = 100
        
        for faction_id, faction_data in self.factions_data.items():
            # 获取当前语言的名称作为主要name
            name_data = faction_data.get('name', {})
            name = name_data.get(lang, name_data.get('en', ''))
            
            # 获取所有语言的名称
            names = {
                'de': name_data.get('de', name),
                'en': name_data.get('en', name),
                'es': name_data.get('es', name),
                'fr': name_data.get('fr', name),
                'ja': name_data.get('ja', name),
                'ko': name_data.get('ko', name),
                'ru': name_data.get('ru', name),
                'zh': name_data.get('zh', name)
            }
            
            # 获取当前语言的描述信息
            description_data = faction_data.get('description', {})
            description = description_data.get(lang, description_data.get('en', ''))
            
            # 获取当前语言的简短描述信息
            short_description_data = faction_data.get('shortDescription', {})
            short_description = short_description_data.get(lang, short_description_data.get('en', ''))
            
            # 设置图标文件名
            icon_name = f"faction_{faction_id}.png"
            
            factions_batch.append((
                faction_id, name, names['de'], names['en'], names['es'],
                names['fr'], names['ja'], names['ko'], names['ru'], names['zh'],
                description, short_description, icon_name
            ))
            
            # 批量插入
            if len(factions_batch) >= batch_size:
                cursor.executemany('''
                    INSERT OR REPLACE INTO factions (
                        id, name, de_name, en_name, es_name, fr_name, 
                        ja_name, ko_name, ru_name, zh_name, description, 
                        shortDescription, iconName
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', factions_batch)
                factions_batch = []
        
        # 处理剩余数据
        if factions_batch:
            cursor.executemany('''
                INSERT OR REPLACE INTO factions (
                    id, name, de_name, en_name, es_name, fr_name, 
                    ja_name, ko_name, ru_name, zh_name, description, 
                    shortDescription, iconName
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', factions_batch)
        
        # 统计信息
        cursor.execute('SELECT COUNT(*) FROM factions')
        factions_count = cursor.fetchone()[0]
        print(f"[+] 派系数据处理完成: {factions_count} 个")
    
    def process_factions_data(self, cursor: sqlite3.Cursor, lang: str = 'en'):
        """
        处理所有派系数据并插入数据库
        
        Args:
            cursor: 数据库游标
            lang: 数据库使用的语言代码
        """
        print(f"[+] 开始处理派系数据 (语言: {lang})...")
        start_time = time.time()
        
        # 创建表
        self.create_factions_table(cursor)
        
        # 处理派系数据
        self.process_factions_to_db(cursor, lang)
        
        end_time = time.time()
        print(f"[+] 派系数据处理完成，耗时: {end_time - start_time:.2f} 秒")
    
    def update_all_databases(self, config):
        """更新所有语言的数据库"""
        project_root = Path(__file__).parent.parent
        db_output_path = project_root / config["paths"]["db_output"]
        languages = config.get("languages", ["en"])
        
        # 加载派系数据
        self.load_factions_data()
        
        # 下载派系图标
        self.download_faction_icons()
        
        # 为每种语言创建数据库并处理数据
        for lang in languages:
            db_filename = db_output_path / f'item_db_{lang}.sqlite'
            
            print(f"\n[+] 处理数据库: {db_filename}")
            
            try:
                conn = sqlite3.connect(str(db_filename))
                cursor = conn.cursor()
                
                # 处理派系数据
                self.process_factions_data(cursor, lang)
                
                # 提交事务
                conn.commit()
                conn.close()
                
                print(f"[+] 数据库 {lang} 更新完成")
                
            except Exception as e:
                print(f"[x] 处理数据库 {db_filename} 时出错: {e}")


def main(config=None):
    """主函数"""
    print("[+] 派系处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = FactionsProcessor(config)
    processor.update_all_databases(config)
    
    print("\n[+] 派系处理器完成")


if __name__ == "__main__":
    main()
