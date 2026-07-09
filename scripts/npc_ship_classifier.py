#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NPC船只分类处理器模块
用于处理types表中的NPC船只分类字段

功能: 在types_processor之后，专门处理npc_ship_scene, npc_ship_faction, npc_ship_type, npc_ship_faction_icon字段
"""

import sqlite3
import json
from pathlib import Path
from typing import Dict, Any, Optional

# NPC船只场景映射
NPC_SHIP_SCENES = [
    {"en": "Asteroid ", "zh": "小行星带"},
    {"en": "Deadspace ", "zh": "死亡空间"},
    {"en": "FW ", "zh": "势力战争"},
    {"en": "Ghost Site ", "zh": "幽灵站点"},
    {"en": "Incursion ", "zh": "入侵"},
    {"en": "Mission ", "zh": "任务"},
    {"en": "Storyline ", "zh": "故事线"},
    {"en": "Abyssal ", "zh": "深渊"}
]

# NPC船只势力映射
NPC_SHIP_FACTIONS = [
    {"en": "Angel Cartel", "zh": "天使"},
    {"en": "Blood Raider", "zh": "血袭者"},
    {"en": "Guristas", "zh": "古斯塔斯"},
    {"en": "Mordu", "zh": "莫德团"},
    {"en": "Rogue Drone", "zh": "自由无人机"},
    {"en": "Sansha", "zh": "萨沙共和国"},
    {"en": "Serpentis", "zh": "天蛇"},
    {"en": "Overseer", "zh": "监察官"},
    {"en": "Sleeper", "zh": "冬眠者"},
    {"en": "Drifter", "zh": "流浪者"},
    {"en": "Amarr Empire", "zh": "艾玛帝国"},
    {"en": "Gallente Federation", "zh": "盖伦特联邦"},
    {"en": "Minmatar Republic", "zh": "米玛塔尔共和国"},
    {"en": "Caldari State", "zh": "加达里合众国"},
    {"en": "CONCORD", "zh": "统合部"},
    {"en": "Faction", "zh": "势力特属"},
    {"en": "Generic", "zh": "任务通用"},
    {"en": "Khanid", "zh": "卡尼迪"},
    {"en": "Thukker", "zh": "图克尔"}
]

# NPC势力ICON映射
NPC_FACTION_ICON_MAP = {
    "Angel Cartel": "faction_500011.png",
    "Blood Raider": "faction_500012.png",
    "Guristas": "faction_500010.png",
    "Mordu": "faction_500018.png",
    "Rogue Drone": "faction_500025.png",
    "Sansha": "faction_500019.png",
    "Serpentis": "faction_500020.png",
    "Overseer": "faction_500021.png",  # 使用默认图标
    "Sleeper": "faction_500005.png",
    "Drifter": "faction_500024.png",
    "Amarr Empire": "faction_500003.png",
    "Gallente Federation": "faction_500004.png",
    "Minmatar Republic": "faction_500002.png",
    "Caldari State": "faction_500001.png",
    "CONCORD": "faction_500006.png",
    "Faction": "faction_500021.png",  # 使用默认图标
    "Generic": "faction_500021.png",  # 使用默认图标
    "Other": "faction_500021.png",  # 使用默认图标
    "Khanid": "faction_500008.png",
    "Thukker": "faction_500015.png"
}

# NPC船只类型映射
NPC_SHIP_TYPES = [
    {"en": " Frigate", "zh": "护卫舰"},
    {"en": " Destroyer", "zh": "驱逐舰"},
    {"en": " Battlecruiser", "zh": "战列巡洋舰"},
    {"en": " Cruiser", "zh": "巡洋舰"},
    {"en": " Battleship", "zh": "战列舰"},
    {"en": " Hauler", "zh": "运输舰"},
    {"en": " Transports", "zh": "运输舰"},
    {"en": " Dreadnought", "zh": "无畏舰"},
    {"en": " Titan", "zh": "泰坦"},
    {"en": " Supercarrier", "zh": "超级航母"},
    {"en": " Carrier", "zh": "航空母舰"},
    {"en": " Officer", "zh": "官员"},
    {"en": " Sentry", "zh": "岗哨"},
    {"en": " Drone", "zh": "无人机"}
]

# 全局缓存（用于跨语言共享分类结果）
npc_classification_cache = {}


class NPCShipClassifier:
    """NPC船只分类处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化NPC船只分类处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.db_output_path = self.project_root / config["paths"]["db_output"]
        self.languages = config.get("languages", ["en"])
        self.brackets_data = None  # 缓存 brackets_output.json 数据
    
    def get_npc_ship_scene(self, group_name: str, lang: str) -> Optional[str]:
        """
        获取NPC船只场景
        """
        for scene in NPC_SHIP_SCENES:
            if group_name.startswith(scene["en"]):
                if scene["en"].strip() == "FW":
                    return "势力战争" if lang == "zh" else "Faction Warfare"
                return scene.get(lang, scene["en"]).strip()
        return "其他" if lang == "zh" else "Other"
    
    def get_npc_ship_faction(self, group_name: str, lang: str) -> Optional[str]:
        """
        获取NPC船只势力
        """
        for faction in NPC_SHIP_FACTIONS:
            if faction["en"] in group_name:
                return faction.get(lang, faction["en"]).strip()
        return "其他" if lang == "zh" else "Other"
    
    def get_faction_icon(self, faction_name: str) -> Optional[str]:
        """
        获取势力图标
        """
        return NPC_FACTION_ICON_MAP.get(faction_name, "faction_500021.png")
    
    def load_brackets_data(self) -> bool:
        """
        加载 brackets_output.json 数据
        如果文件不存在，跳过此分类方法（不尝试生成）
        """
        brackets_output_path = self.project_root / "brackets_decode" / "brackets_output.json"
        
        # 如果文件不存在，直接返回 False（跳过此分类方法）
        if not brackets_output_path.exists():
            print("[!] brackets_output.json 不存在，跳过 brackets 分类方法")
            return False
        
        # 读取 brackets_output.json
        try:
            with open(brackets_output_path, 'r', encoding='utf-8') as f:
                self.brackets_data = json.load(f)
            print("[+] 成功加载 brackets_output.json")
            return True
        except json.JSONDecodeError as e:
            print(f"[!] brackets_output.json JSON 格式错误: {e}，跳过 brackets 分类方法")
            self.brackets_data = None
            return False
        except Exception as e:
            print(f"[!] 读取 brackets_output.json 失败: {e}，跳过 brackets 分类方法")
            self.brackets_data = None
            return False
    
    def get_bracket_name_from_brackets_data(self, type_id: int, group_id: int, category_id: int) -> Optional[str]:
        """
        从 brackets_data 中获取 name
        优先级：bracketsByType -> bracketsByGroup -> bracketsByCategory
        """
        if not self.brackets_data:
            return None
        
        try:
            # 方法1: 从 bracketsByType 查找
            brackets_by_type = self.brackets_data.get('bracketsByType', {})
            type_id_str = str(type_id)
            if type_id_str in brackets_by_type:
                bracket_info = brackets_by_type[type_id_str]
                if isinstance(bracket_info, dict):
                    name = bracket_info.get('name', '')
                    if name:
                        return name
            
            # 方法2: 从 bracketsByGroup 查找
            brackets_by_group = self.brackets_data.get('bracketsByGroup', {})
            group_id_str = str(group_id)
            if group_id_str in brackets_by_group:
                bracket_info = brackets_by_group[group_id_str]
                if isinstance(bracket_info, dict):
                    name = bracket_info.get('name', '')
                    if name:
                        return name
            
            # 方法3: 从 bracketsByCategory 查找
            brackets_by_category = self.brackets_data.get('bracketsByCategory', {})
            category_id_str = str(category_id)
            if category_id_str in brackets_by_category:
                bracket_info = brackets_by_category[category_id_str]
                if isinstance(bracket_info, dict):
                    name = bracket_info.get('name', '')
                    if name:
                        return name
            
            return None
        except Exception as e:
            # 如果解析失败，返回 None
            return None
    
    def classify_ship_type_from_name(self, name: str, lang: str) -> Optional[str]:
        """
        根据 name 使用 NPC_SHIP_TYPES 进行分类
        特殊处理 "Super Carrier" -> Supercarrier/超级航母
        """
        if not name:
            return None
        
        # 特殊处理 "Super Carrier"
        if name == "Super Carrier":
            return "超级航母" if lang == "zh" else "Supercarrier"
        
        # 使用 NPC_SHIP_TYPES 匹配
        for ship_type in NPC_SHIP_TYPES:
            if name.endswith(ship_type["en"]) or name == ship_type["en"].strip():
                return ship_type.get(lang, ship_type["en"]).strip()
        
        return None
    
    def get_npc_ship_type_method2(self, type_id: int, lang: str, 
                                   type_attributes_cache: Dict[int, int],
                                   groups_cache: Dict[int, Dict[str, str]]) -> Optional[str]:
        """
        方法2: 根据属性1766获取型号group_id，然后从groups表查询（从内存缓存）
        """
        try:
            # 从缓存中获取属性1766的值
            model_group_id = type_attributes_cache.get(type_id)
            if model_group_id is None:
                return None
            
            # 从缓存中获取group的名称
            group_data = groups_cache.get(model_group_id)
            if not group_data:
                return None
            
            # 获取对应语言的名称
            lang_column = f"{lang}_name" if lang in ['de', 'en', 'es', 'fr', 'ja', 'ko', 'ru', 'zh'] else 'en_name'
            group_name = group_data.get(lang_column) or group_data.get('en_name')
            
            if group_name:
                return group_name.strip()
        except Exception as e:
            pass
        
        return None
    
    def get_npc_ship_type_method3(self, cursor: sqlite3.Cursor, type_id: int, group_id: int, category_id: int, lang: str) -> Optional[str]:
        """
        方法3: 从 brackets_output.json 中查找 name，然后使用 NPC_SHIP_TYPES 分类
        """
        if not self.brackets_data:
            return None
        
        try:
            # 从 brackets_data 中获取 name
            bracket_name = self.get_bracket_name_from_brackets_data(type_id, group_id, category_id)
            if bracket_name:
                # 使用 name 进行分类
                return self.classify_ship_type_from_name(bracket_name, lang)
        except Exception as e:
            pass
        
        return None
    
    def get_npc_ship_type_method1(self, group_name: str, name: str, lang: str) -> Optional[str]:
        """
        方法1: 使用字符串匹配映射（兜底方法）
        """
        # 首先检查组名是否以Officer结尾
        if group_name.endswith("Officer"):
            return "官员" if lang == "zh" else "Officer"
        
        # 使用字符串匹配映射
        for ship_type in NPC_SHIP_TYPES:
            if name.endswith(ship_type["en"]) or group_name.endswith(ship_type["en"]):
                return ship_type.get(lang, ship_type["en"]).strip()
        
        return None
    
    def get_npc_ship_type(self, type_id: int, group_name: str, name: str, group_id: int, category_id: int, lang: str,
                          type_attributes_cache: Dict[int, int],
                          groups_cache: Dict[int, Dict[str, str]]) -> Optional[str]:
        """
        获取NPC船只类型
        优先级：方法2（属性1766）-> 方法3（brackets_output）-> 方法1（字符串匹配）
        """
        # 方法2: 根据属性1766获取型号group_id
        result = self.get_npc_ship_type_method2(type_id, lang, type_attributes_cache, groups_cache)
        if result:
            return result
        
        # 方法3: 从 brackets_output.json 中查找
        result = self.get_npc_ship_type_method3(None, type_id, group_id, category_id, lang)
        if result:
            return result
        
        # 方法1: 使用字符串匹配映射（兜底）
        result = self.get_npc_ship_type_method1(group_name, name, lang)
        if result:
            return result
        
        # 全部失败，返回 Other
        return "其他" if lang == "zh" else "Other"
    
    def load_data_from_db(self, language: str) -> Optional[Dict[str, Any]]:
        """
        从数据库加载所有需要的数据到内存
        返回包含所有NPC船只数据、属性缓存、groups缓存的字典
        """
        db_path = self.db_output_path / f"item_db_{language}.sqlite"
        
        if not db_path.exists():
            print(f"[!] 数据库文件不存在: {db_path}")
            return None
        
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # 1. 获取所有categoryID为11的NPC船只
            cursor.execute('''
                SELECT type_id, en_name, zh_name, group_name, categoryID, groupID, icon_filename
                FROM types
                WHERE categoryID = 11
            ''')
            npc_ships = cursor.fetchall()
            
            # 2. 获取所有typeAttributes中attribute_id=1766的数据
            cursor.execute('''
                SELECT type_id, value
                FROM typeAttributes
                WHERE attribute_id = 1766
            ''')
            type_attributes = cursor.fetchall()
            type_attributes_cache = {type_id: int(value) for type_id, value in type_attributes if value is not None}
            
            # 3. 获取所有groups数据
            cursor.execute('''
                SELECT group_id, en_name, zh_name, de_name, es_name, fr_name, ja_name, ko_name, ru_name
                FROM groups
            ''')
            groups = cursor.fetchall()
            groups_cache = {}
            for row in groups:
                group_id = row[0]
                groups_cache[group_id] = {
                    'en_name': row[1],
                    'zh_name': row[2],
                    'de_name': row[3],
                    'es_name': row[4],
                    'fr_name': row[5],
                    'ja_name': row[6],
                    'ko_name': row[7],
                    'ru_name': row[8]
                }
            
            conn.close()
            
            return {
                'npc_ships': npc_ships,
                'type_attributes_cache': type_attributes_cache,
                'groups_cache': groups_cache
            }
            
        except Exception as e:
            print(f"[x] 加载数据时出错: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def classify_npc_ships_for_language(self, language: str) -> bool:
        """
        为指定语言分类NPC船只（全部在内存中完成，最后批量写入数据库）
        """
        print(f"[+] 开始分类NPC船只，语言: {language}")
        
        # 加载 brackets_output.json 数据（仅在英文数据库时加载一次）
        if language == 'en':
            self.load_brackets_data()
        
        # 从数据库加载所有数据到内存
        data = self.load_data_from_db(language)
        if not data:
            return False
        
        npc_ships = data['npc_ships']
        type_attributes_cache = data['type_attributes_cache']
        groups_cache = data['groups_cache']
        
        print(f"[+] 找到 {len(npc_ships)} 个NPC船只需要分类")
        print(f"[+] 加载了 {len(type_attributes_cache)} 个属性1766记录")
        print(f"[+] 加载了 {len(groups_cache)} 个groups记录")
        
        # 在内存中存储所有分类结果
        classifications = {}  # {type_id: {scene, faction, type, faction_icon}}
            
        # 如果是英文数据库，处理并缓存分类结果
        if language == 'en':
            npc_classification_cache.clear()
            unmatched_items = []  # 记录未命中的物品
            
            for type_id, en_name, zh_name, group_name, category_id, group_id, icon_filename in npc_ships:
                # 计算分类
                npc_ship_scene_en = self.get_npc_ship_scene(group_name, 'en')
                npc_ship_scene_zh = self.get_npc_ship_scene(group_name, 'zh')
                npc_ship_faction_en = self.get_npc_ship_faction(group_name, 'en')
                npc_ship_faction_zh = self.get_npc_ship_faction(group_name, 'zh')
                npc_ship_type_en = self.get_npc_ship_type(type_id, group_name, en_name, group_id, category_id, 'en',
                                                      type_attributes_cache, groups_cache)
                npc_ship_type_zh = self.get_npc_ship_type(type_id, group_name, en_name, group_id, category_id, 'zh',
                                                      type_attributes_cache, groups_cache)
                npc_ship_faction_icon = self.get_faction_icon(npc_ship_faction_en)
                
                # 检查是否未命中（三个方法都失败，返回 Other/其他）
                if npc_ship_type_en == "Other" or npc_ship_type_zh == "其他":
                    unmatched_items.append({
                        'type_id': type_id,
                        'en_name': en_name,
                        'zh_name': zh_name or en_name
                    })
                
                # 保存到内存
                classifications[type_id] = {
                    'scene': {'en': npc_ship_scene_en, 'zh': npc_ship_scene_zh},
                    'faction': {'en': npc_ship_faction_en, 'zh': npc_ship_faction_zh},
                    'type': {'en': npc_ship_type_en, 'zh': npc_ship_type_zh},
                    'faction_icon': npc_ship_faction_icon,
                    'icon_filename': icon_filename
                }
                
                # 保存到全局缓存
                npc_classification_cache[type_id] = {
                    'scene': {'en': npc_ship_scene_en, 'zh': npc_ship_scene_zh},
                    'faction': {'en': npc_ship_faction_en, 'zh': npc_ship_faction_zh},
                    'type': {'en': npc_ship_type_en, 'zh': npc_ship_type_zh},
                    'faction_icon': npc_ship_faction_icon
                }
            
            # 打印英文数据库处理结果（在循环外部）
            print(f"[+] 英文数据库：成功分类 {len(npc_ships)} 个NPC船只")
            
            # 打印未命中的物品（在循环外部）
            if unmatched_items:
                print(f"\n[!] 未命中分类的物品（三个方法都失败）: {len(unmatched_items)} 个")
                print("=" * 80)
                for item in unmatched_items:
                    print(f"  type_id: {item['type_id']:>8}, en_name: {item['en_name']:<40}, zh_name: {item['zh_name']}")
                print("=" * 80)
            else:
                print("[+] 所有NPC船只都已成功分类")
        
        else:
            # 其他语言从缓存获取分类结果
            if not npc_classification_cache:
                print("[!] 警告：缓存为空，请先处理英文数据库")
                return False
            
            updated_count = 0
            
            for type_id, en_name, zh_name, group_name, category_id, group_id, icon_filename in npc_ships:
                if type_id in npc_classification_cache:
                    cached_data = npc_classification_cache[type_id]
                    
                    # 根据语言选择对应的值
                    if language == 'zh':
                        npc_ship_scene = cached_data['scene']['zh']
                        npc_ship_faction = cached_data['faction']['zh']
                        npc_ship_type = cached_data['type']['zh']
                    else:
                        # 其他语言使用英文版本
                        npc_ship_scene = cached_data['scene']['en']
                        npc_ship_faction = cached_data['faction']['en']
                        npc_ship_type = cached_data['type']['en']
                    
                    npc_ship_faction_icon = cached_data['faction_icon']
                    
                    # 保存到内存
                    classifications[type_id] = {
                        'scene': npc_ship_scene,
                        'faction': npc_ship_faction,
                        'type': npc_ship_type,
                        'faction_icon': npc_ship_faction_icon,
                        'icon_filename': icon_filename
                    }
                    updated_count += 1
            
            print(f"[+] {language}数据库：成功分类 {updated_count} 个NPC船只")
        
        # 在内存中执行修正逻辑
        self.correct_classifications_in_memory(classifications, language)
        
        # 批量写入数据库
        return self.write_classifications_to_db(language, classifications)
    
    def correct_classifications_in_memory(self, classifications: Dict[int, Dict[str, Any]], language: str) -> None:
        """
        在内存中修正"其他"分类
        """
        # 确定"其他"的值（仅中文使用中文，其余语言使用英文）
        other_faction = "其他" if language == "zh" else "Other"
        other_type = "其他" if language == "zh" else "Other"
        
        # 构建按图标分组的索引
        icon_index = {}  # {icon_filename: [type_id, ...]}
        for type_id, data in classifications.items():
            icon_filename = data.get('icon_filename')
            if icon_filename:
                if icon_filename not in icon_index:
                    icon_index[icon_filename] = []
                icon_index[icon_filename].append(type_id)
        
        corrected_count = 0
        
        # 修正每个需要修正的记录
        for type_id, data in classifications.items():
            current_faction = data.get('faction', {}).get(language) if isinstance(data.get('faction'), dict) else data.get('faction')
            current_type = data.get('type', {}).get(language) if isinstance(data.get('type'), dict) else data.get('type')
            icon_filename = data.get('icon_filename')
            
            # 如果不需要修正，跳过
            if (current_faction != other_faction and current_type != other_type) or not icon_filename:
                continue
            
            # 查找同图标的其他物品
            same_icon_type_ids = icon_index.get(icon_filename, [])
            same_icon_type_ids = [tid for tid in same_icon_type_ids if tid != type_id]
            
            if not same_icon_type_ids:
                continue
            
            # 找到第一个非"其他"的值
            new_faction = current_faction
            new_type = current_type
            faction_found = False
            type_found = False
            
            for other_type_id in same_icon_type_ids:
                other_data = classifications.get(other_type_id)
                if not other_data:
                    continue
                
                other_faction_val = other_data.get('faction', {}).get(language) if isinstance(other_data.get('faction'), dict) else other_data.get('faction')
                other_type_val = other_data.get('type', {}).get(language) if isinstance(other_data.get('type'), dict) else other_data.get('type')
                
                # 修正 faction（只有当当前是"其他"时才修正）
                if not faction_found and current_faction == other_faction:
                    if other_faction_val and other_faction_val != other_faction:
                        new_faction = other_faction_val
                        faction_found = True
                
                # 修正 type（只有当当前是"其他"时才修正）
                if not type_found and current_type == other_type:
                    if other_type_val and other_type_val != other_type:
                        new_type = other_type_val
                        type_found = True
                
                # 如果两个都已经修正，可以提前退出
                if (current_faction != other_faction or faction_found) and (current_type != other_type or type_found):
                    break
            
            # 如果有修正，更新内存中的数据
            if new_faction != current_faction or new_type != current_type:
                if isinstance(data.get('faction'), dict):
                    data['faction'][language] = new_faction
                else:
                    data['faction'] = new_faction
                
                if isinstance(data.get('type'), dict):
                    data['type'][language] = new_type
                else:
                    data['type'] = new_type
                
                corrected_count += 1
        
        if corrected_count > 0:
            print(f"[+] 内存中修正了 {corrected_count} 个'其他'分类")
    
    def write_classifications_to_db(self, language: str, classifications: Dict[int, Dict[str, Any]]) -> bool:
        """
        将分类结果批量写入数据库
        """
        db_path = self.db_output_path / f"item_db_{language}.sqlite"
        
        if not db_path.exists():
            print(f"[!] 数据库文件不存在: {db_path}")
            return False
        
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            update_batch = []
            batch_size = 1000
            
            for type_id, data in classifications.items():
                # 根据语言选择对应的值
                if language == 'en':
                    scene = data['scene']['en'] if isinstance(data['scene'], dict) else data['scene']
                    faction = data['faction']['en'] if isinstance(data['faction'], dict) else data['faction']
                    ship_type = data['type']['en'] if isinstance(data['type'], dict) else data['type']
                elif language == 'zh':
                    scene = data['scene']['zh'] if isinstance(data['scene'], dict) else data['scene']
                    faction = data['faction']['zh'] if isinstance(data['faction'], dict) else data['faction']
                    ship_type = data['type']['zh'] if isinstance(data['type'], dict) else data['type']
                else:
                    # 其他语言使用英文版本
                    scene = data['scene']['en'] if isinstance(data['scene'], dict) else data['scene']
                    faction = data['faction']['en'] if isinstance(data['faction'], dict) else data['faction']
                    ship_type = data['type']['en'] if isinstance(data['type'], dict) else data['type']
                
                faction_icon = data['faction_icon']
                
                update_batch.append((
                    scene,
                    faction,
                    ship_type,
                    faction_icon,
                    type_id
                ))
                
                # 批量更新
                if len(update_batch) >= batch_size:
                    cursor.executemany('''
                        UPDATE types
                        SET npc_ship_scene = ?,
                            npc_ship_faction = ?,
                            npc_ship_type = ?,
                            npc_ship_faction_icon = ?
                        WHERE type_id = ?
                    ''', update_batch)
                    update_batch = []
                
                # 处理剩余的数据
                if update_batch:
                    cursor.executemany('''
                UPDATE types
                SET npc_ship_scene = ?,
                    npc_ship_faction = ?,
                    npc_ship_type = ?,
                    npc_ship_faction_icon = ?
                WHERE type_id = ?
                    ''', update_batch)
            
            # 提交更改
            conn.commit()
            conn.close()
            
            print(f"[+] 成功写入 {len(classifications)} 个分类结果到数据库")
            print(f"[+] NPC船只分类完成，语言: {language}")
            return True
            
        except Exception as e:
            print(f"[x] 写入数据库时出错: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def classify_all_languages(self) -> bool:
        """
        为所有语言分类NPC船只（所有逻辑在内存中完成，最后批量写入数据库）
        """
        print("[+] 开始分类NPC船只")
        
        success_count = 0
        for language in self.languages:
            if self.classify_npc_ships_for_language(language):
                success_count += 1
        
        print(f"[+] NPC船只分类完成，成功处理 {success_count}/{len(self.languages)} 个语言")
        return success_count > 0


def main(config=None):
    """主函数"""
    print("[+] NPC船只分类处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    classifier = NPCShipClassifier(config)
    classifier.classify_all_languages()
    
    print("\n[+] NPC船只分类处理器完成")


if __name__ == "__main__":
    main()

