#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
物品详情数据处理器模块
用于处理types数据并写入数据库

功能: 处理物品详情数据，创建types表
完全按照old版本的逻辑实现，确保数据库结构一致
"""

import json
import sqlite3
import shutil
import os
import hashlib
import time
from pathlib import Path
from utils.http_client import get
from typing import Dict, Any, Optional, List, Tuple
import scripts.icon_finder as icon_finder

# 虫洞目标映射
WORMHOLE_TARGET_MAP = {
    1: {"zh": "1级虫洞空间", "other": "W-Space C1"},
    2: {"zh": "2级虫洞空间", "other": "W-Space C2"},
    3: {"zh": "3级虫洞空间", "other": "W-Space C3"},
    4: {"zh": "4级虫洞空间", "other": "W-Space C4"},
    5: {"zh": "5级虫洞空间", "other": "W-Space C5"},
    6: {"zh": "6级虫洞空间", "other": "W-Space C6"},
    7: {"zh": "高安星系", "other": "High-Sec Space"},
    8: {"zh": "低安星系", "other": "Low-Sec Space"},
    9: {"zh": "0.0星系", "other": "Null-Sec Space"},
    12: {"zh": "希拉星系", "other": "Thera"},
    13: {"zh": "破碎星系", "other": "Shattered WH"},
    14: {"zh": "流浪者 Sentinel", "other": "Drifter Sentinel"},
    15: {"zh": "流浪者 Barbican", "other": "Drifter Barbican"},
    16: {"zh": "流浪者 Vidette", "other": "Drifter Vidette"},
    17: {"zh": "流浪者 Conflux", "other": "Drifter Conflux"},
    18: {"zh": "流浪者 Redoubt", "other": "Drifter Redoubt"},
    25: {"zh": "波赫文", "other": "Pochven"}
}

# 虫洞尺寸映射
WORMHOLE_SIZE_MAP = {
    2000000000: {"zh": "XL(旗舰)", "other": "XL(Capital)"},
    1000000000: {"zh": "XL(货舰)", "other": "XL(Freighter)"},
    375000000: {"zh": "L(战列舰)", "other": "L(Battleship)"},
    62000000: {"zh": "M(战巡)", "other": "M(Battlecruiser)"},
    5000000: {"zh": "S(驱逐舰)", "other": "S(Destroyer)"}
}

# 全局缓存
type_en_name_cache = {}
icon_md5_cache = {}  # MD5 -> 目标文件名映射


class TypesProcessor:
    """物品详情数据处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化types处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.sde_jsonl_path = self.project_root / config["paths"]["sde_jsonl"]
        self.db_output_path = self.project_root / config["paths"]["db_output"]
        self.languages = config.get("languages", ["en"])
        self.icons_output_path = self.project_root / config["paths"]["icons_output"]
        self.custom_icons_path = self.project_root / "custom_icons"
        
        # 确保目录存在
        self.icons_output_path.mkdir(parents=True, exist_ok=True)
        self.custom_icons_path.mkdir(parents=True, exist_ok=True)
        
        # 初始化图标查找器（用于下载默认图标）
        self.icon_finder = icon_finder.IconFinder(config)
    
    def read_types_jsonl(self) -> Dict[str, Any]:
        """
        读取types JSONL文件
        """
        jsonl_file = self.sde_jsonl_path / "types.jsonl"
        
        if not jsonl_file.exists():
            print(f"[x] 找不到types JSONL文件: {jsonl_file}")
            return {}
        
        print(f"[+] 读取types JSONL文件: {jsonl_file}")
        
        types_data = {}
        try:
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        # 新版本使用_key作为type_id
                        type_id = data['_key']
                        types_data[type_id] = data
                    except json.JSONDecodeError as e:
                        print(f"[!] 第{line_num}行JSON解析错误: {e}")
                        continue
                    except KeyError as e:
                        print(f"[!] 第{line_num}行缺少必要字段: {e}")
                        continue
            
            print(f"[+] 成功读取 {len(types_data)} 个types记录")
            return types_data
            
        except Exception as e:
            print(f"[x] 读取types JSONL文件时出错: {e}")
            return {}
    
    def read_repackaged_volumes(self) -> Dict[str, float]:
        """
        从网络获取重新打包体积数据
        """
        url = "https://sde.hoboleaks.space/tq/repackagedvolumes.json"
        
        try:
            print(f"[+] 正在从网络获取repackagedvolumes数据: {url}")
            response = get(url, timeout=30, verify=False)
            
            repackaged_volumes = response.json()
            print(f"[+] 成功获取 {len(repackaged_volumes)} 个重新打包体积记录")
            return repackaged_volumes
            
        except Exception as e:
            print(f"[!] 网络请求失败: {e}")
            return {}
        except json.JSONDecodeError as e:
            print(f"[!] JSON解析失败: {e}")
            return {}
        except Exception as e:
            print(f"[!] 获取repackagedvolumes数据时出错: {e}")
            return {}
    
    def create_types_table(self, cursor: sqlite3.Cursor):
        """
        创建types表
        完全按照old版本的数据库结构
        """
        # 先删除现有的表（如果存在）
        cursor.execute('DROP TABLE IF EXISTS types')
        
        # 创建完整的types表
        cursor.execute('''
        CREATE TABLE types (
            type_id INTEGER NOT NULL PRIMARY KEY,
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
            icon_filename TEXT,
            bpc_icon_filename TEXT,
            published BOOLEAN,
            volume REAL,
            repackaged_volume REAL,
            capacity REAL,
            mass REAL,
            marketGroupID INTEGER,
            metaGroupID INTEGER,
            iconID INTEGER,
            groupID INTEGER,
            group_name TEXT,
            categoryID INTEGER,
            category_name TEXT,
            pg_need REAL,
            cpu_need REAL,
            rig_cost INTEGER,
            em_damage REAL,
            them_damage REAL,
            kin_damage REAL,
            exp_damage REAL,
            high_slot INTEGER,
            mid_slot INTEGER,
            low_slot INTEGER,
            rig_slot INTEGER,
            gun_slot INTEGER,
            miss_slot INTEGER,
            variationParentTypeID INTEGER,
            process_size INTEGER,
            npc_ship_scene TEXT,
            npc_ship_faction TEXT,
            npc_ship_type TEXT,
            npc_ship_faction_icon TEXT
        )
        ''')
        print("[+] 创建types表")
    
    def create_wormholes_table(self, cursor: sqlite3.Cursor):
        """
        创建虫洞表
        完全按照old版本的数据库结构
        """
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS wormholes (
            type_id INTEGER NOT NULL PRIMARY KEY,
            name TEXT,
            description TEXT,
            icon TEXT,
            target_value INTEGER,
            target TEXT,
            stable_time TEXT,
            max_stable_mass TEXT,
            max_jump_mass TEXT,
            size_type TEXT
        )
        ''')
        print("[+] 创建wormholes表")
    
    def fetch_and_process_data(self, cursor: sqlite3.Cursor) -> Tuple[Dict[int, int], Dict[int, str], Dict[int, str]]:
        """
        获取并处理组和分类数据
        """
        group_to_category = {}
        category_id_to_name = {}
        group_id_to_name = {}
        
        try:
            # 获取组信息
            cursor.execute('''
                SELECT group_id, name, categoryID 
                FROM groups
            ''')
            for group_id, name, category_id in cursor.fetchall():
                group_to_category[group_id] = category_id
                group_id_to_name[group_id] = name
            
            # 获取分类信息
            cursor.execute('''
                SELECT category_id, name 
                FROM categories
            ''')
            for category_id, name in cursor.fetchall():
                category_id_to_name[category_id] = name
                
        except Exception as e:
            print(f"[!] 获取组和分类信息时出错: {e}")
        
        return group_to_category, category_id_to_name, group_id_to_name
    
    def calculate_file_md5(self, file_path: Path) -> str:
        """
        计算文件的MD5值
        """
        md5_hash = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    md5_hash.update(chunk)
            return md5_hash.hexdigest()
        except Exception as e:
            print(f"[!] 计算MD5失败 {file_path}: {e}")
            return ""
    
    def download_default_icon(self) -> str:
        """
        下载默认图标 res:/ui/texture/icons/7_64_15.png
        """
        default_icon_filename = "type_default.png"
        default_icon_path = self.custom_icons_path / default_icon_filename
        
        # 如果默认图标已存在，直接返回
        if default_icon_path.exists():
            return default_icon_filename
        
        try:
            # 使用icon_finder下载默认图标
            resource_path = "res:/ui/texture/icons/7_64_15.png"
            content = self.icon_finder._get_icon_file_content(resource_path)
            
            if content:
                # 保存到custom_icons目录
                with open(default_icon_path, 'wb') as f:
                    f.write(content)
                # print(f"[+] 下载默认图标: {default_icon_filename}")
                return default_icon_filename
            else:
                # print(f"[!] 无法下载默认图标: {resource_path}")
                return default_icon_filename
                
        except Exception as e:
            print(f"[!] 下载默认图标失败: {e}")
            return default_icon_filename
    
    def copy_and_rename_icon(self, type_id: int, category_id: int = None) -> Tuple[Optional[str], Optional[str]]:
        """
        复制并重命名图标（带MD5去重）
        从output/icons目录获取图标文件，使用内存MD5缓存进行去重
        
        参数:
        - type_id: 物品类型ID
        - category_id: 物品分类ID，如果为91或2118则直接使用默认图标
        """
        # 特定分类直接使用默认图标
        if category_id in [91, 2118]:
            # print(f"[+] 分类 {category_id} 使用默认图标: {type_id}")
            default_icon = self.download_default_icon()
            return default_icon, None
        # 定义文件路径
        icons_input_dir = self.icons_output_path
        custom_icons_dir = self.custom_icons_path
        
        # 确保自定义图标目录存在
        custom_icons_dir.mkdir(parents=True, exist_ok=True)
        
        # 定义输入和输出文件名
        input_file = f"type_{type_id}_64.png"
        output_file = f"type_{type_id}_64.png"
        input_bpc_file = f"type_{type_id}_bpc_64.png"
        output_bpc_file = f"type_{type_id}_bpc_64.png"
        
        # 构造完整路径
        input_path = icons_input_dir / input_file
        input_bpc_path = icons_input_dir / input_bpc_file
        
        copied_file = None
        bpc_copied_file = None
        
        # 处理普通图标（带MD5去重）
        if input_path.exists():
            try:
                # 计算源文件的MD5
                file_md5 = self.calculate_file_md5(input_path)
                
                if file_md5 in icon_md5_cache:
                    # 如果MD5已存在，使用已缓存的文件名
                    cached_filename = icon_md5_cache[file_md5]
                    output_path = custom_icons_dir / cached_filename
                    
                    # 如果目标文件不存在，则复制
                    if not output_path.exists():
                        shutil.copy2(input_path, output_path)
                        # print(f"[+] 复制图标（去重）: {type_id} -> {cached_filename}")
                    # else:
                    #     print(f"[+] 图标已存在（去重）: {cached_filename}")
                    copied_file = cached_filename
                else:
                    # 如果MD5不存在，使用原始文件名
                    output_path = custom_icons_dir / output_file
                    if not output_path.exists():
                        shutil.copy2(input_path, output_path)
                        # print(f"[+] 复制图标: {type_id} -> {output_file}")
                    # else:
                    #     print(f"[+] 图标已存在: {output_file}")
                    
                    # 将新的MD5和文件名添加到缓存中
                    icon_md5_cache[file_md5] = output_file
                    copied_file = output_file
                    
            except Exception as e:
                # print(f"[!] 复制图标失败 {type_id}: {e}")
                copied_file = self.download_default_icon()  # 下载默认图标
        else:
            # print(f"[!] 图标文件不存在: {input_path}")
            copied_file = self.download_default_icon()  # 下载默认图标
        
        # 处理BPC图标（带MD5去重）
        if input_bpc_path.exists():
            try:
                # 计算BPC文件的MD5
                bpc_md5 = self.calculate_file_md5(input_bpc_path)
                
                if bpc_md5 in icon_md5_cache:
                    # 如果MD5已存在，使用已缓存的文件名
                    cached_bpc_filename = icon_md5_cache[bpc_md5]
                    output_bpc_path = custom_icons_dir / cached_bpc_filename
                    
                    # 如果目标文件不存在，则复制
                    if not output_bpc_path.exists():
                        shutil.copy2(input_bpc_path, output_bpc_path)
                        # print(f"[+] 复制BPC图标（去重）: {type_id} -> {cached_bpc_filename}")
                    # else:
                    #     print(f"[+] BPC图标已存在（去重）: {cached_bpc_filename}")
                    bpc_copied_file = cached_bpc_filename
                else:
                    # 如果MD5不存在，使用原始文件名
                    output_bpc_path = custom_icons_dir / output_bpc_file
                    if not output_bpc_path.exists():
                        shutil.copy2(input_bpc_path, output_bpc_path)
                        # print(f"[+] 复制BPC图标: {type_id} -> {output_bpc_file}")
                    # else:
                    #     print(f"[+] BPC图标已存在: {output_bpc_file}")
                    
                    # 将新的MD5和文件名添加到缓存中
                    icon_md5_cache[bpc_md5] = output_bpc_file
                    bpc_copied_file = output_bpc_file
                    
            except Exception as e:
                print(f"[!] 复制BPC图标失败 {type_id}: {e}")
        
        return copied_file, bpc_copied_file
    
    def print_icon_dedup_stats(self):
        """
        打印图标去重统计信息
        """
        if icon_md5_cache:
            print(f"[+] 图标去重统计: 共处理 {len(icon_md5_cache)} 个唯一图标")
        else:
            print("[+] 图标去重统计: 未处理任何图标")
    
    def get_attributes_value(self, cursor: sqlite3.Cursor, type_id: int, attribute_ids: List[int]) -> Tuple:
        """
        从 typeAttributes 表获取多个属性的值
        
        参数:
        - cursor: 数据库游标
        - type_id: 类型ID
        - attribute_ids: 属性ID列表
        
        返回:
        - 包含所有请求属性值的元组，如果某个属性不存在则对应位置返回None
        """
        if not attribute_ids:
            return ()
        
        # 构建 SQL 查询中的 IN 子句
        placeholders = ','.join('?' * len(attribute_ids))
        
        try:
            cursor.execute(f'''
                SELECT attribute_id, value 
                FROM typeAttributes 
                WHERE type_id = ? AND attribute_id IN ({placeholders})
            ''', (type_id, *attribute_ids))
            
            # 获取所有结果并转换为字典
            results = dict(cursor.fetchall())
            
            # 为每个请求的 attribute_id 获取对应的值，如果不存在则返回 None
            return tuple(results.get(attr_id, None) for attr_id in attribute_ids)
            
        except Exception as e:
            print(f"[!] 获取属性值时出错 type_id={type_id}: {e}")
            return (None,) * len(attribute_ids)
    
    def format_number(self, value, unit=""):
        """
        格式化数字，添加千分位分隔符，去除多余的零和小数点，添加单位
        """
        if not value:
            return None

        # 转换为浮点数
        num = float(value)

        # 将数字转换为字符串，并去除多余的零和小数点
        formatted = f"{num:f}".rstrip('0').rstrip('.')

        # 处理整数部分的千分位
        parts = formatted.split('.')
        integer_part = parts[0]
        decimal_part = parts[1] if len(parts) > 1 else ""

        # 添加千分位分隔符
        integer_part = "{:,}".format(int(integer_part))

        # 重新组合整数和小数部分
        if decimal_part:
            formatted = f"{integer_part}.{decimal_part}"
        else:
            formatted = integer_part

        # 添加单位（如果有）
        if unit:
            formatted += unit

        return formatted
    
    def get_wormhole_size_type(self, max_jump_mass, lang: str):
        """
        根据最大跳跃质量确定虫洞尺寸类型
        """
        if not max_jump_mass:
            return None

        # 直接使用浮点数进行比较
        for threshold, size_map in sorted(WORMHOLE_SIZE_MAP.items(), reverse=True):
            if max_jump_mass >= threshold:
                return size_map["zh" if lang == "zh" else "other"]
        return None
    
    def get_wormhole_target(self, target_value, name: str, lang: str):
        """
        获取虫洞目标描述
        """
        # 特殊处理 K162
        if "K162" in name:
            return "出口虫洞" if lang == "zh" else "Exit WH"

        # 特殊处理 U372
        if "U372" in name:
            return "0.0 无人机星域" if lang == "zh" else "Null-Sec Drone Regions"

        # 处理常规映射
        if target_value and int(target_value) in WORMHOLE_TARGET_MAP:
            return WORMHOLE_TARGET_MAP[int(target_value)]["zh" if lang == "zh" else "other"]

        return "Unknown"
    
    def process_wormhole_data(self, cursor: sqlite3.Cursor, type_id: int, name: str, description: str, icon_filename: Optional[str], lang: str):
        """
        处理虫洞数据
        完全按照old版本的逻辑实现
        """
        try:
            # 获取虫洞属性
            attributes = self.get_attributes_value(cursor, type_id, [1381, 1382, 1383, 1385])
            target_value, stable_time, max_stable_mass, max_jump_mass = attributes

            # 处理目标
            target = self.get_wormhole_target(target_value, name, lang)

            # 先进行数值计算
            if stable_time:
                stable_time = float(stable_time) / 60  # 转换为小时
            if max_stable_mass:
                max_stable_mass = float(max_stable_mass)  # 转换为浮点数
            if max_jump_mass:
                max_jump_mass = float(max_jump_mass)  # 转换为浮点数

            # 获取尺寸类型（在格式化之前）
            size_type = self.get_wormhole_size_type(max_jump_mass, lang)

            # 格式化并添加单位
            stable_time = self.format_number(stable_time, "h") if stable_time else None
            max_stable_mass = self.format_number(max_stable_mass, "Kg") if max_stable_mass else None
            max_jump_mass = self.format_number(max_jump_mass, "Kg") if max_jump_mass else None

            # 插入数据
            cursor.execute('''
                INSERT OR IGNORE INTO wormholes (
                    type_id, name, description, icon, target_value, target, stable_time, 
                    max_stable_mass, max_jump_mass, size_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                type_id, name, description, icon_filename, target_value, target, stable_time,
                max_stable_mass, max_jump_mass, size_type
            ))
            
        except Exception as e:
            print(f"[!] 处理虫洞数据时出错 type_id={type_id}: {e}")
    
    def process_types_to_db(self, types_data: Dict[str, Any], cursor: sqlite3.Cursor, lang: str):
        """
        处理types数据并写入数据库
        完全按照old版本的逻辑
        """
        create_types_table = self.create_types_table
        create_wormholes_table = self.create_wormholes_table
        fetch_and_process_data = self.fetch_and_process_data
        read_repackaged_volumes = self.read_repackaged_volumes
        copy_and_rename_icon = self.copy_and_rename_icon
        get_attributes_value = self.get_attributes_value
        process_wormhole_data = self.process_wormhole_data
        
        create_types_table(cursor)
        create_wormholes_table(cursor)  # 创建虫洞表
        group_to_category, category_id_to_name, group_id_to_name = fetch_and_process_data(cursor)

        # 读取repackaged_volumes数据
        repackaged_volumes = read_repackaged_volumes()

        # 如果是英文数据库，建立英文名称映射
        if lang == 'en':
            type_en_name_cache.clear()
            # 预处理所有英文名称
            for type_id, item in types_data.items():
                type_en_name_cache[type_id] = item['name'].get('en', "")

        # 用于存储批量插入的数据
        batch_data = []
        batch_size = 1000  # 每批处理的记录数

        for type_id, item in types_data.items():
            # 获取当前语言的名称作为主要name
            name = item['name'].get(lang, item['name'].get('en', ""))

            # 获取所有语言的名称
            names = {
                'de': item['name'].get('de', name),
                'en': item['name'].get('en', name),
                'es': item['name'].get('es', name),
                'fr': item['name'].get('fr', name),
                'ja': item['name'].get('ja', name),
                'ko': item['name'].get('ko', name),
                'ru': item['name'].get('ru', name),
                'zh': item['name'].get('zh', name)
            }

            description = item.get('description', {}).get(lang, item.get('description', {}).get('en', ""))
            published = item.get('published', False)
            volume = item.get('volume', None)
            # 获取重新打包体积
            repackaged_volume = repackaged_volumes.get(str(type_id), None)
            marketGroupID = item.get('marketGroupID', None)
            metaGroupID = item.get('metaGroupID', 1)
            iconID = item.get('iconID', 0)
            groupID = item.get('groupID', 0)
            process_size = item.get('portionSize', None)
            capacity = item.get('capacity', None)
            mass = item.get('mass', None)
            variationParentTypeID = item.get('variationParentTypeID', None)
            group_name = group_id_to_name.get(groupID, 'Unknown')
            category_id = group_to_category.get(groupID, 0)
            category_name = category_id_to_name.get(category_id, 'Unknown')

            # NPC船只分类字段将在后续的npc_ship_classifier阶段处理，这里先设置为null
            npc_ship_scene = None
            npc_ship_faction = None
            npc_ship_type = None
            npc_ship_faction_icon = None

            copied_file, bpc_copied_file = copy_and_rename_icon(type_id, category_id)
            res = get_attributes_value(cursor, type_id, [30, 50, 1153, 114, 118, 117, 116, 14, 13, 12, 1154, 102, 101])

            pg_need, cpu_need, rig_cost, em_damage, them_damage, kin_damage, exp_damage, \
                high_slot, mid_slot, low_slot, rig_slot, gun_slot, miss_slot = res

            # 处理虫洞数据
            if groupID == 988:
                process_wormhole_data(cursor, type_id, name, description, copied_file, lang)

            # 添加到批处理列表
            batch_data.append((
                type_id, name,
                names['de'], names['en'], names['es'], names['fr'],
                names['ja'], names['ko'], names['ru'], names['zh'],
                description, copied_file, bpc_copied_file, published, volume, repackaged_volume, capacity, mass,
                marketGroupID,
                metaGroupID, iconID, groupID, group_name, category_id, category_name,
                pg_need, cpu_need, rig_cost, em_damage, them_damage, kin_damage, exp_damage,
                high_slot, mid_slot, low_slot, rig_slot, gun_slot, miss_slot, variationParentTypeID,
                process_size, npc_ship_scene, npc_ship_faction, npc_ship_type, npc_ship_faction_icon
            ))

            # 当达到批处理大小时执行插入
            if len(batch_data) >= batch_size:
                cursor.executemany('''
                    INSERT OR REPLACE INTO types (
                        type_id, name, de_name, en_name, es_name, fr_name, ja_name, ko_name, ru_name, zh_name,
                        description, icon_filename, bpc_icon_filename, published, volume, repackaged_volume, capacity, mass,
                        marketGroupID, metaGroupID, iconID, groupID, group_name, categoryID, category_name,
                        pg_need, cpu_need, rig_cost, em_damage, them_damage, kin_damage, exp_damage,
                        high_slot, mid_slot, low_slot, rig_slot, gun_slot, miss_slot, variationParentTypeID,
                        process_size, npc_ship_scene, npc_ship_faction, npc_ship_type, npc_ship_faction_icon
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', batch_data)
                batch_data = []

        # 处理剩余的数据
        if batch_data:
            cursor.executemany('''
                INSERT OR REPLACE INTO types (
                    type_id, name, de_name, en_name, es_name, fr_name, ja_name, ko_name, ru_name, zh_name,
                    description, icon_filename, bpc_icon_filename, published, volume, repackaged_volume, capacity, mass,
                    marketGroupID, metaGroupID, iconID, groupID, group_name, categoryID, category_name,
                    pg_need, cpu_need, rig_cost, em_damage, them_damage, kin_damage, exp_damage,
                    high_slot, mid_slot, low_slot, rig_slot, gun_slot, miss_slot, variationParentTypeID,
                    process_size, npc_ship_scene, npc_ship_faction, npc_ship_type, npc_ship_faction_icon
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', batch_data)
        
        print(f"[+] 成功处理 {len(types_data)} 个types记录")
        
        # 打印图标去重统计信息
        self.print_icon_dedup_stats()
    
    def process_types_for_language(self, language: str) -> bool:
        """
        为指定语言处理types数据
        """
        print(f"[+] 开始处理types数据，语言: {language}")
        
        # 读取types数据
        types_data = self.read_types_jsonl()
        if not types_data:
            print("[x] 无法读取types数据")
            return False
        
        # 数据库文件路径
        db_path = self.db_output_path / f"item_db_{language}.sqlite"
        
        if not db_path.exists():
            print(f"[!] 数据库文件不存在: {db_path}")
            return False
        
        try:
            # 连接数据库
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # 处理数据
            self.process_types_to_db(types_data, cursor, language)
            
            # 提交更改
            conn.commit()
            print(f"[+] types数据处理完成，语言: {language}")
            return True
            
        except Exception as e:
            print(f"[x] 处理types数据时出错: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()
    
    def process_all_languages(self) -> bool:
        """
        为所有语言处理types数据
        """
        print("[+] 开始处理types数据")
        
        success_count = 0
        for language in self.languages:
            if self.process_types_for_language(language):
                success_count += 1
        
        print(f"[+] types数据处理完成，成功处理 {success_count}/{len(self.languages)} 个语言")
        return success_count > 0


def main(config=None):
    """主函数"""
    print("[+] 物品详情数据处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = TypesProcessor(config)
    processor.process_all_languages()
    
    print("\n[+] 物品详情数据处理器完成")


if __name__ == "__main__":
    main()