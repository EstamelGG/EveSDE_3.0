#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
代理人本地化处理器模块
用于更新agents表的本地化信息

对应old版本: old/agent_localization_handler.py
功能: 完全按照old版本的逻辑实现agent name的本地化处理
"""

import json
import sqlite3
import os
import time
from pathlib import Path
from utils.http_client import create_session
from typing import Dict, Any, List


class AgentLocalizationProcessor:
    """代理人本地化处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化代理人本地化处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.db_output_path = self.project_root / config["paths"]["db_output"]
        self.languages = config.get("languages", ["en"])
        self.session = create_session(verify=False)  # 禁用SSL验证
        self.session.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
    
    def load_localization_mapping(self) -> Dict[str, Any]:
        """
        加载英文到多种语言的映射文件
        只从localization/output目录获取
        """
        mapping_file = self.project_root / "localization" / "output" / "en_multi_lang_mapping.json"
        
        if not mapping_file.exists():
            print(f"[x] 找不到本地化映射文件: {mapping_file}")
            return {}
        
        try:
            with open(mapping_file, 'r', encoding='utf-8') as f:
                print(f"[+] 成功加载本地化映射文件: {mapping_file}")
                return json.load(f)
        except Exception as e:
            print(f"[x] 加载本地化映射文件时出错: {e}")
            return {}
    
    def get_agent_names_from_esi(self, agent_ids: List[int]) -> Dict[int, str]:
        """
        通过ESI API获取agent名称
        每次最多发送1000个ID
        """
        agent_names = {}
        
        # 分批处理，每批最多1000个ID
        batch_size = 1000
        for i in range(0, len(agent_ids), batch_size):
            batch_ids = agent_ids[i:i + batch_size]
            
            try:
                print(f"[+] 从ESI获取agent名称，批次 {i//batch_size + 1}，ID数量: {len(batch_ids)}")
                
                response = self.session.post(
                    'https://esi.evetech.net/universe/names',
                    json=batch_ids,
                    timeout=30
                )
                
                batch_results = response.json()
                for item in batch_results:
                    if item.get('category') == 'character':  # agent是character类型
                        agent_names[item['id']] = item['name']
                
                print(f"[+] 成功获取 {len(batch_results)} 个名称")
                
                # 避免请求过于频繁
                time.sleep(0.1)
                
            except Exception as e:
                print(f"[x] 获取agent名称失败，批次 {i//batch_size + 1}: {e}")
                continue
        
        print(f"[+] 总共获取到 {len(agent_names)} 个agent名称")
        return agent_names
    
    def update_agents_localization(self):
        """
        更新agents表的本地化信息
        只处理那些在JSONL中没有名称的agent，使用ESI API作为补充
        """
        print("[+] 开始更新agents表的本地化信息...")
        
        # 加载本地化映射
        localization_mapping = self.load_localization_mapping()
        if not localization_mapping:
            print("[x] 无法加载本地化映射，跳过agents本地化更新")
            return False
        
        # 确保输出目录存在
        self.db_output_path.mkdir(parents=True, exist_ok=True)
        
        # 首先收集所有agent_id和检查哪些没有名称
        all_agent_ids = set()
        agents_without_names = set()
        
        for lang in self.languages:
            db_filename = self.db_output_path / f'item_db_{lang}.sqlite'
            if db_filename.exists():
                try:
                    conn = sqlite3.connect(str(db_filename))
                    cursor = conn.cursor()
                    
                    # 检查agents表是否存在
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='agents'")
                    if not cursor.fetchone():
                        print(f"[-] 数据库 {db_filename} 中不存在agents表，跳过")
                        conn.close()
                        continue
                    
                    # 获取所有agent_id
                    cursor.execute("SELECT agent_id FROM agents")
                    agent_ids = [row[0] for row in cursor.fetchall()]
                    all_agent_ids.update(agent_ids)
                    
                    # 检查哪些agent没有名称（agent_name为NULL或空字符串）
                    cursor.execute("SELECT agent_id FROM agents WHERE agent_name IS NULL OR agent_name = ''")
                    agents_without_names.update([row[0] for row in cursor.fetchall()])
                    
                    conn.close()
                except Exception as e:
                    print(f"[x] 读取数据库 {db_filename} 时出错: {e}")
        
        if not all_agent_ids:
            print("[x] 没有找到任何agent记录")
            return False
        
        print(f"[+] 找到 {len(all_agent_ids)} 个唯一的agent ID")
        print(f"[+] 其中 {len(agents_without_names)} 个agent没有名称，需要从ESI获取")
        
        # 只对没有名称的agent通过ESI API获取名称
        agent_names = {}
        if agents_without_names:
            agent_names = self.get_agent_names_from_esi(list(agents_without_names))
            print(f"[+] 从ESI获取到 {len(agent_names)} 个agent名称")
        else:
            print("[+] 所有agent都有名称，无需从ESI获取")
        
        success_count = 0
        
        for lang in self.languages:
            db_filename = self.db_output_path / f'item_db_{lang}.sqlite'
            
            if not db_filename.exists():
                print(f"[-] 数据库文件 {db_filename} 不存在，跳过")
                continue
                
            print(f"[+] 处理数据库: {db_filename}, 语言代码: {lang}")
            
            try:
                # 连接数据库
                conn = sqlite3.connect(str(db_filename))
                cursor = conn.cursor()
                
                # 检查agents表是否存在
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='agents'")
                if not cursor.fetchone():
                    print(f"[-] 数据库 {db_filename} 中不存在agents表，跳过")
                    conn.close()
                    continue
                
                # 检查agent_name列是否存在，如果不存在则添加
                cursor.execute("PRAGMA table_info(agents)")
                columns = [column[1] for column in cursor.fetchall()]
                if 'agent_name' not in columns:
                    print(f"[+] 在数据库 {db_filename} 中添加agent_name列")
                    cursor.execute("ALTER TABLE agents ADD COLUMN agent_name TEXT")
                
                # 只获取没有名称的agents记录
                cursor.execute("SELECT agent_id FROM agents WHERE agent_name IS NULL OR agent_name = ''")
                agents_without_names = cursor.fetchall()
                
                if not agents_without_names:
                    print(f"[+] 数据库 {db_filename} 中所有agent都有名称，无需更新")
                    conn.close()
                    continue
                
                print(f"[+] 找到 {len(agents_without_names)} 个没有名称的代理人记录")
                
                # 更新每条没有名称的记录
                updated_count = 0
                not_found_count = 0
                esi_not_found_count = 0
                
                for (agent_id,) in agents_without_names:
                    # 从ESI获取的名称中查找英文名称
                    if agent_id in agent_names:
                        english_name = agent_names[agent_id]
                        
                        # 查找对应的本地化文本
                        if english_name in localization_mapping and lang in localization_mapping[english_name]:
                            localized_name = localization_mapping[english_name][lang]
                            
                            # 更新agent_name
                            cursor.execute("""
                                UPDATE agents 
                                SET agent_name = ? 
                                WHERE agent_id = ?
                            """, (localized_name, agent_id))
                            
                            updated_count += 1
                        else:
                            # 如果找不到本地化文本，使用原始英文名称
                            cursor.execute("""
                                UPDATE agents 
                                SET agent_name = ? 
                                WHERE agent_id = ?
                            """, (english_name, agent_id))
                            
                            not_found_count += 1
                    else:
                        # 如果ESI中找不到，使用agent_id作为名称
                        cursor.execute("""
                            UPDATE agents 
                            SET agent_name = ? 
                            WHERE agent_id = ?
                        """, (f"Agent {agent_id}", agent_id))
                        
                        esi_not_found_count += 1
                
                # 提交更改
                conn.commit()
                print(f"[+] 成功更新了 {updated_count} 条记录（使用本地化映射），{not_found_count} 条记录使用原始英文名称，{esi_not_found_count} 条记录使用默认名称")
                success_count += 1
                
            except Exception as e:
                print(f"[x] 处理数据库 {db_filename} 时出错: {e}")
            finally:
                if 'conn' in locals():
                    conn.close()
        
        print(f"[+] 本地化更新完成，成功处理了 {success_count} 个数据库")
        print(f"[+] 数据来源统计:")
        print(f"    - 从JSONL获取名称: {len(all_agent_ids) - len(agents_without_names)} 个agent")
        print(f"    - 从ESI获取名称: {len(agents_without_names)} 个agent")
        return success_count > 0


def main(config=None):
    """主函数"""
    print("[+] 代理人本地化处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = AgentLocalizationProcessor(config)
    processor.update_agents_localization()
    
    print("\n[+] 代理人本地化处理器完成")


if __name__ == "__main__":
    main()
