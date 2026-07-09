#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图标构建处理器模块
使用eve_icon_builder生成EVE物品图标包

功能:
1. 调用eve_icon_builder生成图标包
2. 解压图标包到icons_input目录
3. 统计处理结果
"""

import sys
import zipfile
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
import time


class IconBuilderProcessor:
    """图标构建处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化图标构建处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.eve_icon_builder_path = self.project_root / "eve_icon_builder"
        self.icons_input_path = self.project_root / config["paths"]["icons_input"]
        self.icons_zip_dir = self.project_root / "icons_zip"
        
        # 确保目录存在
        self.icons_input_path.mkdir(parents=True, exist_ok=True)
        self.icons_zip_dir.mkdir(exist_ok=True)
        
        # 输出文件路径
        self.output_zip = self.icons_zip_dir / "icons_generated.zip"
        
        # 统计信息
        self.stats = {
            'build_start_time': None,
            'build_duration': 0,
            'added_icons': 0,
            'removed_icons': 0,
            'total_icons': 0,
            'success': False
        }
    
    def check_eve_icon_builder(self) -> bool:
        """检查eve_icon_builder是否存在"""
        print("[+] 检查eve_icon_builder...")
        
        if not self.eve_icon_builder_path.exists():
            print("[x] eve_icon_builder目录不存在")
            return False
        
        main_py = self.eve_icon_builder_path / "main.py"
        if not main_py.exists():
            print("[x] eve_icon_builder/main.py不存在")
            return False
        
        # 检查必要的模块文件
        required_files = [
            "cache.py",
            "sde.py", 
            "icons.py"
        ]
        
        for file_name in required_files:
            file_path = self.eve_icon_builder_path / file_name
            if not file_path.exists():
                print(f"[x] eve_icon_builder/{file_name}不存在")
                return False
        
        print("[+] eve_icon_builder检查通过")
        return True
    
    def build_icons_with_eve_builder(self) -> bool:
        """使用eve_icon_builder构造图标"""
        try:
            print("[+] 开始使用eve_icon_builder构造图标...")
            self.stats['build_start_time'] = time.time()
            
            # 将eve_icon_builder添加到sys.path
            sys.path.insert(0, str(self.eve_icon_builder_path))
            
            # 导入必要的模块
            from cache import CacheDownloader, CacheError
            from sde import update_sde, read_types, read_group_categories, read_icons, read_graphics, read_skin_materials
            from icons import IconBuildData, build_icon_export, IconError
            
            print("[+] 初始化缓存...")
            cache = CacheDownloader(
                self.eve_icon_builder_path / "cache",
                "EVE-SDE-Builder/1.0",
                use_macos_build=False
            )
            
            print("[+] 加载SDE数据...")
            sde = update_sde(silent_mode=False)
            
            icon_build_data = IconBuildData(
                types=read_types(sde, silent_mode=False),
                group_categories=read_group_categories(sde, silent_mode=False),
                icon_files=read_icons(sde, silent_mode=False),
                graphics_folders=read_graphics(sde, silent_mode=False),
                skin_materials=read_skin_materials(sde, silent_mode=False)
            )
            
            sde.close()
            
            print("[+] 开始构造图标...")
            added, removed = build_icon_export(
                output_mode='service_bundle',
                skip_output_if_fresh=False,
                data=icon_build_data,
                cache=cache,
                icon_dir=self.eve_icon_builder_path / "icons",
                force_rebuild=False,
                silent_mode=False,
                log_file=None,
                show_progress=True,
                skip_skins=True,  # 跳过SKIN图标以加快速度
                test_type_id=None,
                out=str(self.output_zip)
            )
            
            # 记录统计信息
            self.stats['added_icons'] = added
            self.stats['removed_icons'] = removed
            self.stats['total_icons'] = added + removed
            self.stats['build_duration'] = time.time() - self.stats['build_start_time']
            
            print(f"[+] 图标构造完成: {added} 新增, {removed} 删除")
            print(f"[+] 构造耗时: {self.stats['build_duration']:.1f} 秒")
            
            # 清理不必要的缓存
            cache.purge(['sde.zip', 'checksum.txt'])
            
            # 从sys.path中移除
            sys.path.remove(str(self.eve_icon_builder_path))
            
            if not self.output_zip.exists():
                print("[x] 图标包生成失败")
                return False
            
            print(f"[+] 图标包已生成: {self.output_zip}")
            self.stats['success'] = True
            return True
            
        except (CacheError, IconError) as e:
            print(f"[x] eve_icon_builder错误: {e}")
            return False
        except Exception as e:
            print(f"[x] 构造图标时出错: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # 确保从sys.path中移除
            if str(self.eve_icon_builder_path) in sys.path:
                sys.path.remove(str(self.eve_icon_builder_path))
    
    def extract_generated_icons(self) -> bool:
        """解压生成的图标包"""
        try:
            print("[+] 解压图标包...")
            
            if not self.output_zip.exists():
                print("[x] 图标包不存在")
                return False
            
            # 清空icons_input目录
            if self.icons_input_path.exists():
                shutil.rmtree(self.icons_input_path)
            self.icons_input_path.mkdir(parents=True, exist_ok=True)
            
            # 解压图标包
            with zipfile.ZipFile(self.output_zip, 'r') as zip_ref:
                zip_ref.extractall(self.icons_input_path)
            
            print(f"[+] 图标包解压完成: {self.icons_input_path}")
            
            # 统计解压后的文件
            png_files = list(self.icons_input_path.glob("**/*.png"))
            json_files = list(self.icons_input_path.glob("**/*.json"))
            
            print(f"[+] 解压统计:")
            print(f"    - PNG图标文件: {len(png_files)} 个")
            print(f"    - JSON元数据文件: {len(json_files)} 个")
            
            # 查找service_metadata.json
            metadata_files = list(self.icons_input_path.glob("**/service_metadata.json"))
            if metadata_files:
                print(f"[+] 找到service_metadata.json: {metadata_files[0]}")
            else:
                print("[!] 未找到service_metadata.json文件")
            
            return True
            
        except Exception as e:
            print(f"[x] 解压失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def process_icon_building(self) -> bool:
        """执行图标构建处理流程"""
        print("[+] 开始执行图标构建处理流程...")
        
        success = True
        
        # 1. 检查eve_icon_builder
        if not self.check_eve_icon_builder():
            success = False
        
        # 2. 构建图标
        if success:
            if not self.build_icons_with_eve_builder():
                success = False
        
        # 3. 解压图标包
        if success:
            if not self.extract_generated_icons():
                success = False
        
        if success:
            print("[+] 图标构建处理流程完成")
            self.print_statistics()
        else:
            print("[!] 图标构建处理流程失败")
        
        return success
    
    def print_statistics(self):
        """打印统计信息"""
        print("\n" + "=" * 50)
        print("图标构建统计信息")
        print("=" * 50)
        print(f"构建耗时: {self.stats['build_duration']:.1f} 秒")
        print(f"新增图标: {self.stats['added_icons']} 个")
        print(f"删除图标: {self.stats['removed_icons']} 个")
        print(f"总处理图标: {self.stats['total_icons']} 个")
        print(f"输出文件: {self.output_zip}")
        print(f"解压目录: {self.icons_input_path}")
        print("=" * 50)


def main(config: Optional[Dict[str, Any]] = None) -> bool:
    """主函数"""
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    processor = IconBuilderProcessor(config)
    return processor.process_icon_building()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
