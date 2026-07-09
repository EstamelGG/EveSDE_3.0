#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NPC公司处理器模块
处理EVE NPC公司数据并存储到数据库
"""

import json
import sqlite3
import time
import asyncio
import aiohttp
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import scripts.jsonl_loader as jsonl_loader


class NpcCorporationsProcessor:
    """EVE NPC公司处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化NPC公司处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.sde_input_path = self.project_root / config["paths"]["sde_input"]
        self.custom_icons_path = self.project_root / "custom_icons"
        
        # 确保自定义图标目录存在
        self.custom_icons_path.mkdir(parents=True, exist_ok=True)
        
        # 缓存数据
        self.corporations_data = {}
        # ESI API配置
        self.esi_base_url = "https://esi.evetech.net"
        self.max_concurrent = 20  # 最大并发数
        self.request_timeout = aiohttp.ClientTimeout(total=30)
    
    def load_corporations_data(self):
        """加载NPC公司数据"""
        print("[+] 加载NPC公司数据...")
        
        # 加载NPC公司数据
        corporations_file = self.sde_input_path / "npcCorporations.jsonl"
        if corporations_file.exists():
            corporations_list = jsonl_loader.load_jsonl(str(corporations_file))
            self.corporations_data = {item['_key']: item for item in corporations_list}
            print(f"[+] 加载了 {len(self.corporations_data)} 个NPC公司")
        else:
            print(f"[x] NPC公司文件不存在: {corporations_file}")
    
    async def download_corporation_icon(self, corp_id: int, output_dir: Path, semaphore: asyncio.Semaphore, retry_count: int = 15) -> str:
        """下载单个军团图标，带有重试逻辑"""
        url = f"https://images.evetech.net/corporations/{corp_id}/logo?size=128"
        filename = f"corperation_{corp_id}_128.png"
        filepath = output_dir / filename
        
        # 如果文件已存在，直接返回文件名
        if filepath.exists():
            # print(f"[+] 图标已存在，跳过下载: {filename}")
            return filename
        
        async with semaphore:  # 使用信号量限制并发数
            for attempt in range(retry_count):
                try:
                    # 创建SSL上下文，忽略证书验证
                    ssl_context = aiohttp.TCPConnector(ssl=False)
                    async with aiohttp.ClientSession(connector=ssl_context) as session:
                        async with session.get(url, timeout=10) as response:
                            if response.status == 200:
                                content = await response.read()
                                with open(filepath, 'wb') as f:
                                    f.write(content)
                                print(f"[+] 成功下载图标: {url} -> {filename}")
                                return filename
                            else:
                                print(f"[-] 下载失败 (HTTP {response.status}): {filename}")
                except asyncio.TimeoutError:
                    print(f"[-] 超时 (尝试 {attempt + 1}/{retry_count}): {filename}")
                except Exception as e:
                    print(f"[-] 错误 (尝试 {attempt + 1}/{retry_count}): {filename} - {str(e)}")
                
                if attempt < retry_count - 1:
                    await asyncio.sleep(1)  # 重试前等待1秒
        
        print(f"[x] 所有重试均失败: {filename}")
        return None
    
    async def download_all_corporation_icons(self, corp_ids: List[int], output_dir: Path) -> Dict[int, str]:
        """下载所有军团图标"""
        # 创建输出目录
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建信号量以限制并发请求数
        semaphore = asyncio.Semaphore(10)
        
        # 创建下载任务
        tasks = [
            self.download_corporation_icon(corp_id, output_dir, semaphore)
            for corp_id in corp_ids
        ]
        
        print(f"[+] 准备下载 {len(corp_ids)} 个军团图标...")
        
        # 异步执行所有下载任务
        results = await asyncio.gather(*tasks)
        
        # 返回结果字典
        return {corp_id: filename for corp_id, filename in zip(corp_ids, results) if filename}
    
    async def fetch_corporation_faction(
        self,
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        corporation_id: int
    ) -> Optional[int]:
        """
        获取单个军团的faction_id（异步）
        
        Args:
            session: aiohttp会话
            semaphore: 并发控制信号量
            corporation_id: 军团ID
        
        Returns:
            faction_id，如果不是卫队军团则返回None
        """
        async with semaphore:
            url = f"{self.esi_base_url}/corporations/{corporation_id}"
            try:
                async with session.get(url) as response:
                    if response.status == 404:
                        # 404表示该军团不存在，返回None
                        return None
                    elif response.status == 429:
                        # 429表示请求过多，等待后返回None（让调用者重试）
                        retry_after = int(response.headers.get('Retry-After', 60))
                        print(f"    [!] 请求频率限制，等待 {retry_after} 秒...")
                        await asyncio.sleep(retry_after)
                        return None
                    elif response.status >= 400:
                        print(f"    [-] HTTP错误 {response.status} for corporation {corporation_id}")
                        return None
                    
                    data = await response.json()
                    faction_id = data.get('faction_id', 0)
                    
                    # 如果faction_id存在且不为0，则认为是卫队军团
                    if faction_id and faction_id != 0:
                        return faction_id
                    else:
                        return None
                        
            except asyncio.TimeoutError:
                print(f"    [-] 请求超时: corporation {corporation_id}")
                return None
            except Exception as e:
                print(f"    [-] 请求失败: corporation {corporation_id} - {str(e)}")
                return None
    
    async def fetch_all_corporations_factions(self, corporation_ids: List[int]) -> Dict[int, int]:
        """
        并发获取所有军团的faction_id信息
        
        Args:
            corporation_ids: 军团ID列表
        
        Returns:
            字典，key为corporation_id，value为faction_id（如果不是卫队军团则为None）
        """
        print(f"[+] 开始并发获取 {len(corporation_ids)} 个军团的faction_id信息...")
        print(f"[+] 并发数: {self.max_concurrent}")
        
        connector = aiohttp.TCPConnector(limit=100)
        headers = {"User-Agent": "EveSDE_2.0/1.0"}
        
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=self.request_timeout,
            headers=headers
        ) as session:
            semaphore = asyncio.Semaphore(self.max_concurrent)
            
            # 创建所有任务
            tasks = [
                self.fetch_corporation_faction(session, semaphore, corp_id)
                for corp_id in corporation_ids
            ]
            
            # 并发执行
            results = await asyncio.gather(*tasks)
            
            # 构建结果字典
            faction_map = {}
            militia_count = 0
            
            for corp_id, faction_id in zip(corporation_ids, results):
                if faction_id is not None:
                    faction_map[corp_id] = faction_id
                    militia_count += 1
            
            print(f"[+] 获取完成：{militia_count} 个卫队军团，{len(corporation_ids) - militia_count} 个非卫队军团")
            return faction_map
    
    def create_npc_corporations_table(self, cursor: sqlite3.Cursor):
        """创建 npcCorporations 表"""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS npcCorporations (
                corporation_id INTEGER NOT NULL PRIMARY KEY,
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
                faction_id INTEGER,
                militia_faction INTEGER,
                icon_filename TEXT
            )
        ''')
        
        # 创建索引以优化查询性能
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_npcCorporations_faction_id ON npcCorporations(faction_id)')
    
    def process_corporations_data_to_db(
        self,
        cursor: sqlite3.Cursor,
        lang: str,
        militia_faction_map: Dict[int, int],
        icon_filenames: Dict[int, str]
    ):
        """
        处理 npcCorporations 数据并插入数据库
        
        Args:
            cursor: 数据库游标
            lang: 语言代码
            militia_faction_map: 卫队军团faction_id映射字典
            icon_filenames: 图标文件名映射字典
        """
        self.create_npc_corporations_table(cursor)
        
        # 获取所有军团ID
        corp_ids = list(self.corporations_data.keys())
        
        # 用于存储批量插入的数据
        batch_data = []
        batch_size = 1000  # 每批处理的记录数
        
        for corp_id, corp_info in self.corporations_data.items():
            # 获取当前语言的名称作为主要name
            name_data = corp_info.get('name', {})
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
            
            # 获取描述，如果没有对应语言的就用英文
            description_data = corp_info.get('description', {})
            description = description_data.get(lang, description_data.get('en', ''))
            
            # 获取其他信息
            faction_id = corp_info.get('factionID', 500021)
            
            # 获取卫队军团faction_id（如果存在）
            militia_faction = militia_faction_map.get(corp_id)
            
            # 获取图标文件名
            icon_filename = icon_filenames.get(corp_id, "corporations_default.png")
            
            # 添加到批处理列表
            batch_data.append((
                corp_id,
                name,
                names['de'],
                names['en'],
                names['es'],
                names['fr'],
                names['ja'],
                names['ko'],
                names['ru'],
                names['zh'],
                description,
                faction_id,
                militia_faction,
                icon_filename
            ))
            
            # 当达到批处理大小时执行插入
            if len(batch_data) >= batch_size:
                cursor.executemany('''
                    INSERT OR REPLACE INTO npcCorporations (
                        corporation_id,
                        name,
                        de_name, en_name, es_name, fr_name,
                        ja_name, ko_name, ru_name, zh_name,
                        description,
                        faction_id,
                        militia_faction,
                        icon_filename
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', batch_data)
                batch_data = []  # 清空批处理列表
        
        # 处理剩余的数据
        if batch_data:
            cursor.executemany('''
                INSERT OR REPLACE INTO npcCorporations (
                    corporation_id,
                    name,
                    de_name, en_name, es_name, fr_name,
                    ja_name, ko_name, ru_name, zh_name,
                    description,
                    faction_id,
                    militia_faction,
                    icon_filename
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', batch_data)
        
        # 统计信息
        cursor.execute('SELECT COUNT(*) FROM npcCorporations')
        corporations_count = cursor.fetchone()[0]
        print(f"[+] NPC公司数据处理完成: {corporations_count} 个")
    
    def update_all_databases(self, config) -> bool:
        """
        更新所有语言的数据库
        
        Args:
            config: 配置字典
        
        Returns:
            bool: 处理是否成功
        """
        project_root = Path(__file__).parent.parent
        db_output_path = project_root / config["paths"]["db_output"]
        languages = config.get("languages", ["en"])
        
        # 加载NPC公司数据
        self.load_corporations_data()
        
        if not self.corporations_data:
            print("[x] 没有加载到NPC公司数据，无法继续处理")
            return False
        
        # 获取所有军团ID
        corp_ids = list(self.corporations_data.keys())
        
        # 只枚举一次：并发获取所有军团的faction_id信息
        print("\n[+] 开始获取所有军团的faction_id信息（仅枚举一次）...")
        try:
            militia_faction_map = asyncio.run(self.fetch_all_corporations_factions(corp_ids))
        except Exception as e:
            print(f"[x] 获取faction_id信息失败: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # 下载所有图标（异步）
        print("\n[+] 开始下载所有军团图标...")
        try:
            icon_filenames = asyncio.run(self.download_all_corporation_icons(corp_ids, self.custom_icons_path))
        except Exception as e:
            print(f"[x] 下载图标失败: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        print(f"\n[+] 开始将数据写入到 {len(languages)} 个语言的数据库...")
        
        # 为每种语言的数据库分别插入相同的数据
        for lang in languages:
            db_filename = db_output_path / f'item_db_{lang}.sqlite'
            
            print(f"\n[+] 处理数据库: {db_filename}")
            
            try:
                conn = sqlite3.connect(str(db_filename))
                cursor = conn.cursor()
                
                # 处理NPC公司数据（使用相同的militia_faction_map和icon_filenames）
                self.process_corporations_data_to_db(cursor, lang, militia_faction_map, icon_filenames)
                
                # 提交事务
                conn.commit()
                conn.close()
                
                print(f"[+] 数据库 {lang} 更新完成")
                
            except Exception as e:
                print(f"[x] 处理数据库 {db_filename} 时出错: {e}")
                import traceback
                traceback.print_exc()
                try:
                    conn.close()
                except:
                    pass
                return False
        
        return True


def main(config=None):
    """主函数"""
    print("[+] NPC公司处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = NpcCorporationsProcessor(config)
    success = processor.update_all_databases(config)
    
    if success:
        print("\n[+] NPC公司处理器完成")
    else:
        print("\n[x] NPC公司处理器失败")
    
    return success


if __name__ == "__main__":
    main()
