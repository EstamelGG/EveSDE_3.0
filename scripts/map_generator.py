#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
地图生成器模块
从dotlan下载SVG地图并生成JSON文件
使用JSONL数据源而不是YAML
"""

import asyncio
import aiohttp
import os
import re
import json
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin, urlparse
from typing import Dict, List, Any, Optional
import scripts.jsonl_loader as jsonl_loader

# 从dotlan下载svg地图并生成json文件
# 1. 下载New Eden SVG
# 2. 提取星域链接
# 3. 并发下载所有星域SVG
# 4. 处理星域数据
# 5. 保存到JSON

world_map_layout = "https://evemaps.dotlan.net/svg/New_Eden.svg"

class MapGenerator:
    def __init__(self, config: Dict[str, Any]):
        """初始化地图生成器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.sde_input_path = self.project_root / config["paths"]["sde_input"]
        self.maps_output_path = self.project_root / config["paths"]["map_output"]
        self.cache_path = self.project_root / "cache"
        
        # 确保输出目录存在
        self.maps_output_path.mkdir(parents=True, exist_ok=True)
        self.cache_path.mkdir(parents=True, exist_ok=True)
        
        # 数据存储
        self.regions_data = []
        self.region_links = {}  # 存储星域连接关系
        self.systems_data = {}  # 存储所有星域的系统数据
        
        # 从JSONL加载的数据
        self.map_regions = {}  # region_id -> region_data
        self.map_solar_systems = {}  # system_id -> system_data
        
        # 加载JSONL数据
        self._load_jsonl_data()
        
    def _load_jsonl_data(self):
        """加载JSONL数据"""
        print("[+] 加载JSONL数据...")
        
        # 加载星域数据
        regions_file = self.sde_input_path / "mapRegions.jsonl"
        if regions_file.exists():
            regions_list = jsonl_loader.load_jsonl(str(regions_file))
            self.map_regions = {item['_key']: item for item in regions_list}
            print(f"[+] 加载了 {len(self.map_regions)} 个星域")
        else:
            print(f"[x] 星域文件不存在: {regions_file}")
        
        # 加载星系数据
        systems_file = self.sde_input_path / "mapSolarSystems.jsonl"
        if systems_file.exists():
            systems_list = jsonl_loader.load_jsonl(str(systems_file))
            self.map_solar_systems = {item['_key']: item for item in systems_list}
            print(f"[+] 加载了 {len(self.map_solar_systems)} 个星系")
        else:
            print(f"[x] 星系文件不存在: {systems_file}")
    
    def build_system_neighbors(self) -> Dict[int, List[int]]:
        """从mapStargates.jsonl构建星系邻居关系"""
        print("[+] 构建星系邻居关系...")
        
        neighbors = {}
        stargates_file = self.sde_input_path / "mapStargates.jsonl"
        
        if not stargates_file.exists():
            print(f"[x] 星门文件不存在: {stargates_file}")
            return {}
        
        stargates_data = jsonl_loader.load_jsonl(str(stargates_file))
        print(f"[+] 加载了 {len(stargates_data)} 个星门")
        
        for stargate in stargates_data:
            source_system = stargate["solarSystemID"]
            dest_system = stargate["destination"]["solarSystemID"]
            
            # 添加双向连接
            if source_system not in neighbors:
                neighbors[source_system] = set()
            if dest_system not in neighbors:
                neighbors[dest_system] = set()
                
            neighbors[source_system].add(dest_system)
            neighbors[dest_system].add(source_system)
        
        # 转换为列表格式
        for system_id in neighbors:
            neighbors[system_id] = list(neighbors[system_id])
        
        print(f"[+] 构建了 {len(neighbors)} 个星系的邻居关系")
        return neighbors
    
    async def download_new_eden_svg(self):
        """下载New Eden SVG地图"""
        print("[+] 正在下载New Eden SVG地图...")
        # 创建SSL上下文，忽略证书验证
        ssl_context = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=ssl_context) as session:
            async with session.get(world_map_layout) as response:
                if response.status == 200:
                    content = await response.text()
                    svg_path = self.cache_path / "New_Eden.svg"
                    with open(svg_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    print(f"[+] New Eden SVG下载完成: {svg_path}")
                    return content
                else:
                    raise Exception(f"下载失败: {response.status}")
    
    def extract_region_links(self, svg_content):
        """从SVG内容中提取星域链接"""
        print("[+] 正在提取星域链接...")
        try:
            soup = BeautifulSoup(svg_content, features="xml")
            region_links = {}
            
            # 查找所有href属性包含evemaps.dotlan.net/map/的链接
            links = soup.find_all('a', attrs={'xlink:href': re.compile(r'http://evemaps\.dotlan\.net/map/.*')})
            
            for link in links:
                href = link.get('xlink:href')
                if href:
                    # 提取星域名
                    region_name = href.split('/')[-1]
                    region_links[region_name] = href
                    print(f"[+] 找到星域: {region_name}")
            
            print(f"[+] 共找到 {len(region_links)} 个星域")
            return region_links
        except Exception as e:
            print(f"[x] 解析SVG失败: {e}")
            return {}
    
    async def download_region_svg(self, session, region_name, url):
        """下载单个星域的SVG"""
        try:
            # 修改URL为SVG格式
            svg_url = url.replace('/map/', '/svg/') + '.svg'
            async with session.get(svg_url) as response:
                if response.status == 200:
                    content = await response.text()
                    filename = f"{region_name}.svg"
                    svg_path = self.cache_path / filename
                    with open(svg_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    print(f"[+] 下载完成: {region_name}")
                    return region_name, content
                else:
                    print(f"[x] 下载失败 {region_name}: {response.status}")
                    return region_name, None
        except Exception as e:
            print(f"[x] 下载出错 {region_name}: {e}")
            return region_name, None
    
    async def download_all_regions(self, region_links):
        """并发下载所有星域SVG"""
        print("[+] 正在并发下载星域SVG...")
        # 创建SSL上下文，忽略证书验证，并限制连接数
        connector = aiohttp.TCPConnector(limit=30, ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = []
            for region_name, url in region_links.items():
                task = self.download_region_svg(session, region_name, url)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return {name: content for name, content in results if content is not None}
    
    def extract_coordinates_and_relations(self, svg_content):
        """从SVG中提取坐标和连接关系"""
        try:
            soup = BeautifulSoup(svg_content, features="xml")
            
            # 提取系统坐标
            systems = {}
            sysuse_group = soup.find('g', id='sysuse')
            if sysuse_group:
                for system in sysuse_group.find_all('use'):
                    system_id = system.get('id')
                    if system_id and system_id.startswith('sys'):
                        # 提取系统ID（去掉'sys'前缀）
                        actual_system_id = system_id[3:]
                        x = float(system.get('x', 0))
                        y = float(system.get('y', 0))
                        systems[actual_system_id] = {'x': x, 'y': y}
            
            # 提取连接关系
            relations = {}
            jumps_group = soup.find('g', id='jumps')
            if jumps_group:
                for line in jumps_group.find_all('line'):
                    line_id = line.get('id')
                    if line_id and line_id.startswith('j-'):
                        # 解析连接的系统ID
                        parts = line_id.split('-')
                        if len(parts) >= 3:
                            system1 = parts[1]
                            system2 = parts[2]
                            if system1 not in relations:
                                relations[system1] = []
                            if system2 not in relations[system1]:
                                relations[system1].append(system2)
                            
                            if system2 not in relations:
                                relations[system2] = []
                            if system1 not in relations[system2]:
                                relations[system2].append(system1)
            
            return systems, relations
        except Exception as e:
            print(f"[x] 解析坐标和关系失败: {e}")
            return {}, {}
    
    def extract_region_centers(self, svg_content):
        """从New Eden SVG中提取星域中心点坐标"""
        try:
            soup = BeautifulSoup(svg_content, features="xml")
            region_centers = {}
            
            # 查找sysuse组
            sysuse_group = soup.find('g', id='sysuse')
            if sysuse_group:
                for system in sysuse_group.find_all('use'):
                    system_id = system.get('id')
                    if system_id and system_id.startswith('sys'):
                        # 提取星域ID（去掉'sys'前缀）
                        region_id = system_id[3:]
                        x = float(system.get('x', 0))
                        y = float(system.get('y', 0))
                        region_centers[region_id] = {'x': x, 'y': y}
            
            print(f"[+] 从New Eden SVG中提取到 {len(region_centers)} 个星域的中心点坐标")
            return region_centers
        except Exception as e:
            print(f"[x] 提取星域中心点失败: {e}")
            return {}
    
    def extract_global_relations(self, svg_content):
        """从New Eden SVG中提取全局连接关系"""
        try:
            soup = BeautifulSoup(svg_content, features="xml")
            global_relations = {}
            
            # 查找jumps组
            jumps_group = soup.find('g', id='jumps')
            if jumps_group:
                for line in jumps_group.find_all('line'):
                    line_id = line.get('id')
                    if line_id and line_id.startswith('j-'):
                        # 解析连接的区域ID
                        parts = line_id.split('-')
                        if len(parts) >= 3:
                            region1 = parts[1]
                            region2 = parts[2]
                            
                            # 确保两个区域ID不同
                            if region1 != region2:
                                if region1 not in global_relations:
                                    global_relations[region1] = set()
                                global_relations[region1].add(region2)
                                
                                if region2 not in global_relations:
                                    global_relations[region2] = set()
                                global_relations[region2].add(region1)
            
            print(f"[+] 从New Eden SVG中提取到 {len(global_relations)} 个区域的连接关系")
            return global_relations
        except Exception as e:
            print(f"[x] 提取全局连接关系失败: {e}")
            return {}
    
    def get_region_connections(self, region_id, global_relations):
        """获取指定区域的连接关系"""
        if str(region_id) in global_relations:
            return list(global_relations[str(region_id)])
        return []
    
    def find_region_by_name(self, region_name):
        """根据星域名查找星域数据"""
        # 尝试直接匹配（使用name字段，支持多语言）
        for region_id, region_data in self.map_regions.items():
            name_data = region_data.get('name', {})
            if isinstance(name_data, dict):
                # 多语言名称，检查英文名称
                if name_data.get('en', '').lower() == region_name.lower():
                    return region_id, region_data
            elif isinstance(name_data, str):
                # 字符串名称
                if name_data.lower() == region_name.lower():
                    return region_id, region_data
        
        # 尝试匹配格式化后的名称（删除下划线）
        formatted_name = region_name.replace('_', ' ')
        for region_id, region_data in self.map_regions.items():
            name_data = region_data.get('name', {})
            if isinstance(name_data, dict):
                # 多语言名称，检查英文名称
                if name_data.get('en', '').lower() == formatted_name.lower():
                    return region_id, region_data
            elif isinstance(name_data, str):
                # 字符串名称
                if name_data.lower() == formatted_name.lower():
                    return region_id, region_data
        
        print(f"[!] 警告: 未找到星域 {region_name} 的数据")
        return None, None
    
    def get_systems_in_region(self, region_id):
        """获取指定星域中的所有星系"""
        systems = {}
        for system_id, system_data in self.map_solar_systems.items():
            if system_data.get('regionID') == region_id:
                systems[system_id] = system_data
        return systems
    
    def process_regions_data(self, region_links, region_svgs, new_eden_svg_content):
        """处理所有星域数据"""
        print("[+] 正在处理星域数据...")
        
        # 从New Eden SVG中提取全局连接关系和星域中心点
        print("[+] 正在从New Eden SVG中提取连接关系和星域中心点...")
        global_relations = self.extract_global_relations(new_eden_svg_content)
        region_centers = self.extract_region_centers(new_eden_svg_content)
        
        # 存储区域连接关系
        region_connections = {}
        
        # 统计信息
        processed_count = 0
        skipped_count = 0
        no_systems_count = 0
        center_found_count = 0
        center_not_found_count = 0
        
        for region_name, svg_content in region_svgs.items():
            if not svg_content:
                print(f"[!] 警告: 星域 {region_name} 的SVG内容为空，跳过处理")
                skipped_count += 1
                continue
            
            # 查找星域数据
            region_id, region_data = self.find_region_by_name(region_name)
            if not region_id or not region_data:
                print(f"[x] 错误: 无法找到星域数据: {region_name}")
                skipped_count += 1
                continue
            
            # 获取星域信息
            faction_id = region_data.get('factionID', 0)
            
            # 提取坐标和连接关系
            systems, relations = self.extract_coordinates_and_relations(svg_content)
            
            # 检查系统数量
            if len(systems) == 0:
                print(f"[!] 警告: 星域 {region_name} 未解析到任何系统")
                no_systems_count += 1
            
            # 从New Eden SVG中获取星域中心点坐标
            center = region_centers.get(str(region_id))
            if center:
                center_found_count += 1
                print(f"[+] 找到星域 {region_name} (ID: {region_id}) 的中心点: ({center['x']}, {center['y']})")
            else:
                center_not_found_count += 1
                print(f"[!] 警告: 未找到星域 {region_name} (ID: {region_id}) 的中心点，使用默认坐标")
                # 如果找不到中心点，使用系统坐标的平均值作为备选
                if systems:
                    center_x = sum(sys['x'] for sys in systems.values()) / len(systems)
                    center_y = sum(sys['y'] for sys in systems.values()) / len(systems)
                    center = {'x': center_x, 'y': center_y}
                else:
                    center = {'x': 0, 'y': 0}
            
            # 从全局连接关系中获取该区域的连接
            connected_regions = self.get_region_connections(region_id, global_relations)
            # 按数值大小排序
            connected_regions.sort(key=int)
            
            # 生成单个星域的地图数据
            region_map_data = {
                "region_id": region_id,
                "faction_id": faction_id,
                "center": center,
                "relations": connected_regions,
                "systems": systems,
                "jumps": relations
            }
            
            # 将星域数据存储到systems_data中
            self.systems_data[str(region_id)] = region_map_data
            
            # 为regions_data.json准备数据
            region_data = {
                "region_id": region_id,
                "faction_id": faction_id,
                "center": center,
                "relations": connected_regions
            }
            
            self.regions_data.append(region_data)
            region_connections[region_id] = connected_regions
            processed_count += 1
            print(f"[+] 处理完成: {region_name} (ID: {region_id}, 系统数: {len(systems)}, 连接数: {len(connected_regions)})")
        
        # 输出统计信息
        print(f"\n[+] 处理统计:")
        print(f"    - 成功处理: {processed_count} 个星域")
        print(f"    - 跳过处理: {skipped_count} 个星域")
        print(f"    - 无系统星域: {no_systems_count} 个")
        print(f"    - 找到中心点: {center_found_count} 个星域")
        print(f"    - 未找到中心点: {center_not_found_count} 个星域")
        
        # 验证连接关系的完整性
        self.validate_connections(region_connections)
    
    def validate_connections(self, region_connections):
        """验证连接关系的完整性"""
        print("[+] 正在验证连接关系...")
        for region_id, connections in region_connections.items():
            for connected_region in connections:
                if connected_region in region_connections:
                    if region_id not in region_connections[connected_region]:
                        # 添加反向连接
                        region_connections[connected_region].append(region_id)
                        print(f"[+] 添加反向连接: {connected_region} -> {region_id}")
        
        # 更新regions_data中的relations
        for region_data in self.regions_data:
            region_id = region_data["region_id"]
            if region_id in region_connections:
                # 按数值大小排序
                sorted_relations = sorted(region_connections[region_id], key=int)
                region_data["relations"] = sorted_relations
    
    def save_to_json(self, filename="regions_data.json"):
        """保存数据到JSON文件"""
        output_path = self.maps_output_path / filename
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.regions_data, f, ensure_ascii=False, indent=2)
        print(f"[+] 数据已保存到: {output_path}")
    
    def save_systems_data(self, filename="systems_data.json"):
        """保存所有星域的系统数据到JSON文件"""
        output_path = self.maps_output_path / filename
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.systems_data, f, ensure_ascii=False, indent=2)
        print(f"[+] 所有星域系统数据已保存到: {output_path}")
    
    def save_neighbors_data(self, neighbors_data: Dict[int, List[int]], filename="neighbors_data.json"):
        """保存星系邻居关系数据到JSON文件"""
        output_path = self.maps_output_path / filename
        
        # 按星系ID顺序排序，将整数键转换为字符串键，以便JSON序列化
        # 同时确保内部的邻居ID列表也按顺序排序
        sorted_neighbors = {}
        for system_id in sorted(neighbors_data.keys()):
            # 对邻居ID列表也进行排序
            sorted_neighbor_list = sorted(neighbors_data[system_id])
            sorted_neighbors[str(system_id)] = sorted_neighbor_list
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(sorted_neighbors, f, ensure_ascii=False, indent=2)
        print(f"[+] 星系邻居关系数据已保存到: {output_path} (按星系ID和邻居ID排序)")
    
    async def run(self):
        """运行完整的地图生成流程"""
        try:
            # 1. 下载New Eden SVG
            svg_content = await self.download_new_eden_svg()
            
            # 2. 提取星域链接
            region_links = self.extract_region_links(svg_content)
            
            # 3. 并发下载所有星域SVG
            region_svgs = await self.download_all_regions(region_links)
            
            # 4. 处理星域数据
            self.process_regions_data(region_links, region_svgs, svg_content)
            
            # 5. 构建星系邻居关系
            neighbors_data = self.build_system_neighbors()
            
            # 6. 保存到JSON
            self.save_to_json()
            self.save_systems_data()
            self.save_neighbors_data(neighbors_data)
            
            print("[+] 地图生成完成！")
            return True
            
        except Exception as e:
            print(f"[x] 处理过程中出错: {e}")
            return False


def main(config=None):
    """主函数"""
    print("[+] 地图生成器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建地图生成器并执行
    generator = MapGenerator(config)
    
    # 运行异步任务
    success = asyncio.run(generator.run())
    
    if success:
        print("[+] 地图生成器完成")
    else:
        print("[x] 地图生成器失败")
    
    return success


if __name__ == "__main__":
    main()
