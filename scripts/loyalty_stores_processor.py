#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
忠诚点商店数据处理器模块
用于从ESI API获取所有NPC军团的LP商店数据并存储到数据库

数据来源：
- 军团列表: https://esi.evetech.net/corporations/npccorps
- LP商店数据: https://esi.evetech.net/loyalty/stores/{corporation_id}/offers
"""

import json
import sqlite3
import time
import asyncio
import aiohttp
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


class LoyaltyStoresProcessor:
    """忠诚点商店数据处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化LP商店处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.db_output_path = self.project_root / config["paths"]["db_output"]
        self.languages = config.get("languages", ["en", "zh"])
        
        # ESI API基础URL
        self.esi_base_url = "https://esi.evetech.net"
        self.npccorps_url = f"{self.esi_base_url}/corporations/npccorps"
        
        # 请求配置
        self.max_retries = 5
        self.request_timeout = aiohttp.ClientTimeout(total=30)
        self.retry_delay = 1.0
        self.max_concurrent = 20  # 最大并发数
        
        # 统计数据
        self.stats = {
            "total_corporations": 0,
            "processed_corporations": 0,
            "failed_corporations": 0,
            "total_offers": 0,
            "total_required_items": 0
        }
    
    async def fetch_with_retry(
        self, 
        session: aiohttp.ClientSession,
        url: str, 
        max_retries: Optional[int] = None
    ) -> Optional[Any]:
        """
        带重试机制的异步API请求
        
        Args:
            session: aiohttp会话
            url: 请求的URL
            max_retries: 最大重试次数，默认使用self.max_retries
        
        Returns:
            响应数据（JSON），失败返回None
        """
        if max_retries is None:
            max_retries = self.max_retries
        
        for attempt in range(max_retries):
            try:
                async with session.get(url) as response:
                    if response.status == 404:
                        # 404表示该军团没有LP商店，这是正常的
                        return None
                    elif response.status == 429:
                        # 429表示请求过多，需要等待
                        retry_after = int(response.headers.get('Retry-After', 60))
                        if attempt < max_retries - 1:
                            print(f"    [!] 请求频率限制，等待 {retry_after} 秒...")
                            await asyncio.sleep(retry_after)
                            continue
                        else:
                            print(f"    [x] 请求频率限制，已达到最大重试次数")
                            return None
                    elif response.status >= 400:
                        if attempt < max_retries - 1:
                            wait_time = self.retry_delay * (attempt + 1)
                            print(f"    [-] HTTP错误 {response.status}，{wait_time:.1f}秒后重试 ({attempt+1}/{max_retries})")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            print(f"    [x] HTTP错误 {response.status}，已达到最大重试次数")
                            return None
                    
                    # 成功响应
                    return await response.json()
                    
            except asyncio.TimeoutError:
                if attempt < max_retries - 1:
                    wait_time = self.retry_delay * (attempt + 1)
                    print(f"    [-] 请求超时，{wait_time:.1f}秒后重试 ({attempt+1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"    [x] 请求超时，已达到最大重试次数")
                    return None
                    
            except aiohttp.ClientError as e:
                if attempt < max_retries - 1:
                    wait_time = self.retry_delay * (attempt + 1)
                    print(f"    [-] 请求失败: {str(e)}，{wait_time:.1f}秒后重试 ({attempt+1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"    [x] 请求失败: {str(e)}，已达到最大重试次数")
                    return None
        
        return None
    
    async def fetch_npc_corporations(self, session: aiohttp.ClientSession) -> List[int]:
        """
        获取所有NPC军团ID列表（异步）
        
        Args:
            session: aiohttp会话
        
        Returns:
            NPC军团ID列表
        """
        print(f"[+] 获取NPC军团列表: {self.npccorps_url}")
        
        corporations = await self.fetch_with_retry(session, self.npccorps_url)
        
        if corporations is None:
            print("[x] 获取NPC军团列表失败")
            return []
        
        if not isinstance(corporations, list):
            print("[x] NPC军团列表格式错误")
            return []
        
        print(f"[+] 获取到 {len(corporations)} 个NPC军团")
        self.stats["total_corporations"] = len(corporations)
        return corporations
    
    async def fetch_loyalty_offers(
        self, 
        session: aiohttp.ClientSession,
        corporation_id: int
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取指定军团的LP商店数据（异步）
        
        Args:
            session: aiohttp会话
            corporation_id: 军团ID
        
        Returns:
            LP商店offer列表，失败返回None
        """
        url = f"{self.esi_base_url}/loyalty/stores/{corporation_id}/offers"
        return await self.fetch_with_retry(session, url)
    
    def create_tables(self, cursor: sqlite3.Cursor):
        """
        创建数据库表结构
        
        Args:
            cursor: 数据库游标
        """
        # 1. 创建忠诚点商店商品需求表（每个offer_id对应的需求物品，以offer_id为索引）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS loyalty_offer_requirements (
                offer_id INTEGER NOT NULL,
                required_type_id INTEGER NOT NULL,
                required_quantity INTEGER NOT NULL,
                PRIMARY KEY (offer_id, required_type_id)
            )
        ''')
        
        # 2. 创建忠诚点商店商品输出表（每个offer_id对应的输出，以offer_id为索引）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS loyalty_offer_outputs (
                offer_id INTEGER PRIMARY KEY,
                type_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                isk_cost INTEGER NOT NULL DEFAULT 0,
                lp_cost INTEGER NOT NULL DEFAULT 0,
                ak_cost INTEGER NOT NULL DEFAULT 0
            )
        ''')
        
        # 3. 创建忠诚点商店表（每个军团提供的offer_id，以corporation_id+offer_id为联合主键）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS loyalty_offers (
                corporation_id INTEGER NOT NULL,
                offer_id INTEGER NOT NULL,
                PRIMARY KEY (corporation_id, offer_id)
            )
        ''')
        
        # 创建索引
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_loyalty_offers_corporation_id 
            ON loyalty_offers(corporation_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_loyalty_offer_outputs_type_id 
            ON loyalty_offer_outputs(type_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_loyalty_offer_outputs_lp_cost 
            ON loyalty_offer_outputs(lp_cost)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_loyalty_offer_requirements_offer_id 
            ON loyalty_offer_requirements(offer_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_loyalty_offer_requirements_type_id 
            ON loyalty_offer_requirements(required_type_id)
        ''')
        
        
        print("[+] 数据库表结构创建完成")
    
    def clear_existing_data(self, cursor: sqlite3.Cursor):
        """
        清空现有数据
        
        Args:
            cursor: 数据库游标
        """
        print("[+] 清空现有数据...")
        cursor.execute('DELETE FROM loyalty_offers')
        cursor.execute('DELETE FROM loyalty_offer_outputs')
        cursor.execute('DELETE FROM loyalty_offer_requirements')
        print("[+] 数据清空完成")
    
    def process_corporation_data(
        self, 
        corporation_id: int,
        offers: Optional[List[Dict[str, Any]]]
    ) -> Optional[Tuple[List, List]]:
        """
        处理单个军团的数据（不涉及数据库操作）
        
        Args:
            corporation_id: 军团ID
            offers: LP商店offer列表
        
        Returns:
            (offers_batch, outputs_batch, requirements_batch) 元组，如果没有数据返回None
            - offers_batch: 军团和offer的关系
            - outputs_batch: offer的输出信息
            - requirements_batch: offer的需求物品
        """
        # 如果返回None，可能是404（没有LP商店）或其他错误
        if offers is None:
            # 404是正常的，不是所有军团都有LP商店
            return None
        
        if not isinstance(offers, list) or len(offers) == 0:
            # 空列表表示该军团没有LP商店
            return None
        
        # 批量准备数据
        offers_batch = []  # 表3：军团和offer的关系
        outputs_batch = []  # 表2：offer的输出
        requirements_batch = []  # 表1：offer的需求
        
        for offer in offers:
            offer_id = offer.get('offer_id')
            type_id = offer.get('type_id')
            quantity = offer.get('quantity', 1)
            isk_cost = offer.get('isk_cost', 0)
            lp_cost = offer.get('lp_cost', 0)
            ak_cost = offer.get('ak_cost', 0)
            required_items = offer.get('required_items', [])
            
            # 准备offer数据（仅存储军团和offer的关系）
            offers_batch.append((
                corporation_id,
                offer_id
            ))
            
            # 准备offer信息数据（每个offer只存储一次，包含产出和价格）
            outputs_batch.append((
                offer_id,
                type_id,
                quantity,
                isk_cost,
                lp_cost,
                ak_cost
            ))
            
            # 准备requirements数据（表1：每个offer_id对应的需求物品）
            for req_item in required_items:
                required_type_id = req_item.get('type_id')
                required_quantity = req_item.get('quantity', 1)
                requirements_batch.append((
                    offer_id,
                    required_type_id,
                    required_quantity
                ))
        
        return (offers_batch, outputs_batch, requirements_batch)
    
    def save_corporation_data(
        self,
        cursor: sqlite3.Cursor,
        corporation_id: int,
        offers_batch: List,
        outputs_batch: List,
        requirements_batch: List
    ):
        """
        将处理好的数据保存到数据库
        
        Args:
            cursor: 数据库游标
            corporation_id: 军团ID
            offers_batch: 表3数据列表（corporation_id和offer_id的关系）
            outputs_batch: 表2数据列表（offer的输出信息，包含产出和价格）
            requirements_batch: 表1数据列表（offer的需求物品）
        """
        # 批量插入表2：offer输出（每个offer只插入一次，使用INSERT OR IGNORE避免重复）
        if outputs_batch:
            cursor.executemany('''
                INSERT OR IGNORE INTO loyalty_offer_outputs
                (offer_id, type_id, quantity, isk_cost, lp_cost, ak_cost)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', outputs_batch)
        
        # 批量插入表1：offer需求物品（每个offer只插入一次，使用INSERT OR IGNORE避免重复）
        if requirements_batch:
            cursor.executemany('''
                INSERT OR IGNORE INTO loyalty_offer_requirements
                (offer_id, required_type_id, required_quantity)
                VALUES (?, ?, ?)
            ''', requirements_batch)
            self.stats["total_required_items"] += len(requirements_batch)
        
        # 批量插入表3：军团和offer的关系
        if offers_batch:
            cursor.executemany('''
                INSERT OR REPLACE INTO loyalty_offers
                (corporation_id, offer_id)
                VALUES (?, ?)
            ''', offers_batch)
            self.stats["total_offers"] += len(offers_batch)
    
    async def process_single_corporation(
        self,
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        corporation_id: int,
        idx: int,
        total: int
    ) -> Tuple[int, Optional[List[Dict[str, Any]]]]:
        """
        异步处理单个军团的LP商店数据
        
        Args:
            session: aiohttp会话
            semaphore: 并发控制信号量
            corporation_id: 军团ID
            idx: 当前索引
            total: 总数
        
        Returns:
            (corporation_id, offers) 元组
        """
        async with semaphore:
            try:
                offers = await self.fetch_loyalty_offers(session, corporation_id)
                return (corporation_id, offers)
            except Exception as e:
                print(f"    [!] 处理军团 {corporation_id} 时出错: {e}")
                return (corporation_id, None)
    
    async def process_all_corporations_async(self) -> List[Tuple[int, Optional[List[Dict[str, Any]]]]]:
        """
        异步处理所有NPC军团的LP商店数据
        
        Returns:
            所有军团的数据列表，格式为 (corporation_id, offers)
        """
        print("[+] 开始获取所有NPC军团...")
        
        # 创建aiohttp会话
        connector = aiohttp.TCPConnector(limit=100)
        headers = {"User-Agent": "EveSDE_2.0/1.0"}
        
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=self.request_timeout,
            headers=headers
        ) as session:
            # 获取NPC军团列表
            corporations = await self.fetch_npc_corporations(session)
            
            if not corporations:
                print("[x] 没有获取到NPC军团列表，无法继续处理")
                return []
            
            print(f"[+] 开始异步处理 {len(corporations)} 个军团的LP商店数据...")
            print(f"[+] 并发数: {self.max_concurrent}")
            print(f"[+] 注意：不是所有军团都有LP商店，404错误是正常的")
            
            start_time = time.time()
            
            # 创建信号量控制并发数
            semaphore = asyncio.Semaphore(self.max_concurrent)
            
            # 创建所有任务
            tasks = [
                self.process_single_corporation(
                    session, semaphore, corp_id, idx + 1, len(corporations)
                )
                for idx, corp_id in enumerate(corporations)
            ]
            
            # 使用asyncio.as_completed显示进度
            results = []
            completed = 0
            
            for coro in asyncio.as_completed(tasks):
                result = await coro
                results.append(result)
                completed += 1
                
                corporation_id, offers = result
                if offers is not None and len(offers) > 0:
                    print(f"[{completed}/{len(corporations)}] 军团 {corporation_id}: ✓ 成功 ({len(offers)} 个offers)")
                    self.stats["processed_corporations"] += 1
                else:
                    print(f"[{completed}/{len(corporations)}] 军团 {corporation_id}: ✗ 跳过（无LP商店）")
                    self.stats["failed_corporations"] += 1
            
            elapsed_time = time.time() - start_time
            print(f"\n[+] 异步处理完成，耗时: {elapsed_time:.2f} 秒")
            print(f"[+] 平均速度: {len(corporations) / elapsed_time:.2f} 个军团/秒")
            
            return results
    
    def fetch_all_corporations_data(self) -> List[Tuple[int, Optional[List[Dict[str, Any]]]]]:
        """
        获取所有NPC军团的LP商店数据（只枚举一次）
        
        Returns:
            所有军团的数据列表，格式为 (corporation_id, offers)
        """
        # 运行异步处理
        results = asyncio.run(self.process_all_corporations_async())
        return results
    
    def calculate_statistics(self, results: List[Tuple[int, Optional[List[Dict[str, Any]]]]]):
        """
        计算统计数据（不更新self.stats，只返回统计结果）
        
        Args:
            results: 所有军团的数据列表
        
        Returns:
            统计信息字典
        """
        stats = {
            "total_corporations": len(results),
            "processed_corporations": 0,
            "failed_corporations": 0,
            "total_offers": 0,
            "total_required_items": 0
        }
        
        for corporation_id, offers in results:
            if offers is not None and len(offers) > 0:
                stats["processed_corporations"] += 1
                stats["total_offers"] += len(offers)
                # 计算required_items总数
                for offer in offers:
                    required_items = offer.get('required_items', [])
                    stats["total_required_items"] += len(required_items)
            else:
                stats["failed_corporations"] += 1
        
        return stats
    
    def save_all_data_to_database(
        self,
        cursor: sqlite3.Cursor,
        results: List[Tuple[int, Optional[List[Dict[str, Any]]]]]
    ):
        """
        将获取到的所有数据保存到数据库
        
        Args:
            cursor: 数据库游标
            results: 所有军团的数据列表
        """
        print("[+] 开始保存数据到数据库...")
        save_start_time = time.time()
        
        for corporation_id, offers in results:
            data = self.process_corporation_data(corporation_id, offers)
            if data:
                offers_batch, outputs_batch, requirements_batch = data
                self.save_corporation_data(
                    cursor, corporation_id, offers_batch, outputs_batch, requirements_batch
                )
        
        save_elapsed_time = time.time() - save_start_time
        print(f"[+] 数据保存完成，耗时: {save_elapsed_time:.2f} 秒")
    
    def update_all_databases(self, config: Dict[str, Any]) -> bool:
        """
        更新所有语言的数据库
        
        Args:
            config: 配置字典
        
        Returns:
            bool: 处理是否成功
        """
        print("[+] 开始处理LP商店数据...")
        print(f"[+] 支持语言: {', '.join(self.languages)}")
        
        # 确保数据库目录存在
        self.db_output_path.mkdir(parents=True, exist_ok=True)
        
        # 只枚举一次所有LP商店数据
        print("\n[+] 开始获取所有NPC军团的LP商店数据（仅枚举一次）...")
        try:
            results = self.fetch_all_corporations_data()
        except Exception as e:
            print(f"[x] 获取LP商店数据失败: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        if not results:
            print("[x] 没有获取到任何LP商店数据，无法继续处理")
            return False
        
        # 计算并输出统计数据
        stats = self.calculate_statistics(results)
        print(f"\n[+] 数据获取完成，统计信息：")
        print(f"    - 总军团数: {stats['total_corporations']}")
        print(f"    - 有LP商店的军团: {stats['processed_corporations']}")
        print(f"    - 无LP商店的军团: {stats['failed_corporations']}")
        print(f"    - 总offer数: {stats['total_offers']}")
        print(f"    - 总required_items数: {stats['total_required_items']}")
        
        print(f"\n[+] 开始将数据写入到 {len(self.languages)} 个语言的数据库...")
        
        # 为每种语言的数据库分别插入相同的数据
        for lang in self.languages:
            db_filename = self.db_output_path / f'item_db_{lang}.sqlite'
            
            print(f"\n[+] 处理数据库: {db_filename}")
            
            try:
                conn = sqlite3.connect(str(db_filename))
                cursor = conn.cursor()
                
                # 创建表结构
                self.create_tables(cursor)
                
                # 清空现有数据
                self.clear_existing_data(cursor)
                
                # 将数据保存到数据库
                self.save_all_data_to_database(cursor, results)
                
                # 提交事务
                conn.commit()
                conn.close()
                
                print(f"[+] 数据库 {lang} 更新完成")
                
            except Exception as e:
                print(f"[x] 处理数据库 {db_filename} 时出错: {e}")
                import traceback
                traceback.print_exc()
                # 关闭连接（如果存在）
                try:
                    conn.close()
                except:
                    pass
                # 返回失败
                return False
        
        return True


def main(config=None):
    """主函数"""
    print("[+] LP商店数据处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = LoyaltyStoresProcessor(config)
    success = processor.update_all_databases(config)
    
    if success:
        print("\n[+] LP商店数据处理器完成")
    else:
        print("\n[x] LP商店数据处理器失败")
    
    return success


if __name__ == "__main__":
    main()

