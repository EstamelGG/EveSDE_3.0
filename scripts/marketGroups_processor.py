#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
市场分组数据处理器模块
用于处理marketGroups数据并写入数据库

功能: 处理市场分组数据，创建marketGroups表
"""

import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Dict, Any, List, Tuple, Set
import asyncio
import aiohttp
import scripts.icon_finder as icon_finder

# 自定义组名称附加文本
CUSTOM_GROUP_EXPAND = {
    '2396': '(R4)',
    '2397': '(R8)',
    '2398': '(R16)',
    '2400': '(R32)',
    '2401': '(R64)',
    '1333': '(P0)',
    '1334': '(P1)',
    '1335': '(P2)',
    '1336': '(P3)',
    '1337': '(P4)',
}

# 特殊图标映射
SPECIAL_ICON_MAP = {
    20966: "res:/ui/texture/icons/19_128_1.png",
    20959: "res:/ui/texture/icons/19_128_4.png",
    20967: "res:/ui/texture/icons/19_128_3.png",
    20968: "res:/ui/texture/icons/19_128_2.png",
}


class MarketGroupsProcessor:
    """市场分组数据处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化marketGroups处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.sde_jsonl_path = self.project_root / config["paths"]["sde_jsonl"]
        self.db_output_path = self.project_root / config["paths"]["db_output"]
        self.languages = config.get("languages", ["en"])
        self.custom_icons_path = self.project_root / "custom_icons"
        
        # 确保自定义图标目录存在
        self.custom_icons_path.mkdir(parents=True, exist_ok=True)
        
        # 初始化图标查找器（用于下载res:格式的图标）
        self.icon_finder = icon_finder.IconFinder(config)
        
        # 图标下载缓存
        self.icon_download_cache = {}  # icon_id -> filename
    
    def read_market_groups_jsonl(self) -> Dict[str, Any]:
        """
        读取marketGroups JSONL文件
        """
        jsonl_file = self.sde_jsonl_path / "marketGroups.jsonl"
        
        if not jsonl_file.exists():
            print(f"[x] 找不到marketGroups JSONL文件: {jsonl_file}")
            return {}
        
        print(f"[+] 读取marketGroups JSONL文件: {jsonl_file}")
        
        market_groups_data = {}
        try:
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        # 新版本使用_key作为group_id
                        group_id = data['_key']
                        market_groups_data[group_id] = data
                    except json.JSONDecodeError as e:
                        print(f"[!] 第{line_num}行JSON解析错误: {e}")
                        continue
                    except KeyError as e:
                        print(f"[!] 第{line_num}行缺少必要字段: {e}")
                        continue
            
            print(f"[+] 成功读取 {len(market_groups_data)} 个marketGroups记录")
            return market_groups_data
            
        except Exception as e:
            print(f"[x] 读取marketGroups JSONL文件时出错: {e}")
            return {}
    
    def create_market_groups_table(self, cursor: sqlite3.Cursor):
        """
        创建marketGroups表
        完全按照old版本的数据库结构
        """
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS marketGroups (
            group_id INTEGER NOT NULL PRIMARY KEY,
            name TEXT,
            icon_name TEXT,
            parentgroup_id INTEGER,
            show BOOLEAN DEFAULT 1
        )
        ''')
        print("[+] 创建marketGroups表")
    
    def build_group_hierarchies(self, cursor: sqlite3.Cursor) -> Tuple[Dict[int, List[int]], Dict[int, Dict[str, Any]]]:
        """
        构建组层级关系和组信息的缓存
        """
        # 获取所有组的层级关系
        cursor.execute('SELECT group_id, parentgroup_id, icon_name FROM marketGroups')
        results = cursor.fetchall()
        
        # 构建父子关系映射
        children_map = defaultdict(list)
        group_info = {}
        for group_id, parent_id, icon_name in results:
            if parent_id is not None:
                children_map[parent_id].append(group_id)
            group_info[group_id] = {'icon_name': icon_name}
        
        return children_map, group_info
    
    def build_group_items_map(self, cursor: sqlite3.Cursor) -> Dict[int, int]:
        """
        构建组与物品数量的映射
        """
        cursor.execute('''
            SELECT marketGroupID, COUNT(*) as count 
            FROM types 
            WHERE marketGroupID IS NOT NULL 
            GROUP BY marketGroupID
        ''')
        return dict(cursor.fetchall())
    
    def get_icon_for_group(self, group_id: int, children_map: Dict[int, List[int]], 
                          group_info: Dict[int, Dict[str, Any]], visited: Set[int] = None) -> str:
        """
        使用缓存的数据递归查找组的图标
        """
        if visited is None:
            visited = set()
        
        if group_id in visited:
            return None
        visited.add(group_id)
        
        # 检查当前组的图标
        current_icon = group_info[group_id]['icon_name']
        if current_icon:
            return current_icon
        
        # 检查子组的图标
        for child_id in children_map[group_id]:
            child_icon = self.get_icon_for_group(child_id, children_map, group_info, visited)
            if child_icon:
                return child_icon
        
        return None
    
    def check_group_has_items_cached(self, group_id: int, children_map: Dict[int, List[int]], 
                                   items_map: Dict[int, int], visited: Set[int] = None) -> bool:
        """
        使用缓存的数据递归检查组是否包含物品
        """
        if visited is None:
            visited = set()
        
        if group_id in visited:
            return False
        visited.add(group_id)
        
        # 检查当前组是否有物品
        if items_map.get(group_id, 0) > 0:
            return True
        
        # 检查子组
        for child_id in children_map[group_id]:
            if self.check_group_has_items_cached(child_id, children_map, items_map, visited):
                return True
        
        return False
    
    async def download_icon_async(self, session: aiohttp.ClientSession, icon_id: int) -> Tuple[int, str]:
        """
        异步下载单个图标
        
        Args:
            session: aiohttp会话
            icon_id: 图标ID
            
        Returns:
            Tuple[int, str]: (icon_id, filename) 或 (icon_id, None)
        """
        icon_filename = f"market_icon_{icon_id}.png"
        icon_path = self.custom_icons_path / icon_filename
        
        # 如果图标已存在，直接返回
        if icon_path.exists():
            return icon_id, icon_filename
        
        try:
            # 使用icon_finder获取图标URL
            icon_info = self.icon_finder.get_icon_info(icon_id)
            if not icon_info or not icon_info.get('url'):
                return icon_id, None
            
            # 异步下载图标
            async with session.get(icon_info['url']) as response:
                if response.status == 200:
                    content = await response.read()
                    with open(icon_path, 'wb') as f:
                        f.write(content)
                    print(f"[+] 下载市场分组图标: {icon_id} -> {icon_filename}")
                    return icon_id, icon_filename
                else:
                    print(f"[!] 下载图标失败 {icon_id}: HTTP {response.status}")
                    return icon_id, None
                    
        except Exception as e:
            print(f"[!] 下载图标失败 {icon_id}: {e}")
            return icon_id, None
    
    async def download_icons_batch(self, icon_ids: List[int], max_concurrent: int = 10) -> Dict[int, str]:
        """
        批量异步下载图标（限制并发数）
        
        Args:
            icon_ids: 图标ID列表
            max_concurrent: 最大并发数，默认10
            
        Returns:
            Dict[int, str]: icon_id -> filename 映射
        """
        if not icon_ids:
            return {}
        
        print(f"[+] 开始批量下载 {len(icon_ids)} 个市场分组图标（最大并发数: {max_concurrent}）...")
        
        # 创建aiohttp会话
        timeout = aiohttp.ClientTimeout(total=30)
        connector = aiohttp.TCPConnector(limit=max_concurrent, limit_per_host=max_concurrent)
        
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            # 创建信号量来限制并发数
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def download_with_semaphore(icon_id: int):
                async with semaphore:
                    return await self.download_icon_async(session, icon_id)
            
            # 创建下载任务
            tasks = [download_with_semaphore(icon_id) for icon_id in icon_ids]
            
            # 并发执行所有下载任务
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理结果
            icon_map = {}
            for result in results:
                if isinstance(result, Exception):
                    print(f"[!] 下载任务异常: {result}")
                    continue
                
                icon_id, filename = result
                if filename:
                    icon_map[icon_id] = filename
            
            print(f"[+] 批量下载完成，成功下载 {len(icon_map)}/{len(icon_ids)} 个图标")
            return icon_map
    
    def download_res_icon(self, res_path: str, icon_id: int) -> str:
        """
        从网络下载res:格式的图标
        
        Args:
            res_path: res:格式的图标路径
            icon_id: 图标ID，用于生成文件名
            
        Returns:
            str: 下载后的图标文件名
        """
        icon_filename = f"market_icon_{icon_id}.png"
        icon_path = self.custom_icons_path / icon_filename
        
        # 如果图标已存在，直接返回
        if icon_path.exists():
            return icon_filename
        
        try:
            # 使用icon_finder下载图标
            content = self.icon_finder._get_icon_file_content(res_path)
            
            if content:
                # 保存到custom_icons目录
                with open(icon_path, 'wb') as f:
                    f.write(content)
                print(f"[+] 下载市场分组图标: {icon_id} -> {icon_filename}")
                return icon_filename
            else:
                print(f"[!] 无法下载图标: {res_path}")
                return None
                
        except Exception as e:
            print(f"[!] 下载图标失败 {res_path}: {e}")
            return None
    
    def get_icon_name(self, cursor: sqlite3.Cursor, group_id: int, icon_id: int) -> str:
        """
        获取组的图标名称
        """
        # 检查特殊图标映射（res:格式）
        if icon_id in SPECIAL_ICON_MAP:
            res_path = SPECIAL_ICON_MAP[icon_id]
            if res_path.startswith("res:/"):
                # 从网络下载res:格式的图标
                downloaded_icon = self.download_res_icon(res_path, icon_id)
                return downloaded_icon if downloaded_icon else None
            else:
                # 兼容旧的硬编码文件名
                return res_path
        
        # 从缓存中获取图标
        if icon_id in self.icon_download_cache:
            return self.icon_download_cache[icon_id]
        
        # 检查文件是否已存在
        if icon_id is not None:
            icon_filename = f"market_icon_{icon_id}.png"
            icon_path = self.custom_icons_path / icon_filename
            if icon_path.exists():
                self.icon_download_cache[icon_id] = icon_filename
                return icon_filename
        
        # 如果缓存和本地都找不到，从网络下载（根据resfile中的路径）
        if icon_id is not None:
            try:
                # 使用icon_finder获取图标内容
                icon_content = self.icon_finder.get_icon_file_content(icon_id)
                if icon_content:
                    # 保存到本地
                    icon_filename = f"market_icon_{icon_id}.png"
                    icon_path = self.custom_icons_path / icon_filename
                    with open(icon_path, 'wb') as f:
                        f.write(icon_content)
                    
                    # 更新缓存
                    self.icon_download_cache[icon_id] = icon_filename
                    print(f"[+] 从网络下载市场分组图标: {icon_id} -> {icon_filename}")
                    return icon_filename
                else:
                    print(f"[!] 无法从网络获取图标: {icon_id}")
            except Exception as e:
                print(f"[!] 下载图标失败 {icon_id}: {e}")
        
        return None
    
    def process_market_groups_to_db(self, market_groups_data: Dict[str, Any], cursor: sqlite3.Cursor, lang: str):
        """
        处理marketGroups数据并写入数据库
        完全按照old版本的逻辑
        """
        self.create_market_groups_table(cursor)
        
        # 清空现有数据
        cursor.execute('DELETE FROM marketGroups')

        # 收集需要下载的图标ID
        icon_ids_to_download = set()
        for group_id, group_data in market_groups_data.items():
            icon_id = group_data.get('iconID')
            if icon_id and icon_id not in SPECIAL_ICON_MAP:
                icon_ids_to_download.add(icon_id)
        
        # 批量下载图标
        if icon_ids_to_download:
            print(f"[+] 准备批量下载 {len(icon_ids_to_download)} 个图标...")
            try:
                # 运行异步下载
                icon_map = asyncio.run(self.download_icons_batch(list(icon_ids_to_download)))
                # 更新缓存
                self.icon_download_cache.update(icon_map)
            except Exception as e:
                print(f"[!] 批量下载图标失败: {e}")

        # 处理每个市场组
        insert_data = []
        for group_id, group_data in market_groups_data.items():
            # 获取当前语言的名称和描述，如果为空则使用英语
            name = group_data.get('name', {}).get(lang, '')
            if not name:  # 如果当前语言的name为空，尝试获取英语的name
                name = group_data.get('name', {}).get('en', '')
            if str(group_id) in CUSTOM_GROUP_EXPAND.keys():
                name += CUSTOM_GROUP_EXPAND[str(group_id)]

            # 获取图标ID并查找对应的图标文件名
            icon_id = group_data.get('iconID')
            icon_name = self.get_icon_name(cursor, group_id, icon_id)
            
            # 获取父组ID
            parentgroup_id = group_data.get('parentGroupID')
            
            # 收集插入数据
            insert_data.append((group_id, name, icon_name, parentgroup_id))
        
        # 批量插入数据
        cursor.executemany('''
            INSERT OR REPLACE INTO marketGroups 
            (group_id, name, icon_name, parentgroup_id)
            VALUES (?, ?, ?, ?)
        ''', insert_data)
        
        # 构建缓存数据
        children_map, group_info = self.build_group_hierarchies(cursor)
        items_map = self.build_group_items_map(cursor)
        
        # 后处理：处理图标继承
        updates_icon = []
        for group_id in group_info:
            if not group_info[group_id]['icon_name']:
                icon_name = self.get_icon_for_group(group_id, children_map, group_info)
                if not icon_name:
                    icon_name = 'category_default.png'  # 默认图标
                updates_icon.append((icon_name, group_id))
        
        # 批量更新图标
        if updates_icon:
            cursor.executemany('''
                UPDATE marketGroups 
                SET icon_name = ? 
                WHERE group_id = ?
            ''', updates_icon)
        
        # 后处理：检查显示状态
        updates_show = []
        for group_id in group_info:
            should_show = self.check_group_has_items_cached(group_id, children_map, items_map)
            updates_show.append((should_show, group_id))
        
        # 批量更新显示状态
        cursor.executemany('''
            UPDATE marketGroups 
            SET show = ? 
            WHERE group_id = ?
        ''', updates_show)
        
        print(f"[+] 已处理 {len(market_groups_data)} 个市场分组，语言: {lang}")
    
    def process_market_groups_for_language(self, language: str) -> bool:
        """
        为指定语言处理marketGroups数据
        """
        print(f"[+] 开始处理marketGroups数据，语言: {language}")
        
        # 读取marketGroups数据
        market_groups_data = self.read_market_groups_jsonl()
        if not market_groups_data:
            print("[x] 无法读取marketGroups数据")
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
            self.process_market_groups_to_db(market_groups_data, cursor, language)
            
            # 提交更改
            conn.commit()
            print(f"[+] marketGroups数据处理完成，语言: {language}")
            return True
            
        except Exception as e:
            print(f"[x] 处理marketGroups数据时出错: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()
    
    def process_all_languages(self) -> bool:
        """
        为所有语言处理marketGroups数据
        """
        print("[+] 开始处理marketGroups数据")
        
        success_count = 0
        for language in self.languages:
            if self.process_market_groups_for_language(language):
                success_count += 1
        
        print(f"[+] marketGroups数据处理完成，成功处理 {success_count}/{len(self.languages)} 个语言")
        return success_count > 0


def main(config=None):
    """主函数"""
    print("[+] 市场分组数据处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = MarketGroupsProcessor(config)
    processor.process_all_languages()
    
    print("\n[+] 市场分组数据处理器完成")


if __name__ == "__main__":
    main()
