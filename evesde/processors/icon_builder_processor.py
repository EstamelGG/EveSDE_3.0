#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图标构建处理器模块
使用 evesde.icon_builder 生成 EVE 物品图标包

功能:
1. 调用 icon_builder 生成图标包
2. 解压图标包到 icons_input 目录
3. 统计处理结果
"""

from evesde.paths import PROJECT_ROOT
import zipfile
import shutil
from pathlib import Path
from typing import Dict, Any
import time

from evesde.icon_builder.cache import CacheError
from evesde.icon_builder.sde import (
    update_sde,
    read_types,
    read_group_categories,
    read_icons,
    read_graphics,
    read_skin_materials,
)
from evesde.icon_builder.icons import IconBuildData, build_icon_export, IconError


class IconBuilderProcessor:
    """图标构建处理器"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.project_root = PROJECT_ROOT
        self.icons_input_path = self.project_root / config["paths"]["icons_input"]
        self.icons_input_path.mkdir(parents=True, exist_ok=True)
        self.icon_builder_dir = Path(__file__).resolve().parent.parent / "icon_builder"
        self.output_zip = self.project_root / config["paths"]["icons_output"] / "icons.zip"
        self.output_zip.parent.mkdir(parents=True, exist_ok=True)
        self.stats = {
            "build_start_time": None,
            "build_duration": 0,
            "added_icons": 0,
            "removed_icons": 0,
            "total_icons": 0,
            "success": False,
        }

    def build_icons_with_eve_builder(self) -> bool:
        try:
            print("[+] 开始使用 icon_builder 构造图标...")
            self.stats["build_start_time"] = time.time()

            print("[+] 初始化缓存...")
            cache = self.config.get("eve_client")
            if cache is None:
                from evesde.utils.eve_client import EveClient
                cache = EveClient.from_tq(self.project_root / self.config["paths"]["client_cache"])

            print("[+] 加载SDE数据...")
            build_number = self.config.get("sde_build_number")
            sde_zip_dir = self.project_root / self.config["paths"]["sde_zip"]
            source_zip = None
            if build_number:
                source_zip = sde_zip_dir / f"eve-online-static-data-{build_number}-jsonl.zip"
            sde = update_sde(
                silent_mode=False,
                build_number=build_number,
                source_zip=source_zip,
            )

            icon_build_data = IconBuildData(
                types=read_types(sde, silent_mode=False),
                group_categories=read_group_categories(sde, silent_mode=False),
                icon_files=read_icons(sde, silent_mode=False),
                graphics_folders=read_graphics(sde, silent_mode=False),
                skin_materials=read_skin_materials(sde, silent_mode=False),
            )
            sde.close()

            print("[+] 开始构造图标...")
            added, removed = build_icon_export(
                output_mode="iec",
                skip_output_if_fresh=False,
                data=icon_build_data,
                cache=cache,
                icon_dir=self.icon_builder_dir / "icons",
                force_rebuild=False,
                silent_mode=False,
                log_file=None,
                show_progress=True,
                skip_skins=True,
                test_type_id=None,
                out=str(self.output_zip),
            )

            self.stats["added_icons"] = added
            self.stats["removed_icons"] = removed
            self.stats["total_icons"] = added + removed
            self.stats["build_duration"] = time.time() - self.stats["build_start_time"]

            print(f"[+] 图标构造完成: {added} 新增, {removed} 删除")
            print(f"[+] 构造耗时: {self.stats['build_duration']:.1f} 秒")

            cache.purge(["sde.zip", "checksum.txt"])

            if not self.output_zip.exists():
                print("[x] 图标包生成失败")
                return False

            print(f"[+] 图标包已生成: {self.output_zip}")
            self.stats["success"] = True
            return True

        except (CacheError, IconError) as e:
            print(f"[x] icon_builder 错误: {e}")
            return False
        except Exception as e:
            print(f"[x] 构造图标时出错: {e}")
            import traceback
            traceback.print_exc()
            return False

    def extract_generated_icons(self) -> bool:
        try:
            print("[+] 解压图标包...")
            if not self.output_zip.exists():
                print("[x] 图标包不存在")
                return False

            if self.icons_input_path.exists():
                shutil.rmtree(self.icons_input_path)
            self.icons_input_path.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(self.output_zip, "r") as zip_ref:
                zip_ref.extractall(self.icons_input_path)

            png_count = len(list(self.icons_input_path.glob("*.png")))
            print(f"[+] 已解压 {png_count} 个图标到 {self.icons_input_path}")
            return True
        except Exception as e:
            print(f"[x] 解压图标包失败: {e}")
            return False

    def process(self) -> bool:
        print("=" * 50)
        print("图标构建处理")
        print("=" * 50)
        if not self.build_icons_with_eve_builder():
            return False
        if not self.extract_generated_icons():
            return False
        print("[+] 图标构建处理完成")
        return True


def main(config: Dict[str, Any]) -> bool:
    return IconBuilderProcessor(config).process()


if __name__ == "__main__":
    import json
    config_path = PROJECT_ROOT / "config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    main(cfg)
