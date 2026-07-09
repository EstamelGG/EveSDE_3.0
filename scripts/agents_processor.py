#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
代理人处理器模块
处理EVE代理人数据并存储到数据库

注意：从SDE Build 3031812开始，agents和researchAgents已合并到npcCharacters中
新数据结构中，只有包含agent字段的行才是真正的代理人
agent字段包含agentTypeID、divisionID、isLocator、level等信息
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, Any, List
import scripts.jsonl_loader as jsonl_loader


class AgentsProcessor:
    """EVE代理人处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化代理人处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.sde_input_path = self.project_root / config["paths"]["sde_input"]
        
        # 缓存数据
        self.agents_data = {}
        self.agents_in_space_data = {}
        self.research_agents_data = {}
    
    def load_agents_data(self):
        """加载代理人数据"""
        print("[+] 加载代理人数据...")
        
        # 加载npcCharacters数据（新版本合并了agents和researchAgents）
        # 新数据结构中，只有包含agent字段的行才是真正的代理人
        npc_characters_file = self.sde_input_path / "npcCharacters.jsonl"
        if npc_characters_file.exists():
            npc_characters_list = jsonl_loader.load_jsonl(str(npc_characters_file))
            self.agents_data = {item['_key']: item for item in npc_characters_list}
            print(f"[+] 加载了 {len(self.agents_data)} 个NPC角色")
            
            # 统计真正的代理人数量
            agent_count = sum(1 for item in self.agents_data.values() if 'agent' in item)
            print(f"[+] 其中包含 {agent_count} 个真正的代理人（有agent字段）")
        else:
            print(f"[x] NPC角色文件不存在: {npc_characters_file}")
        
        # 加载agentsInSpace数据
        agents_in_space_file = self.sde_input_path / "agentsInSpace.jsonl"
        if agents_in_space_file.exists():
            agents_in_space_list = jsonl_loader.load_jsonl(str(agents_in_space_file))
            self.agents_in_space_data = {item['_key']: item for item in agents_in_space_list}
            print(f"[+] 加载了 {len(self.agents_in_space_data)} 个太空中的代理人")
        else:
            print(f"[x] 太空代理人文件不存在: {agents_in_space_file}")
        
        # 清空research_agents_data，因为已经合并到npcCharacters中
        self.research_agents_data = {}
    
    def create_agents_table(self, cursor: sqlite3.Cursor):
        """创建agents表"""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agents (
                agent_id INTEGER NOT NULL PRIMARY KEY,
                agent_type INTEGER,
                corporationID INTEGER,
                divisionID INTEGER,
                isLocator INTEGER,
                level INTEGER,
                locationID INTEGER,
                solarSystemID INTEGER,
                agent_name TEXT
            )
        ''')
        
        # 创建索引以优化查询性能
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_agents_solarSystemID ON agents(solarSystemID)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_agents_locationID ON agents(locationID)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_agents_corporationID ON agents(corporationID)')
    
    def process_agents_to_db(self, cursor: sqlite3.Cursor, lang: str = 'en'):
        """处理代理人数据并插入数据库"""
        print(f"[+] 开始处理代理人数据 (语言: {lang})...")
        
        # 清空现有数据
        cursor.execute('DELETE FROM agents')
        
        # 首先，从agentsInSpace.jsonl中提取所有代理的太阳系ID
        agents_solar_systems = {}
        for agent_id, agent_data in self.agents_in_space_data.items():
            agents_solar_systems[agent_id] = agent_data.get('solarSystemID')
        
        agents_batch = []
        batch_size = 1000
        
        # 处理每个代理
        for agent_id, agent_data in self.agents_data.items():
            # 只处理包含agent字段的行（真正的代理人）
            if 'agent' not in agent_data:
                continue
            
            # 从agent字段获取代理人信息
            agent_info = agent_data['agent']
            agent_type = agent_info.get('agentTypeID')
            division_id = agent_info.get('divisionID')
            is_locator = 1 if agent_info.get('isLocator', False) else 0
            level = agent_info.get('level')
            
            # 从主对象获取其他信息
            corporation_id = agent_data.get('corporationID')
            location_id = agent_data.get('locationID')
            
            # 获取多语言名称
            agent_name = None
            if 'name' in agent_data and isinstance(agent_data['name'], dict):
                agent_name = agent_data['name'].get(lang, agent_data['name'].get('en', None))
            
            # 如果代理在太空中，获取其太阳系ID，否则为NULL
            solar_system_id = agents_solar_systems.get(agent_id)
            
            agents_batch.append((
                agent_id, agent_type, corporation_id, division_id,
                is_locator, level, location_id, solar_system_id, agent_name
            ))
            
            # 批量插入
            if len(agents_batch) >= batch_size:
                cursor.executemany('''
                    INSERT OR REPLACE INTO agents (
                        agent_id, agent_type, corporationID, divisionID,
                        isLocator, level, locationID, solarSystemID, agent_name
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', agents_batch)
                agents_batch = []
        
        # 处理剩余数据
        if agents_batch:
            cursor.executemany('''
                INSERT OR REPLACE INTO agents (
                    agent_id, agent_type, corporationID, divisionID,
                    isLocator, level, locationID, solarSystemID, agent_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', agents_batch)
        
        # 统计信息
        cursor.execute('SELECT COUNT(*) FROM agents')
        agents_count = cursor.fetchone()[0]
        print(f"[+] 代理人数据处理完成: {agents_count} 个代理人")
    
    def process_agents_data(self, cursor: sqlite3.Cursor, lang: str = 'en'):
        """
        处理所有代理人数据并插入数据库
        
        Args:
            cursor: 数据库游标
            lang: 数据库使用的语言代码
        """
        print(f"[+] 开始处理代理人数据 (语言: {lang})...")
        start_time = time.time()
        
        # 创建表
        self.create_agents_table(cursor)
        
        # 处理代理人数据
        self.process_agents_to_db(cursor, lang)
        
        end_time = time.time()
        print(f"[+] 代理人数据处理完成，耗时: {end_time - start_time:.2f} 秒")
    
    def update_all_databases(self, config):
        """更新所有语言的数据库"""
        project_root = Path(__file__).parent.parent
        db_output_path = project_root / config["paths"]["db_output"]
        languages = config.get("languages", ["en"])
        
        # 加载代理人数据
        self.load_agents_data()
        
        # 为每种语言创建数据库并处理数据
        for lang in languages:
            db_filename = db_output_path / f'item_db_{lang}.sqlite'
            
            print(f"\n[+] 处理数据库: {db_filename}")
            
            try:
                conn = sqlite3.connect(str(db_filename))
                cursor = conn.cursor()
                
                # 处理代理人数据
                self.process_agents_data(cursor, lang)
                
                # 提交事务
                conn.commit()
                conn.close()
                
                print(f"[+] 数据库 {lang} 更新完成")
                
            except Exception as e:
                print(f"[x] 处理数据库 {db_filename} 时出错: {e}")


def main(config=None):
    """主函数"""
    print("[+] 代理人处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = AgentsProcessor(config)
    processor.update_all_databases(config)
    
    print("\n[+] 代理人处理器完成")


if __name__ == "__main__":
    main()
