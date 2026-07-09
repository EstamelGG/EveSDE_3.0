#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
压缩处理器模块
用于创建无压缩的图标ZIP文件和压缩数据库文件

功能: 
1. 将custom_icons目录中的图片打包到output/icons/icons.zip（无压缩）
2. 移除output/icons中的图片文件
3. 压缩所有数据库文件
"""

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
        self.project_root = Path(__file__).parent.parent
        self.db_output_path = self.project_root / config["paths"]["db_output"]
        self.icons_output_path = self.project_root / config["paths"]["icons_output"]
        self.custom_icons_path = self.project_root / "custom_icons"
        self.languages = config.get("languages", ["en"])
        
        # 新的输出目录结构
        self.output_icons_path = self.project_root / "output_icons"
        self.output_icons_path.mkdir(exist_ok=True)
        
        # 图标ZIP文件路径
        self.icons_zip_path = self.output_icons_path / "icons.zip"
    
    def _create_consistent_zip(self, zip_path: Path, files_to_add: List[Path], 
                              compression: int = zipfile.ZIP_STORED, 
                              sort_files: bool = True) -> bool:
        """
        创建具有一致元数据的ZIP文件
        
        Args:
            zip_path: 输出ZIP文件路径
            files_to_add: 要添加到ZIP的文件列表
            compression: 压缩类型
            sort_files: 是否按文件名排序
        
        Returns:
            bool: 是否创建成功
        """
        try:
            # 确保输出目录存在
            zip_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 如果ZIP文件已存在，先删除
            if zip_path.exists():
                zip_path.unlink()
            
            with zipfile.ZipFile(zip_path, 'w', compression=compression) as zipf:
                # 处理文件列表
                file_list = []
                for file_path in files_to_add:
                    file_path = Path(file_path)
                    if file_path.exists() and file_path.is_file():
                        file_list.append(file_path)
                
                # 按文件名排序（如果需要）
                if sort_files:
                    file_list.sort(key=lambda x: x.name.lower())
                
                # 添加文件到ZIP
                for file_path in file_list:
                    # 创建ZIP信息对象
                    zip_info = zipfile.ZipInfo(filename=file_path.name)
                    zip_info.compress_type = compression
                    
                    # 设置固定元数据
                    for key, value in self.FIXED_METADATA.items():
                        setattr(zip_info, key, value)
                    
                    # 读取文件内容
                    with open(file_path, 'rb') as f:
                        file_data = f.read()
                    
                    # 添加到ZIP
                    zipf.writestr(zip_info, file_data)
            
            return True
            
        except Exception as e:
            print(f"[x] 创建ZIP文件失败 {zip_path}: {e}")
            return False
    
    def create_uncompressed_icons_zip(self):
        """
        创建一个无压缩的ZIP文件，用于存储图标
        将custom_icons目录中的图片打包到output/icons/icons.zip
        使用一致性元数据确保ZIP文件的一致性
        """
        print("[+] 开始创建无压缩图标ZIP文件...")
        
        # 检查custom_icons目录是否存在
        if not self.custom_icons_path.exists():
            print(f"[!] custom_icons目录不存在: {self.custom_icons_path}")
            return False
        
        # 获取所有PNG文件
        png_files = list(self.custom_icons_path.glob("*.png"))
        if not png_files:
            print(f"[!] 在目录 {self.custom_icons_path} 中未找到PNG文件")
            return False
        
        # 复制PNG文件到output_icons目录
        copied_files = []
        for png_file in png_files:
            target_path = self.output_icons_path / png_file.name
            shutil.copy2(png_file, target_path)
            copied_files.append(target_path)
        
        print(f"[+] 已复制 {len(copied_files)} 个PNG文件到output_icons目录")
        
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
        """删除output_icons目录中的PNG文件，只保留icons.zip"""
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
    """主函数"""
    print("[+] 压缩处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = CompressionProcessor(config)
    processor.process_compression()
    
    print("\n[+] 压缩处理器完成")


if __name__ == "__main__":
    main()
