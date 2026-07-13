#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
地图生成器模块
从 SDE JSONL 数据生成地图 JSON 文件

数据来源：
- mapRegions.jsonl: 星域（factionID、名称）
- mapSolarSystems.jsonl: 星系（position2D 坐标、security、regionID）
- mapStargates.jsonl: 星门（星系间连接关系）

输出：
- regions_data.json: 星域列表（id, faction_id, center, relations；不含虫洞星域）
- systems_data.json: 按星域分组的星系（坐标、跳跃关系；不含 x=y=0 虫洞星系）
- neighbors_data.json: 星系邻居关系
"""

from evesde.paths import PROJECT_ROOT
import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any, Set, Tuple
import evesde.processors.jsonl_loader as jsonl_loader


def _is_wormhole_system(sys_data: dict) -> bool:
    """虫洞星系：position2D 的 x、y 均为 0（或缺失视为 0）。"""
    pos = sys_data.get("position2D") or {}
    return float(pos.get("x", 0) or 0) == 0.0 and float(pos.get("y", 0) or 0) == 0.0


class MapGenerator:
    def __init__(self, config: Dict[str, Any]):
        """初始化地图生成器"""
        self.config = config
        self.project_root = PROJECT_ROOT
        self.sde_input_path = self.project_root / config["paths"]["sde_input"]
        self.maps_output_path = self.project_root / config["paths"]["map_output"]

        self.maps_output_path.mkdir(parents=True, exist_ok=True)

        # SDE 数据（过滤后仅保留非虫洞星系 / 非空星域）
        self.map_regions: Dict[int, dict] = {}
        self.map_solar_systems: Dict[int, dict] = {}

    def _load_jsonl_data(self):
        """加载 SDE JSONL，并剔除虫洞星系（x=y=0）及无有效星系的星域。"""
        print("[+] 加载 SDE 数据...")

        regions_file = self.sde_input_path / "mapRegions.jsonl"
        if regions_file.exists():
            regions_list = jsonl_loader.load_jsonl(str(regions_file))
            self.map_regions = {item["_key"]: item for item in regions_list}
            print(f"[+] 加载了 {len(self.map_regions)} 个星域")
        else:
            print(f"[x] 星域文件不存在: {regions_file}")

        systems_file = self.sde_input_path / "mapSolarSystems.jsonl"
        if systems_file.exists():
            systems_list = jsonl_loader.load_jsonl(str(systems_file))
            all_systems = {item["_key"]: item for item in systems_list}
            kept = {
                sid: data
                for sid, data in all_systems.items()
                if not _is_wormhole_system(data)
            }
            skipped = len(all_systems) - len(kept)
            self.map_solar_systems = kept
            print(f"[+] 加载了 {len(all_systems)} 个星系，跳过虫洞 {skipped}，保留 {len(kept)}")
        else:
            print(f"[x] 星系文件不存在: {systems_file}")

        # 仅保留仍有非虫洞星系的星域
        regions_with_systems = {
            data.get("regionID")
            for data in self.map_solar_systems.values()
            if data.get("regionID") is not None
        }
        before = len(self.map_regions)
        self.map_regions = {
            rid: region
            for rid, region in self.map_regions.items()
            if rid in regions_with_systems
        }
        print(
            f"[+] 星域过滤: {before} → {len(self.map_regions)} "
            f"（忽略 {before - len(self.map_regions)} 个虫洞/空星域）"
        )

    def build_system_neighbors(self) -> Dict[int, List[int]]:
        """从 mapStargates.jsonl 构建星系邻居关系（仅非虫洞星系）。"""
        print("[+] 构建星系邻居关系...")

        neighbors: Dict[int, Set[int]] = defaultdict(set)
        stargates_file = self.sde_input_path / "mapStargates.jsonl"

        if not stargates_file.exists():
            print(f"[x] 星门文件不存在: {stargates_file}")
            return {}

        stargates_data = jsonl_loader.load_jsonl(str(stargates_file))
        print(f"[+] 加载了 {len(stargates_data)} 个星门")

        known = self.map_solar_systems
        for stargate in stargates_data:
            source_system = stargate["solarSystemID"]
            dest_system = stargate["destination"]["solarSystemID"]
            if source_system not in known or dest_system not in known:
                continue
            neighbors[source_system].add(dest_system)
            neighbors[dest_system].add(source_system)

        result = {sid: sorted(list(nbrs)) for sid, nbrs in neighbors.items()}
        print(f"[+] 构建了 {len(result)} 个星系的邻居关系")
        return result

    def build_region_connections(self, system_neighbors: Dict[int, List[int]]) -> Dict[int, List[int]]:
        """从星系邻居关系推导星域间连接（跨星域的星门）"""
        print("[+] 推导星域间连接关系...")

        region_connections: Dict[int, Set[int]] = defaultdict(set)
        for system_id, nbrs in system_neighbors.items():
            r1 = self.map_solar_systems.get(system_id, {}).get('regionID')
            if r1 is None:
                continue
            for nbr_id in nbrs:
                r2 = self.map_solar_systems.get(nbr_id, {}).get('regionID')
                if r2 is not None and r2 != r1:
                    region_connections[r1].add(r2)
                    region_connections[r2].add(r1)

        result = {rid: sorted(list(conns)) for rid, conns in region_connections.items()}
        print(f"[+] {len(result)} 个星域有跨星域连接")
        return result

    def compute_coord_scale(self):
        """计算坐标缩放参数，将 SDE position2D（~1e17）缩放到百级范围。
        使用统一的缩放因子保持比例，平移使最小值从 0 开始。"""
        coords = [
            s["position2D"]
            for s in self.map_solar_systems.values()
            if s.get("position2D")
        ]
        if not coords:
            self._coord_offset = {"x": 0.0, "y": 0.0}
            self._coord_scale = 1.0
            return

        min_x = min(c["x"] for c in coords)
        min_y = min(c["y"] for c in coords)
        max_x = max(c["x"] for c in coords)
        max_y = max(c["y"] for c in coords)

        width = max_x - min_x
        height = max_y - min_y
        self._coord_scale = 1000.0 / max(width, height) if max(width, height) > 0 else 1.0
        self._coord_offset = {"x": min_x, "y": min_y}

        print(f"[+] 坐标缩放: scale={self._coord_scale:.2e}, offset=({min_x:.2e}, {min_y:.2e})")

    def scale_coord(self, pos: Dict[str, float]) -> Dict[str, float]:
        """将原始 position2D 坐标缩放到百级范围"""
        return {
            "x": round((pos["x"] - self._coord_offset["x"]) * self._coord_scale, 1),
            "y": round((pos["y"] - self._coord_offset["y"]) * self._coord_scale, 1),
        }

    def compute_region_center(self, region_id: int) -> Dict[str, float]:
        """计算星域中心点（该星域所有星系 position2D 缩放后的平均值）"""
        systems = [
            s
            for s in self.map_solar_systems.values()
            if s.get("regionID") == region_id and s.get("position2D")
        ]
        if not systems:
            return {"x": 0.0, "y": 0.0}
        scaled = [self.scale_coord(s["position2D"]) for s in systems]
        cx = sum(c["x"] for c in scaled) / len(scaled)
        cy = sum(c["y"] for c in scaled) / len(scaled)
        return {"x": round(cx, 1), "y": round(cy, 1)}

    def build_systems_data(self, system_neighbors: Dict[int, List[int]]) -> Tuple[list, dict]:
        """构建星域数据列表和按星域分组的星系数据（已排除虫洞）。"""
        print("[+] 构建星系数据...")

        region_systems: Dict[int, List[int]] = defaultdict(list)
        for sys_id, sys_data in self.map_solar_systems.items():
            rid = sys_data.get("regionID")
            if rid is not None:
                region_systems[rid].append(sys_id)

        regions_data = []
        systems_data = {}

        for region_id in sorted(self.map_regions.keys()):
            region = self.map_regions[region_id]
            sys_ids = region_systems.get(region_id, [])
            if not sys_ids:
                continue

            faction_id = region.get("factionID", 0)
            center = self.compute_region_center(region_id)

            region_conns = self._region_connections.get(region_id, [])
            # 只保留仍被导出的星域之间的连接
            relations = [str(r) for r in region_conns if r in self.map_regions]

            sys_coords = {}
            sys_jumps = {}
            for sys_id in sys_ids:
                sys_data = self.map_solar_systems[sys_id]
                pos2d = sys_data.get("position2D")
                if not pos2d:
                    continue
                sys_coords[str(sys_id)] = self.scale_coord(pos2d)

                nbrs = system_neighbors.get(sys_id, [])
                same_region_nbrs = [
                    str(n)
                    for n in nbrs
                    if self.map_solar_systems.get(n, {}).get("regionID") == region_id
                ]
                if same_region_nbrs:
                    sys_jumps[str(sys_id)] = same_region_nbrs

            if not sys_coords:
                continue

            regions_data.append({
                "region_id": region_id,
                "faction_id": faction_id,
                "center": center,
                "relations": relations,
            })

            systems_data[str(region_id)] = {
                "region_id": region_id,
                "faction_id": faction_id,
                "center": center,
                "relations": relations,
                "systems": sys_coords,
                "jumps": sys_jumps,
            }

        print(f"[+] 处理了 {len(regions_data)} 个星域")
        return regions_data, systems_data

    def save_json(self, data, filename: str):
        """保存 JSON 文件"""
        output_path = self.maps_output_path / filename
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[+] 已保存: {output_path}")

    def run(self) -> bool:
        """运行完整的地图生成流程"""
        try:
            # 1. 加载 SDE 数据
            self._load_jsonl_data()
            if not self.map_solar_systems:
                print("[x] 无星系数据，终止")
                return False

            # 2. 计算坐标缩放参数
            self.compute_coord_scale()

            # 3. 构建星系邻居关系
            system_neighbors = self.build_system_neighbors()

            # 4. 推导星域间连接
            self._region_connections = self.build_region_connections(system_neighbors)

            # 5. 构建星域和星系数据
            regions_data, systems_data = self.build_systems_data(system_neighbors)

            # 6. 保存
            self.save_json(regions_data, "regions_data.json")
            self.save_json(systems_data, "systems_data.json")

            # 6. 保存邻居关系（排序）
            sorted_neighbors = {}
            for sys_id in sorted(system_neighbors.keys()):
                sorted_neighbors[str(sys_id)] = system_neighbors[sys_id]
            self.save_json(sorted_neighbors, "neighbors_data.json")

            print("[+] 地图生成完成！")
            return True

        except Exception as e:
            print(f"[x] 处理过程中出错: {e}")
            import traceback
            traceback.print_exc()
            return False


def main(config=None) -> bool:
    """主函数"""
    print("[+] 地图生成器启动")

    if config is None:
        config_path = PROJECT_ROOT / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

    generator = MapGenerator(config)
    success = generator.run()

    if success:
        print("[+] 地图生成器完成")
    else:
        print("[x] 地图生成器失败")

    return success


if __name__ == "__main__":
    main()
