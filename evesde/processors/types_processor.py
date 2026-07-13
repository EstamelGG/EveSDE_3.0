#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
物品详情数据处理器模块
用于处理types数据并写入数据库

功能: 处理物品详情数据，创建types表
完全按照old版本的逻辑实现，确保数据库结构一致
"""

from evesde.paths import PROJECT_ROOT
from evesde.utils.single_db import get_db_path
from evesde.utils.wide_i18n import wide_texts, names_row, name_cols_sql, LANGS
import json
import sqlite3
import shutil
import os
import hashlib
import time
from pathlib import Path
from evesde.utils.http_client import get
from typing import Dict, Any, Optional, List, Tuple
import evesde.processors.icon_finder as icon_finder

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


class TypesProcessor:
    """物品详情数据处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化types处理器"""
        self.config = config
        self.project_root = PROJECT_ROOT
        self.sde_jsonl_path = self.project_root / config["paths"]["sde_input"]
        self.db_output_path = self.project_root / config["paths"]["db_output"]
        self.languages = config.get("languages", ["en"])
        self.icons_input_path = self.project_root / config["paths"]["icons_input"]
        self.custom_icons_path = self.project_root / "cache/custom_icons"

        # 确保目录存在
        self.custom_icons_path.mkdir(parents=True, exist_ok=True)

        # 加载图标索引（type_id → icon 文件名映射，已去重）
        self.icon_metadata = self._load_icon_metadata()

        # 初始化图标查找器（用于下载默认图标）
        self.icon_finder = icon_finder.IconFinder(config)

    def _load_icon_metadata(self) -> Dict[str, str]:
        """从 icons_input/icon_index.json 加载 type_id → icon 文件名映射"""
        index_file = self.icons_input_path / "icon_index.json"
        if not index_file.exists():
            print(f"[!] 图标索引文件不存在: {index_file}")
            return {}
        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            print(f"[+] 加载图标索引: {len(metadata):,} 个映射")
            return metadata
        except Exception as e:
            print(f"[!] 加载图标索引失败: {e}")
            return {}
    
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
            de_name TEXT,
            en_name TEXT,
            es_name TEXT,
            fr_name TEXT,
            ja_name TEXT,
            ko_name TEXT,
            ru_name TEXT,
            zh_name TEXT,
            de_desc_id TEXT,
            en_desc_id TEXT,
            es_desc_id TEXT,
            fr_desc_id TEXT,
            ja_desc_id TEXT,
            ko_desc_id TEXT,
            ru_desc_id TEXT,
            zh_desc_id TEXT,
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
            group_de_name TEXT,
            group_en_name TEXT,
            group_es_name TEXT,
            group_fr_name TEXT,
            group_ja_name TEXT,
            group_ko_name TEXT,
            group_ru_name TEXT,
            group_zh_name TEXT,
            categoryID INTEGER,
            category_de_name TEXT,
            category_en_name TEXT,
            category_es_name TEXT,
            category_fr_name TEXT,
            category_ja_name TEXT,
            category_ko_name TEXT,
            category_ru_name TEXT,
            category_zh_name TEXT,
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

    def create_texts_table(self, cursor: sqlite3.Cursor):
        """创建全局文本池表，对 description 做跨行去重。
        内部用整数序号；写入 types.*_desc_id 与 texts.json 时转为无前缀十六进制键（0,1,…,a,…,f,10,…）。
        构建末尾会调用 export_texts_to_json 将 texts 拆分为独立 JSON 文件。"""
        cursor.execute('DROP TABLE IF EXISTS texts')
        cursor.execute('''
            CREATE TABLE texts (
                id INTEGER PRIMARY KEY,
                content TEXT
            ) WITHOUT ROWID
        ''')
        print("[+] 创建texts表（description 文本池）")

    @staticmethod
    def text_id_hex(seq: int) -> str:
        """序号 → 无前缀小写十六进制字符串。"""
        return format(seq, "x")

    def export_texts_to_json(self, conn: sqlite3.Connection):
        """将 texts 表导出为 zip 压缩的 JSON 对象并从数据库中移除。
        格式: {"0":"...","1":"...","a":"...","10":"..."}，indent=2 便于阅读。"""
        import zipfile

        cur = conn.cursor()
        cur.execute("SELECT id, content FROM texts ORDER BY id")
        all_rows = cur.fetchall()
        if not all_rows:
            return

        texts_obj = {
            self.text_id_hex(i): (content if content else "")
            for i, content in all_rows
        }
        json_bytes = json.dumps(texts_obj, ensure_ascii=False, indent=2).encode("utf-8")

        zip_path = self.db_output_path.parent / "texts.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            zf.writestr("texts.json", json_bytes)

        zip_size = zip_path.stat().st_size
        raw_size = len(json_bytes)

        cur.execute("DROP TABLE texts")
        cur.execute("DROP TABLE IF EXISTS _zstd_dict")
        conn.commit()

        ratio = (1 - zip_size / raw_size) * 100
        print(f"[+] texts 导出: {len(texts_obj):,} 条 → {zip_path.name}")
        print(f"    {raw_size/(1024*1024):.1f} MB → {zip_size/(1024*1024):.1f} MB (zip {ratio:.0f}%)")
        print(f"    已从数据库移除 texts 表")
    
    def create_wormholes_table(self, cursor: sqlite3.Cursor):
        """
        创建虫洞表
        完全按照old版本的数据库结构
        """
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS wormholes (
            type_id INTEGER NOT NULL PRIMARY KEY,
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
    
    def fetch_and_process_data(self, cursor: sqlite3.Cursor):
        """获取组/分类多语名称映射"""
        group_to_category = {}
        category_id_to_names: Dict[int, Dict[str, str]] = {}
        group_id_to_names: Dict[int, Dict[str, str]] = {}
        unknown = {lang: "Unknown" for lang in LANGS}

        try:
            cursor.execute(f'''
                SELECT group_id, {name_cols_sql()}, categoryID
                FROM groups
            ''')
            for row in cursor.fetchall():
                group_id, *name_vals, category_id = row
                group_to_category[group_id] = category_id
                group_id_to_names[group_id] = {
                    LANGS[i]: name_vals[i] for i in range(len(LANGS))
                }

            cursor.execute(f'''
                SELECT category_id, {name_cols_sql()}
                FROM categories
            ''')
            for row in cursor.fetchall():
                category_id, *name_vals = row
                category_id_to_names[category_id] = {
                    LANGS[i]: name_vals[i] for i in range(len(LANGS))
                }
        except Exception as e:
            print(f"[!] 获取组和分类信息时出错: {e}")

        return group_to_category, category_id_to_names, group_id_to_names, unknown
    
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
                # 保存到cache/custom_icons目录
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
        """从 icons_input 复制已去重、已命名的图标到 cache/custom_icons 目录。

        图标在 eve_icon_builder 构造阶段已完成去重和命名（type_{id}.png），
        此处仅做透传复制，无需额外去重或重命名。

        参数:
        - type_id: 物品类型ID
        - category_id: 物品分类ID，91/2118 无图标
        """
        if category_id in [91, 2118]:
            return None, None

        icon_filename = self.icon_metadata.get(str(type_id))
        if not icon_filename:
            return None, None

        input_path = self.icons_input_path / icon_filename
        if not input_path.exists():
            return None, None

        output_path = self.custom_icons_path / icon_filename
        try:
            if not output_path.exists():
                shutil.copy2(input_path, output_path)
        except Exception as e:
            print(f"[!] 复制图标失败 type_id={type_id}: {e}")
            return None, None

        return icon_filename, None
    
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
    
    def process_wormhole_data(
        self,
        cursor: sqlite3.Cursor,
        type_id: int,
        names: Dict[str, str],
        descs: Dict[str, str],
        icon_filename: Optional[str],
        lang: str,
    ):
        """处理虫洞数据（宽列 name / description）"""
        try:
            attributes = self.get_attributes_value(cursor, type_id, [1381, 1382, 1383, 1385])
            target_value, stable_time, max_stable_mass, max_jump_mass = attributes

            target = self.get_wormhole_target(target_value, names['en'], lang)

            if stable_time:
                stable_time = float(stable_time) / 60
            if max_stable_mass:
                max_stable_mass = float(max_stable_mass)
            if max_jump_mass:
                max_jump_mass = float(max_jump_mass)

            size_type = self.get_wormhole_size_type(max_jump_mass, lang)

            stable_time = self.format_number(stable_time, "h") if stable_time else None
            max_stable_mass = self.format_number(max_stable_mass, "Kg") if max_stable_mass else None
            max_jump_mass = self.format_number(max_jump_mass, "Kg") if max_jump_mass else None

            cursor.execute('''
                INSERT OR IGNORE INTO wormholes (
                    type_id,
                    de_name, en_name, es_name, fr_name, ja_name, ko_name, ru_name, zh_name,
                    de_description, en_description, es_description, fr_description,
                    ja_description, ko_description, ru_description, zh_description,
                    icon, target_value, target, stable_time,
                    max_stable_mass, max_jump_mass, size_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                type_id, *names_row(names), *names_row(descs),
                icon_filename, target_value, target, stable_time,
                max_stable_mass, max_jump_mass, size_type,
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
        self.create_texts_table(cursor)
        group_to_category, category_id_to_names, group_id_to_names, unknown_names = fetch_and_process_data(cursor)

        # 读取repackaged_volumes数据
        repackaged_volumes = read_repackaged_volumes()

        # 构建文本池：收集所有非空 description 文本，去重后写入 texts 表
        all_texts = set()
        for item in types_data.values():
            descs = wide_texts(item.get('description'))
            for lang in LANGS:
                if descs[lang]:
                    all_texts.add(descs[lang])
        sorted_texts = sorted(all_texts)
        if sorted_texts:
            cursor.executemany(
                "INSERT INTO texts (id, content) VALUES (?, ?)",
                [(i, t) for i, t in enumerate(sorted_texts)],
            )
        text_to_id = {
            content: self.text_id_hex(i) for i, content in enumerate(sorted_texts)
        }
        print(f"[+] 文本池去重: {len(text_to_id):,} 个唯一描述文本（desc_id 为十六进制）")

        # 如果是英文数据库，建立英文名称映射
        if lang == 'en':
            type_en_name_cache.clear()
            # 预处理所有英文名称
            for type_id, item in types_data.items():
                type_en_name_cache[type_id] = item['name'].get('en', "")

        batch_data = []
        batch_size = 1000
        _types_insert_sql = '''
            INSERT OR REPLACE INTO types (
                type_id,
                de_name, en_name, es_name, fr_name, ja_name, ko_name, ru_name, zh_name,
                de_desc_id, en_desc_id, es_desc_id, fr_desc_id,
                ja_desc_id, ko_desc_id, ru_desc_id, zh_desc_id,
                icon_filename, bpc_icon_filename, published, volume, repackaged_volume, capacity, mass,
                marketGroupID, metaGroupID, iconID, groupID,
                group_de_name, group_en_name, group_es_name, group_fr_name,
                group_ja_name, group_ko_name, group_ru_name, group_zh_name,
                categoryID,
                category_de_name, category_en_name, category_es_name, category_fr_name,
                category_ja_name, category_ko_name, category_ru_name, category_zh_name,
                pg_need, cpu_need, rig_cost, em_damage, them_damage, kin_damage, exp_damage,
                high_slot, mid_slot, low_slot, rig_slot, gun_slot, miss_slot, variationParentTypeID,
                process_size, npc_ship_scene, npc_ship_faction, npc_ship_type, npc_ship_faction_icon
            ) VALUES ({ph})
        '''.format(ph=", ".join(["?"] * 64))

        for type_id, item in types_data.items():
            # 多语名称与描述（宽列，单库一次写入）
            names = wide_texts(item.get('name'))
            descs = wide_texts(item.get('description'))
            desc_ids = tuple(text_to_id[descs[lang]] if descs[lang] else None for lang in LANGS)
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
            group_names = group_id_to_names.get(groupID, unknown_names)
            category_id = group_to_category.get(groupID, 0)
            category_names = category_id_to_names.get(category_id, unknown_names)

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
                process_wormhole_data(cursor, type_id, names, descs, copied_file, lang)

            batch_data.append((
                type_id,
                *names_row(names),
                *desc_ids,
                copied_file, bpc_copied_file, published, volume, repackaged_volume, capacity, mass,
                marketGroupID,
                metaGroupID, iconID, groupID,
                *names_row(group_names),
                category_id,
                *names_row(category_names),
                pg_need, cpu_need, rig_cost, em_damage, them_damage, kin_damage, exp_damage,
                high_slot, mid_slot, low_slot, rig_slot, gun_slot, miss_slot, variationParentTypeID,
                process_size, npc_ship_scene, npc_ship_faction, npc_ship_type, npc_ship_faction_icon
            ))

            if len(batch_data) >= batch_size:
                cursor.executemany(_types_insert_sql, batch_data)
                batch_data = []

        if batch_data:
            cursor.executemany(_types_insert_sql, batch_data)
        
        print(f"[+] 成功处理 {len(types_data)} 个types记录")
        print(f"[+] 图标索引: {len(self.icon_metadata):,} 个映射（已在构造阶段去重）")
    
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
        db_path = get_db_path(self.config)
        
        try:
            # 连接数据库
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # 处理数据
            self.process_types_to_db(types_data, cursor, language)

            # 提交更改
            conn.commit()

            # 将 texts 表拆分为独立 JSON 文件
            self.export_texts_to_json(conn)
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
        
        # 单库宽列：一次写入全部 name / description 列
        return self.process_types_for_language('en')


def main(config=None):
    """主函数"""
    print("[+] 物品详情数据处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = PROJECT_ROOT / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = TypesProcessor(config)
    processor.process_all_languages()
    
    print("\n[+] 物品详情数据处理器完成")


if __name__ == "__main__":
    main()