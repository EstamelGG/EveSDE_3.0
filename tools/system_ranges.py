#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
星系跳数计算工具
计算从指定星系到指定星域内所有星系的跳数，并按跳数范围分类保存
"""

import json
from pathlib import Path
from collections import deque
from typing import Dict, List, Set, Tuple
import sys

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.jsonl_loader import load_jsonl


def calculate_system_ranges(
    start_system_id: int,
    target_region_id: int,
    sde_input_path: Path
) -> Dict[str, List[int]]:
    """
    计算从起始星系到目标星域内所有星系的跳数，并按跳数范围分类
    
    Args:
        start_system_id: 起始星系ID (例如: 30000142)
        target_region_id: 目标星域ID (例如: 10000002)
        sde_input_path: SDE JSONL文件路径
        
    Returns:
        Dict[str, List[int]]: 按跳数范围分类的星系ID列表字典
            键: "<=1", "<=2", "<=3", "<=4", "<=5", "<=10", "<=20", "<=30", "<=40", "all"
            值: 该跳数范围内的星系ID列表
    """
    print(f"[+] 开始计算从星系 {start_system_id} 到星域 {target_region_id} 的跳数...")
    
    # 1. 加载星系邻居关系
    print("[+] 加载星系邻居关系...")
    neighbors = _load_neighbors(sde_input_path)
    if not neighbors:
        print("[x] 无法加载星系邻居关系")
        return {}
    print(f"[+] 加载了 {len(neighbors)} 个星系的邻居关系")
    
    # 2. 构建星系到星域的映射
    print("[+] 构建星系到星域的映射...")
    system_to_region = _build_system_to_region_mapping(sde_input_path)
    if not system_to_region:
        print("[x] 无法构建星系到星域的映射")
        return {}
    print(f"[+] 构建了 {len(system_to_region)} 个星系的星域映射")
    
    # 3. 获取目标星域内的所有星系
    target_systems = {
        system_id for system_id, region_id in system_to_region.items()
        if region_id == target_region_id
    }
    print(f"[+] 目标星域 {target_region_id} 包含 {len(target_systems)} 个星系")
    
    # 4. 检查起始星系是否存在
    if start_system_id not in neighbors:
        print(f"[x] 起始星系 {start_system_id} 不存在或没有邻居关系")
        return {}
    
    # 5. 使用BFS计算跳数
    print("[+] 使用BFS算法计算跳数...")
    jump_distances = _calculate_jump_distances(start_system_id, neighbors, target_systems)
    
    # 6. 按跳数范围分类
    print("[+] 按跳数范围分类...")
    result = _categorize_by_jumps(jump_distances, target_systems)
    
    # 打印统计信息
    print("\n[+] 跳数统计:")
    for key, systems in result.items():
        if key != "all":
            print(f"    {key}跳: {len(systems)} 个星系")
    print(f"    星域内所有星系: {len(result['all'])} 个")
    
    return result


def _load_neighbors(sde_input_path: Path) -> Dict[int, List[int]]:
    """
    从mapStargates.jsonl加载星系邻居关系
    
    Returns:
        Dict[int, List[int]]: 星系ID -> 邻居星系ID列表
    """
    neighbors = {}
    stargates_file = sde_input_path / "mapStargates.jsonl"
    
    if not stargates_file.exists():
        print(f"[x] 星门文件不存在: {stargates_file}")
        return {}
    
    stargates_data = load_jsonl(str(stargates_file))
    print(f"[+] 加载了 {len(stargates_data)} 个星门")
    
    for stargate in stargates_data:
        source_system = stargate.get("solarSystemID")
        destination = stargate.get("destination", {})
        dest_system = destination.get("solarSystemID") if isinstance(destination, dict) else None
        
        if source_system and dest_system:
            # 添加双向连接
            if source_system not in neighbors:
                neighbors[source_system] = []
            if dest_system not in neighbors:
                neighbors[dest_system] = []
            
            # 避免重复添加
            if dest_system not in neighbors[source_system]:
                neighbors[source_system].append(dest_system)
            if source_system not in neighbors[dest_system]:
                neighbors[dest_system].append(source_system)
    
    return neighbors


def _build_system_to_region_mapping(sde_input_path: Path) -> Dict[int, int]:
    """
    构建星系ID到星域ID的映射
    
    Returns:
        Dict[int, int]: 星系ID -> 星域ID
    """
    system_to_region = {}
    
    # 加载星座数据
    constellations_file = sde_input_path / "mapConstellations.jsonl"
    if not constellations_file.exists():
        print(f"[x] 星座文件不存在: {constellations_file}")
        return {}
    
    constellations_list = load_jsonl(str(constellations_file))
    constellation_to_region = {
        item['_key']: item.get('regionID')
        for item in constellations_list
        if item.get('regionID')
    }
    print(f"[+] 加载了 {len(constellation_to_region)} 个星座的星域映射")
    
    # 加载星系数据
    solar_systems_file = sde_input_path / "mapSolarSystems.jsonl"
    if not solar_systems_file.exists():
        print(f"[x] 星系文件不存在: {solar_systems_file}")
        return {}
    
    solar_systems_list = load_jsonl(str(solar_systems_file))
    for system in solar_systems_list:
        system_id = system.get('_key')
        constellation_id = system.get('constellationID')
        
        if system_id and constellation_id and constellation_id in constellation_to_region:
            system_to_region[system_id] = constellation_to_region[constellation_id]
    
    return system_to_region


def _calculate_jump_distances(
    start_system_id: int,
    neighbors: Dict[int, List[int]],
    target_systems: Set[int]
) -> Dict[int, int]:
    """
    使用BFS算法计算从起始星系到目标星域内所有星系的最短跳数
    
    Args:
        start_system_id: 起始星系ID
        neighbors: 星系邻居关系字典
        target_systems: 目标星域内的星系集合
        
    Returns:
        Dict[int, int]: 星系ID -> 跳数（只包含目标星域内的星系）
    """
    jump_distances = {}
    
    # BFS队列: (system_id, jumps)
    queue = deque([(start_system_id, 0)])
    visited = {start_system_id}
    
    # 如果起始星系在目标星域内，记录它
    if start_system_id in target_systems:
        jump_distances[start_system_id] = 0
    
    while queue:
        current_system, jumps = queue.popleft()
        
        # 获取当前星系的邻居
        current_neighbors = neighbors.get(current_system, [])
        
        for neighbor in current_neighbors:
            if neighbor not in visited:
                visited.add(neighbor)
                next_jumps = jumps + 1
                
                # 如果邻居在目标星域内，记录跳数
                if neighbor in target_systems:
                    # 只记录最短路径（BFS保证第一次到达就是最短路径）
                    if neighbor not in jump_distances:
                        jump_distances[neighbor] = next_jumps
                
                # 继续BFS搜索
                queue.append((neighbor, next_jumps))
    
    return jump_distances


def _categorize_by_jumps(
    jump_distances: Dict[int, int],
    all_target_systems: Set[int]
) -> Dict[str, List[int]]:
    """
    按跳数范围分类星系
    
    Args:
        jump_distances: 星系ID -> 跳数字典
        all_target_systems: 目标星域内的所有星系集合
        
    Returns:
        Dict[str, List[int]]: 按跳数范围分类的星系ID列表
    """
    result = {
        "<=1": [],
        "<=2": [],
        "<=3": [],
        "<=4": [],
        "<=5": [],
        "<=10": [],
        "<=20": [],
        "<=30": [],
        "<=40": [],
        "all": list(all_target_systems)
    }
    
    # 按跳数分类
    for system_id, jumps in jump_distances.items():
        if jumps <= 1:
            result["<=1"].append(system_id)
        if jumps <= 2:
            result["<=2"].append(system_id)
        if jumps <= 3:
            result["<=3"].append(system_id)
        if jumps <= 4:
            result["<=4"].append(system_id)
        if jumps <= 5:
            result["<=5"].append(system_id)
        if jumps <= 10:
            result["<=10"].append(system_id)
        if jumps <= 20:
            result["<=20"].append(system_id)
        if jumps <= 30:
            result["<=30"].append(system_id)
        if jumps <= 40:
            result["<=40"].append(system_id)
    
    # 对每个列表进行排序
    for key in result:
        result[key].sort()
    
    return result


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="计算从指定星系到指定星域内所有星系的跳数")
    parser.add_argument("--start-system", type=int, default=30000142,
                       help="起始星系ID (默认: 30000142)")
    parser.add_argument("--target-region", type=int, default=10000002,
                       help="目标星域ID (默认: 10000002)")
    parser.add_argument("--sde-path", type=str, default=None,
                       help="SDE JSONL文件路径 (默认: 从config.json读取)")
    parser.add_argument("--output", type=str, default=None,
                       help="输出JSON文件路径 (默认: system_ranges_<start>_<region>.json)")
    
    args = parser.parse_args()
    
    # 确定SDE路径
    if args.sde_path:
        sde_input_path = Path(args.sde_path)
    else:
        # 从config.json读取
        config_path = project_root / "config.json"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            sde_input_path = project_root / config["paths"]["sde_input"]
        else:
            sde_input_path = project_root / "sde_jsonl"
    
    if not sde_input_path.exists():
        print(f"[x] SDE路径不存在: {sde_input_path}")
        return
    
    # 计算跳数
    result = calculate_system_ranges(
        args.start_system,
        args.target_region,
        sde_input_path
    )
    
    if not result:
        print("[x] 计算失败")
        return
    
    # 确定输出路径
    if args.output:
        output_path = Path(args.output)
    else:
        output_dir = project_root / "output_sde"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"system_ranges_{args.start_system}_{args.target_region}.json"
    
    # 保存结果
    print(f"\n[+] 保存结果到: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print("[+] 完成！")


if __name__ == "__main__":
    main()

