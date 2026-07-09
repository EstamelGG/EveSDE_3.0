#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
物品分类处理器模块
处理EVE物品分类数据并存储到数据库
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
import scripts.jsonl_loader as jsonl_loader
import scripts.icon_finder as icon_finder


class CategoriesProcessor:
    """EVE物品分类处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化物品分类处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.sde_input_path = self.project_root / config["paths"]["sde_input"]
        
        # 缓存数据
        self.categories_data = {}
        
        # 初始化图标查找器
        self.icon_finder = icon_finder.IconFinder(config)
        
        # 图标缓存目录
        self.custom_icons_path = self.project_root / "custom_icons"
        self.custom_icons_path.mkdir(parents=True, exist_ok=True)
        
        # 分类ID到图标文件名的映射（已更新为统一的category_{id}.png格式）
        self.categories_id_icon_map = {
            0: "res:/ui/texture/icons/7_64_4.png",
            1: "res:/ui/texture/icons/70_128_11.png",
            2: "type_6_64.png",
            3: "type_1932_64.png",
            4: "type_34_64.png",
            5: "type_29668_64.png",
            6: "res:/ui/texture/icons/26_64_2.png",
            7: "res:/ui/texture/icons/2_64_11.png",
            8: "res:/ui/texture/icons/5_64_2.png",
            9: "type_1002_64.png",
            10: "res:/ui/texture/icons/6_64_3.png",
            11: "res:/ui/texture/icons/26_64_10.png",
            14: "res:/ui/texture/icons/modules/fleetboost_infobase.png",
            16: "type_2403_64.png",
            17: "type_11068_64.png",
            18: "type_2454_64.png",
            20: "res:/ui/texture/icons/40_64_16.png",
            22: "type_33475_64.png",
            23: "type_17174_64.png",
            24: "res:/ui/texture/icons/comprfuel_amarr.png",
            25: "res:/ui/texture/icons/inventory/moonasteroid_r4.png",
            30: "res:/ui/texture/icons/inventory/cratexvishirt.png",
            32: "res:/ui/texture/icons/76_64_7.png",
            34: "type_30752_64.png",
            35: "res:/ui/texture/icons/55_64_11.png",
            39: "res:/ui/texture/icons/95_64_6.png",
            40: "type_32458_64.png",
            41: "type_2409_64.png",
            42: "res:/ui/texture/icons/97_64_10.png",
            43: "res:/ui/texture/icons/99_64_8.png",
            46: "type_2233_64.png",
            63: "type_19658_64.png",
            65: "type_40340_64.png",
            66: "type_35923_64.png",
            87: "type_23061_64.png",
            91: "res:/ui/texture/icons/rewardtrack/crateskincontainer.png",
            2100: "type_57203_64.png",
            2118: "type_83291_64.png",
            2143: "type_81143_64.png",
        }
    
    def load_categories_data(self):
        """加载物品分类数据"""
        print("[+] 加载物品分类数据...")
        
        # 加载分类数据
        categories_file = self.sde_input_path / "categories.jsonl"
        categories_list = jsonl_loader.load_jsonl(str(categories_file))
        self.categories_data = {item['_key']: item for item in categories_list}
        print(f"[+] 加载了 {len(self.categories_data)} 个物品分类")
    
    def download_category_icon(self, category_id: int, icon_source: str) -> str:
        """
        下载分类图标
        
        Args:
            category_id: 分类ID
            icon_source: 图标源（res路径或type文件名）
            
        Returns:
            下载后的图标文件名
        """
        # 生成目标文件名
        target_filename = f"category_{category_id}.png"
        target_path = self.custom_icons_path / target_filename
        
        # 如果图标已存在，直接返回
        if target_path.exists():
            return target_filename
        
        try:
            # 判断图标源类型
            if icon_source.startswith("res:/"):
                # 从resfileindex下载
                content = self.icon_finder._get_icon_file_content(icon_source)
                if content:
                    with open(target_path, 'wb') as f:
                        f.write(content)
                    print(f"[+] 下载分类图标: {category_id} -> {target_filename}")
                    return target_filename
                else:
                    print(f"[!] 无法下载res图标: {icon_source}")
                    return self.download_default_category_icon()
            
            elif icon_source.startswith("type_"):
                # 从output/icons目录复制
                source_path = self.project_root / "output_icons" / icon_source
                if source_path.exists():
                    import shutil
                    shutil.copy2(source_path, target_path)
                    print(f"[+] 复制分类图标: {category_id} -> {target_filename}")
                    return target_filename
                else:
                    print(f"[!] 找不到type图标文件: {source_path}")
                    return self.download_default_category_icon()
            
            else:
                print(f"[!] 未知的图标源格式: {icon_source}")
                return self.download_default_category_icon()
                
        except Exception as e:
            print(f"[!] 下载分类图标失败 {category_id}: {e}")
            return self.download_default_category_icon()
    
    def download_default_category_icon(self) -> str:
        """
        下载默认分类图标
        """
        default_filename = "category_default.png"
        default_path = self.custom_icons_path / default_filename
        
        if default_path.exists():
            return default_filename
        
        try:
            # 使用默认图标路径
            default_res_path = "res:/ui/texture/icons/73_16_50.png"
            content = self.icon_finder._get_icon_file_content(default_res_path)
            
            if content:
                with open(default_path, 'wb') as f:
                    f.write(content)
                print(f"[+] 下载默认分类图标: {default_filename}")
                return default_filename
            else:
                print(f"[!] 无法下载默认分类图标")
                return default_filename
                
        except Exception as e:
            print(f"[!] 下载默认分类图标失败: {e}")
            return default_filename
    
    def create_categories_table(self, cursor: sqlite3.Cursor):
        """创建categories表"""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                category_id INTEGER NOT NULL PRIMARY KEY,
                name TEXT,
                de_name TEXT,
                en_name TEXT,
                es_name TEXT,
                fr_name TEXT,
                ja_name TEXT,
                ko_name TEXT,
                ru_name TEXT,
                zh_name TEXT,
                icon_filename TEXT,
                iconID INTEGER,
                published BOOLEAN
            )
        ''')
    
    def process_categories_to_db(self, cursor: sqlite3.Cursor, lang: str = 'en'):
        """
        处理物品分类数据并插入数据库
        
        Args:
            cursor: 数据库游标
            lang: 数据库使用的语言代码
        """
        print(f"[+] 开始处理物品分类数据 (语言: {lang})...")
        start_time = time.time()
        
        # 创建表
        self.create_categories_table(cursor)
        
        # 清空现有数据
        cursor.execute('DELETE FROM categories')
        
        # 处理分类数据
        categories_batch = []
        batch_size = 100  # 分类数据量不大
        
        for category_id, category_data in self.categories_data.items():
            # 获取多语言名称
            name_dict = category_data.get('name', {})
            if not name_dict:
                continue
            
            # 获取当前语言的名称作为主要name
            name = name_dict.get(lang, name_dict.get('en', ''))
            
            # 获取所有语言的名称
            names = {
                'de': name_dict.get('de', name),
                'en': name_dict.get('en', name),
                'es': name_dict.get('es', name),
                'fr': name_dict.get('fr', name),
                'ja': name_dict.get('ja', name),
                'ko': name_dict.get('ko', name),
                'ru': name_dict.get('ru', name),
                'zh': name_dict.get('zh', name)
            }
            
            if not name:
                continue
            
            # 获取其他字段
            published = category_data.get('published', False)
            iconID = category_data.get('iconID', 0)
            
            # 获取图标文件名（动态下载）
            if category_id in self.categories_id_icon_map:
                # 在映射中的分类，使用指定的图标源
                icon_source = self.categories_id_icon_map[category_id]
                icon_filename = self.download_category_icon(category_id, icon_source)
            else:
                # 不在映射中的分类，使用默认图标
                icon_filename = self.download_default_category_icon()
            
            categories_batch.append((
                category_id, name,
                names['de'], names['en'], names['es'], names['fr'],
                names['ja'], names['ko'], names['ru'], names['zh'],
                icon_filename, iconID, published
            ))
            
            # 批量插入
            if len(categories_batch) >= batch_size:
                cursor.executemany('''
                    INSERT OR REPLACE INTO categories (
                        category_id, name,
                        de_name, en_name, es_name, fr_name,
                        ja_name, ko_name, ru_name, zh_name,
                        icon_filename, iconID, published
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', categories_batch)
                categories_batch = []
        
        # 处理剩余的数据
        if categories_batch:
            cursor.executemany('''
                INSERT OR REPLACE INTO categories (
                    category_id, name,
                    de_name, en_name, es_name, fr_name,
                    ja_name, ko_name, ru_name, zh_name,
                    icon_filename, iconID, published
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', categories_batch)
        
        # 统计信息
        cursor.execute('SELECT COUNT(*) FROM categories')
        categories_count = cursor.fetchone()[0]
        
        end_time = time.time()
        print(f"[+] 物品分类数据处理完成:")
        print(f"    - 分类: {categories_count} 个")
        print(f"    - 耗时: {end_time - start_time:.2f} 秒")
    
    def update_all_databases(self, config):
        """更新所有语言的数据库"""
        project_root = Path(__file__).parent.parent
        db_output_path = project_root / config["paths"]["db_output"]
        languages = config.get("languages", ["en"])
        
        # 加载分类数据
        self.load_categories_data()
        
        # 为每种语言创建数据库并处理数据
        for lang in languages:
            db_filename = db_output_path / f'item_db_{lang}.sqlite'
            
            print(f"\n[+] 处理数据库: {db_filename}")
            
            try:
                conn = sqlite3.connect(str(db_filename))
                cursor = conn.cursor()
                
                # 处理分类数据
                self.process_categories_to_db(cursor, lang)
                
                # 提交事务
                conn.commit()
                conn.close()
                
                print(f"[+] 数据库 {lang} 更新完成")
                
            except Exception as e:
                print(f"[x] 处理数据库 {db_filename} 时出错: {e}")


def main(config=None):
    """主函数"""
    print("[+] 物品分类处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = CategoriesProcessor(config)
    processor.update_all_databases(config)
    
    print("\n[+] 物品分类处理器完成")


if __name__ == "__main__":
    main()
