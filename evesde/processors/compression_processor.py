#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
压缩处理器模块
用于创建无压缩的图标ZIP文件和压缩数据库文件

功能: 
1. 将cache/custom_icons目录中的图片打包到output/icons/icons.zip（无压缩）
2. 移除output/icons中的图片文件
3. 压缩所有数据库文件
"""

from evesde.paths import PROJECT_ROOT
import os
import zipfile
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional


class CompressionProcessor:
    """压缩处理器"""
    
    # 固定的ZIP元数据，确保一致性
    FIXED_METADATA = {
        'date_time': (2024, 1, 1, 0, 0, 0),  # 固定时间戳
        'create_system': 3,  # Unix系统
        'extract_version': 20,  # 固定版本
        'create_version': 20,  # 固定版本
        'external_attr': 0o644 << 16,  # 固定文件权限
    }
    
    def __init__(self, config: Dict[str, Any]):
        """初始化压缩处理器"""
        self.config = config
        self.project_root = PROJECT_ROOT
        self.db_output_path = self.project_root / config["paths"]["db_output"]
        self.icons_output_path = self.project_root / config["paths"]["icons_output"]
        self.custom_icons_path = self.project_root / config["paths"].get("custom_icons", "cache/custom_icons")
        self.languages = config.get("languages", ["en"])
        
        self.output_icons_path = self.project_root / config["paths"]["icons_output"]
        self.output_icons_path.mkdir(parents=True, exist_ok=True)
        self.custom_icons_path.mkdir(parents=True, exist_ok=True)
        
        self.icons_zip_path = self.output_icons_path / "icons.zip"
    
    def _create_consistent_zip(self, zip_path: Path, files_to_add: List[Path], 
                              compression: int = zipfile.ZIP_STORED, 
                              sort_files: bool = True) -> bool:
        """
        创建具有一致元数据的ZIP文件（先写临时文件再替换，避免失败时丢掉旧包）
        """
        try:
            zip_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = zip_path.with_suffix(zip_path.suffix + ".tmp")
            if tmp_path.exists():
                tmp_path.unlink()

            with zipfile.ZipFile(tmp_path, 'w', compression=compression) as zipf:
                file_list = []
                for file_path in files_to_add:
                    file_path = Path(file_path)
                    if file_path.exists() and file_path.is_file():
                        file_list.append(file_path)

                if sort_files:
                    file_list.sort(key=lambda x: x.name.lower())

                if not file_list:
                    print(f"[x] 没有可打包的文件: {zip_path}")
                    tmp_path.unlink(missing_ok=True)
                    return False

                for file_path in file_list:
                    zip_info = zipfile.ZipInfo(filename=file_path.name)
                    zip_info.compress_type = compression
                    for key, value in self.FIXED_METADATA.items():
                        setattr(zip_info, key, value)
                    with open(file_path, 'rb') as f:
                        zipf.writestr(zip_info, f.read())

            tmp_path.replace(zip_path)
            return True

        except Exception as e:
            print(f"[x] 创建ZIP文件失败 {zip_path}: {e}")
            try:
                zip_path.with_suffix(zip_path.suffix + ".tmp").unlink(missing_ok=True)
            except Exception:
                pass
            return False
    
    def create_uncompressed_icons_zip(self):
        """
        创建一个无压缩的ZIP文件，用于存储图标
        将cache/custom_icons目录中的图片打包到output/icons/icons.zip
        使用一致性元数据确保ZIP文件的一致性
        """
        print("[+] 开始创建无压缩图标ZIP文件...")
        
        # 检查cache/custom_icons目录是否存在
        if not self.custom_icons_path.exists():
            print(f"[!] cache/custom_icons目录不存在: {self.custom_icons_path}")
            return False
        
        # 获取所有PNG文件
        png_files = list(self.custom_icons_path.glob("*.png"))
        if not png_files:
            print(f"[!] 在目录 {self.custom_icons_path} 中未找到PNG文件")
            return False
        
        # 复制PNG文件到output/icons目录
        copied_files = []
        for png_file in png_files:
            target_path = self.output_icons_path / png_file.name
            shutil.copy2(png_file, target_path)
            copied_files.append(target_path)
        
        print(f"[+] 已复制 {len(copied_files)} 个PNG文件到output/icons目录")
        
        # 使用一致性ZIP创建方法
        success = self._create_consistent_zip(
            zip_path=self.icons_zip_path,
            files_to_add=copied_files,
            compression=zipfile.ZIP_STORED,
            sort_files=True
        )
        
        if success:
            # 统计ZIP文件中的文件数量
            with zipfile.ZipFile(self.icons_zip_path, 'r') as zipf:
                file_count = len(zipf.namelist())
            
            zip_size = self.icons_zip_path.stat().st_size / (1024 * 1024)  # MB
            print(f"[+] 图标ZIP文件创建完成: {self.icons_zip_path}")
            print(f"[+] 包含 {file_count} 个图标文件，大小: {zip_size:.2f}MB")
            print(f"[+] 使用一致性元数据，确保文件顺序和ZIP结构一致")
            
            return True
        else:
            print(f"[x] 创建图标ZIP文件失败")
            return False
    
    def remove_icons_from_output(self):
        """
        移除output/icons目录中的图片文件（保留ZIP文件）
        """
        print("[+] 开始清理output/icons目录中的图片文件...")
        
        if not self.icons_output_path.exists():
            print(f"[!] output/icons目录不存在: {self.icons_output_path}")
            return False
        
        removed_count = 0
        try:
            # 遍历output/icons目录下的文件
            for file_path in self.icons_output_path.iterdir():
                # 删除PNG文件，但保留ZIP文件
                if file_path.is_file() and file_path.suffix.lower() == ".png":
                    try:
                        file_path.unlink()
                        removed_count += 1
                        # print(f"[+] 删除图片文件: {file_path.name}")
                    except Exception as e:
                        print(f"[!] 删除文件 {file_path.name} 时发生错误: {e}")
            
            print(f"[+] 清理完成，删除了 {removed_count} 个图片文件")
            return True
            
        except Exception as e:
            print(f"[x] 清理图片文件时发生错误: {e}")
            return False


    def cleanup_png_files(self) -> bool:
        """删除output/icons目录中的PNG文件，只保留icons.zip"""
        try:
            print("[+] 清理PNG文件...")
            
            png_files = list(self.output_icons_path.glob("*.png"))
            removed_count = 0
            
            for png_file in png_files:
                try:
                    png_file.unlink()
                    removed_count += 1
                except Exception as e:
                    print(f"[!] 删除文件失败 {png_file}: {e}")
            
            print(f"[+] 已删除 {removed_count} 个PNG文件")
            return True
            
        except Exception as e:
            print(f"[x] 清理PNG文件时发生错误: {e}")
            return False

    def process_compression(self) -> bool:
        """执行图标打包处理流程"""
        print("[+] 开始执行图标打包处理流程...")
        
        success = True
        
        # 1. 创建无压缩的图标ZIP文件
        if not self.create_uncompressed_icons_zip():
            success = False
        
        # 2. 删除PNG文件，只保留icons.zip
        if success:
            if not self.cleanup_png_files():
                success = False
        
        if success:
            print("[+] 图标打包处理流程完成")
        else:
            print("[!] 图标打包处理流程部分失败")
        
        return success


def main(config=None):
    """主函数。最终必须留下 output/icons/icons.zip。"""
    print("[+] 压缩处理器启动")
    
    if config is None:
        import json
        config_path = PROJECT_ROOT / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    processor = CompressionProcessor(config)
    ok = processor.process_compression()
    if not processor.icons_zip_path.exists():
        print(f"[x] icons.zip 未生成: {processor.icons_zip_path}")
        print("\n[+] 压缩处理器完成")
        return False
    if not ok:
        print(f"[!] 压缩流程部分失败，但保留已有 icons.zip: {processor.icons_zip_path}")

    print("\n[+] 压缩处理器完成")
    return True


if __name__ == "__main__":
    main()
