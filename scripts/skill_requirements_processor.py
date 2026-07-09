#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
技能需求数据处理器模块
用于处理物品的技能需求数据并写入数据库

对应old版本: old/typeSkillRequirements_handler.py
功能: 从types表和typeAttributes表获取数据，生成技能需求信息
"""

import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional


class SkillRequirementsProcessor:
    """技能需求数据处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化技能需求处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.db_output_path = self.project_root / config["paths"]["db_output"]
        self.languages = config.get("languages", ["en"])
    
    def create_skill_requirements_table(self, cursor: sqlite3.Cursor):
        """创建技能需求表"""
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS typeSkillRequirement (
            typeid INTEGER NOT NULL,
            typename TEXT,
            typeicon TEXT,
            published BOOLEAN,
            categoryID INTEGER,
            category_name TEXT,
            required_skill_id INTEGER NOT NULL,
            required_skill_level INTEGER,
            PRIMARY KEY (typeid, required_skill_id)
        )
        ''')
        print("[+] 创建typeSkillRequirement表")
    
    def process_skill_requirements_to_db(self, cursor: sqlite3.Cursor, lang: str):
        """
        处理技能需求数据并写入数据库
        完全按照old版本的逻辑
        """
        try:
            # 创建表
            self.create_skill_requirements_table(cursor)
            
            # 清空现有数据
            cursor.execute('DELETE FROM typeSkillRequirement')
            
            # 技能需求的属性ID映射
            skill_requirements = [
                (182, 277),   # 主技能
                (183, 278),   # 副技能
                (184, 279),   # 三级技能
                (1285, 1286), # 四级技能
                (1289, 1287), # 五级技能
                (1290, 1288)  # 六级技能
            ]
            
            # 获取所有物品
            cursor.execute('''
                SELECT type_id, name, icon_filename, published, categoryID, category_name 
                FROM types 
            ''')
            items = cursor.fetchall()
            
            print(f"[+] 开始处理技能需求数据，共 {len(items)} 个物品，语言: {lang}")
            
            # 处理每个物品的技能需求
            processed_count = 0
            for item in items:
                type_id, type_name, type_icon, published, categoryID, category_name = item
                
                # 检查每个可能的技能需求
                for skill_attr_id, level_attr_id in skill_requirements:
                    # 查找技能ID
                    cursor.execute('''
                        SELECT value 
                        FROM typeAttributes 
                        WHERE type_id = ? AND attribute_id = ?
                    ''', (type_id, skill_attr_id))
                    skill_result = cursor.fetchone()
                    
                    if skill_result:
                        required_skill_id = int(float(skill_result[0]))
                        
                        # 查找需要的等级
                        cursor.execute('''
                            SELECT value 
                            FROM typeAttributes 
                            WHERE type_id = ? AND attribute_id = ?
                        ''', (type_id, level_attr_id))
                        level_result = cursor.fetchone()
                        
                        if level_result:
                            required_level = int(float(level_result[0]))
                            
                            # 插入数据
                            cursor.execute('''
                                INSERT OR REPLACE INTO typeSkillRequirement 
                                (typeid, typename, typeicon, published, categoryID, category_name, required_skill_id, required_skill_level)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (type_id, type_name, type_icon, published, categoryID, category_name, required_skill_id, required_level))
                            processed_count += 1
            
            print(f"[+] 技能需求数据处理完成，共处理 {processed_count} 个技能需求，语言: {lang}")
            
        except Exception as e:
            print(f"[x] 处理过程中出错: {str(e)}")
            raise
    
    def process_skill_requirements_for_language(self, language: str) -> bool:
        """
        为指定语言处理技能需求数据
        """
        print(f"[+] 开始处理技能需求数据，语言: {language}")
        
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
            self.process_skill_requirements_to_db(cursor, language)
            
            # 提交更改
            conn.commit()
            print(f"[+] 技能需求数据处理完成，语言: {language}")
            return True
            
        except Exception as e:
            print(f"[x] 处理技能需求数据时出错: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()
    
    def process_all_languages(self) -> bool:
        """
        为所有语言处理技能需求数据
        """
        print("[+] 开始处理技能需求数据")
        
        success_count = 0
        for language in self.languages:
            if self.process_skill_requirements_for_language(language):
                success_count += 1
        
        print(f"[+] 技能需求数据处理完成，成功处理 {success_count}/{len(self.languages)} 个语言")
        return success_count > 0


def main(config=None):
    """主函数"""
    print("[+] 技能需求数据处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = SkillRequirementsProcessor(config)
    processor.process_all_languages()
    
    print("\n[+] 技能需求数据处理器完成")


if __name__ == "__main__":
    main()
