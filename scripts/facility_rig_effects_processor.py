#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设施装配效果数据处理器模块
用于处理设施装配效果数据并写入数据库

功能: 从外部URL下载工业修正源数据和目标过滤器数据，处理设施装配效果
数据源:
- https://sde.hoboleaks.space/tq/industrymodifiersources.json
- https://sde.hoboleaks.space/tq/industrytargetfilters.json
"""

import json
import sqlite3
from pathlib import Path
from utils.http_client import get
from typing import Dict, List, Tuple, Optional, Any


class FacilityRigEffectsProcessor:
    """设施装配效果数据处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化设施装配效果处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.db_output_path = self.project_root / config["paths"]["db_output"]
        self.languages = config.get("languages", ["en"])
        
        # 缓存数据
        self._modifier_data = None
        self._filter_data = None
    
    def download_json(self, url: str) -> Dict:
        """下载并解析JSON文件"""
        print(f"[+] 正在下载: {url}")
        try:
            response = get(url, timeout=30, verify=False)
            return response.json()
        except Exception as e:
            print(f"[x] 下载失败: {e}")
            raise
    
    def create_facility_rig_effects_table(self, cursor: sqlite3.Cursor):
        """创建设施装配效果表"""
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS facility_rig_effects (
            id INTEGER NOT NULL,
            category INTEGER NOT NULL,
            group_id INTEGER NOT NULL,
            PRIMARY KEY (id, category, group_id)
        )
        ''')
        print("[+] 创建facility_rig_effects表")
    
    def get_dogma_attribute_ids_from_data(self, activity_data: Dict) -> List[int]:
        """从活动数据中提取所有的dogmaAttributeID"""
        attribute_ids = set()
        
        # 从material中收集dogmaAttributeID
        for material in activity_data.get('material', []):
            if 'dogmaAttributeID' in material:
                attribute_ids.add(material['dogmaAttributeID'])
        
        # 从time中收集dogmaAttributeID
        for time_item in activity_data.get('time', []):
            if 'dogmaAttributeID' in time_item:
                attribute_ids.add(time_item['dogmaAttributeID'])
        
        return list(attribute_ids)
    
    def process_industry_modifier_sources(
        self, 
        modifier_data: Dict, 
        filter_data: Dict, 
        cursor: sqlite3.Cursor
    ) -> List[Tuple]:
        """处理工业修正源数据"""
        facility_effects = []
        
        for facility_id, facility_data in modifier_data.items():
            facility_id = int(facility_id)
            
            # 检查设施是否在types表中且marketGroupID不为null
            cursor.execute('''
                SELECT marketGroupID FROM types 
                WHERE type_id = ? AND marketGroupID IS NOT NULL
            ''', (facility_id,))
            market_group_result = cursor.fetchone()
            
            # 如果设施不在types表中或marketGroupID为null，跳过
            if not market_group_result:
                continue
            
            # 只处理manufacturing和reaction相关数据
            for activity_type in ['manufacturing', 'reaction']:
                if activity_type not in facility_data:
                    continue
                    
                activity_data = facility_data[activity_type]
                
                # 获取活动数据中的所有dogmaAttributeID
                dogma_attribute_ids = self.get_dogma_attribute_ids_from_data(activity_data)
                
                # 分别收集material和time的filterID和dogmaAttributeID映射
                material_filter_dogma_map = {}  # ME相关属性
                time_filter_dogma_map = {}      # TE相关属性
                
                # 从material中收集filterID和dogmaAttributeID的映射（ME属性）
                for material in activity_data.get('material', []):
                    if 'dogmaAttributeID' in material:
                        filter_id = material.get('filterID', None)
                        dogma_attr_id = material['dogmaAttributeID']
                        material_filter_dogma_map[filter_id] = dogma_attr_id
                
                # 从time中收集filterID和dogmaAttributeID的映射（TE属性）
                for time_item in activity_data.get('time', []):
                    if 'dogmaAttributeID' in time_item:
                        filter_id = time_item.get('filterID', None)
                        dogma_attr_id = time_item['dogmaAttributeID']
                        time_filter_dogma_map[filter_id] = dogma_attr_id
                
                # 合并所有的filterID，为每个filter创建记录
                all_filter_ids = set(material_filter_dogma_map.keys()) | set(time_filter_dogma_map.keys())
                
                for filter_id in all_filter_ids:
                    if filter_id is None:
                        # 没有filterID，表示对所有物品有效
                        facility_effects.append((facility_id, 0, 0))
                    else:
                        # 有filterID，需要查找对应的category和group
                        filter_id_str = str(filter_id)
                        if filter_id_str in filter_data:
                            filter_info = filter_data[filter_id_str]
                            
                            # 处理categoryIDs
                            if 'categoryIDs' in filter_info:
                                for category_id in filter_info['categoryIDs']:
                                    facility_effects.append((facility_id, category_id, 0))
                            
                            # 处理groupIDs
                            if 'groupIDs' in filter_info:
                                for group_id in filter_info['groupIDs']:
                                    facility_effects.append((facility_id, 0, group_id))
                            
                            # 如果既没有categoryIDs也没有groupIDs，使用默认值
                            if 'categoryIDs' not in filter_info and 'groupIDs' not in filter_info:
                                facility_effects.append((facility_id, 0, 0))
        
        return facility_effects
    
    def insert_facility_rig_effects(self, cursor: sqlite3.Cursor, effects_data: List[Tuple]):
        """插入设施装配效果数据到数据库"""
        cursor.execute('DELETE FROM facility_rig_effects')
        
        cursor.executemany('''
            INSERT OR REPLACE INTO facility_rig_effects 
            (id, category, group_id)
            VALUES (?, ?, ?)
        ''', effects_data)
    
    def process_facility_rig_effects_to_db(self, cursor: sqlite3.Cursor, lang: str):
        """处理设施装配效果数据并写入数据库"""
        try:
            # 首次处理时下载数据，避免重复下载
            if self._modifier_data is None:
                print("[+] 下载工业修正源数据...")
                modifier_url = "https://sde.hoboleaks.space/tq/industrymodifiersources.json"
                filter_url = "https://sde.hoboleaks.space/tq/industrytargetfilters.json"
                
                self._modifier_data = self.download_json(modifier_url)
                self._filter_data = self.download_json(filter_url)
                
                print(f"[+] 下载完成 - 修正源数据: {len(self._modifier_data)} 个设施")
                print(f"[+] 下载完成 - 目标过滤器: {len(self._filter_data)} 个过滤器")
            
            # 创建表
            self.create_facility_rig_effects_table(cursor)
            
            # 处理数据
            effects_data = self.process_industry_modifier_sources(self._modifier_data, self._filter_data, cursor)
            
            # 插入数据
            self.insert_facility_rig_effects(cursor, effects_data)
            
            # 显示统计信息
            cursor.execute('SELECT COUNT(*) FROM facility_rig_effects')
            total_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(DISTINCT id) FROM facility_rig_effects')
            facility_count = cursor.fetchone()[0]
            
            print(f"[+] 语言 {lang}: 总记录数 {total_count}, 设施数量 {facility_count}")
            
        except Exception as e:
            print(f"[x] 处理过程中出错: {str(e)}")
            raise
    
    def process_facility_rig_effects_for_language(self, language: str) -> bool:
        """为指定语言处理设施装配效果数据"""
        print(f"[+] 开始处理设施装配效果数据，语言: {language}")
        
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
            self.process_facility_rig_effects_to_db(cursor, language)
            
            # 提交更改
            conn.commit()
            print(f"[+] 设施装配效果数据处理完成，语言: {language}")
            return True
            
        except Exception as e:
            print(f"[x] 处理设施装配效果数据时出错: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()
    
    def process_all_languages(self) -> bool:
        """为所有语言处理设施装配效果数据"""
        print("[+] 开始处理设施装配效果数据")
        
        success_count = 0
        for language in self.languages:
            if self.process_facility_rig_effects_for_language(language):
                success_count += 1
        
        print(f"[+] 设施装配效果数据处理完成，成功处理 {success_count}/{len(self.languages)} 个语言")
        return success_count > 0


def main(config=None):
    """主函数"""
    print("[+] 设施装配效果数据处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = FacilityRigEffectsProcessor(config)
    processor.process_all_languages()
    
    print("\n[+] 设施装配效果数据处理器完成")


if __name__ == "__main__":
    main()
