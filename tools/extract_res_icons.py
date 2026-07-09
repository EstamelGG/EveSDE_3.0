#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EVE客户端资源图标提取工具
从macOS客户端的ResFiles目录中枚举全部资源文件，
检测图片文件并复制到output/res_icons目录，添加.png后缀
"""

import os
import shutil
import platform
from pathlib import Path
from typing import Optional, Tuple


# 图片文件类型的魔数（文件头）
IMAGE_SIGNATURES = {
    # PNG: 89 50 4E 47 0D 0A 1A 0A
    b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A': 'png',
    # JPEG: FF D8 FF
    b'\xFF\xD8\xFF': 'jpeg',
    # GIF: 47 49 46 38 (GIF8)
    b'\x47\x49\x46\x38': 'gif',
    # BMP: 42 4D (BM)
    b'\x42\x4D': 'bmp',
    # WebP: RIFF...WEBP
    b'\x52\x49\x46\x46': 'webp',  # 需要进一步检查
    # TIFF: 49 49 2A 00 (little-endian) 或 4D 4D 00 2A (big-endian)
    b'\x49\x49\x2A\x00': 'tiff',
    b'\x4D\x4D\x00\x2A': 'tiff',
}


def is_image_file(file_path: Path) -> Tuple[bool, Optional[str]]:
    """
    通过文件头检测文件是否为图片
    
    Args:
        file_path: 文件路径
        
    Returns:
        (是否为图片, 图片类型)
    """
    try:
        with open(file_path, 'rb') as f:
            # 读取前16字节用于检测
            header = f.read(16)
            
            if len(header) < 3:
                return False, None
            
            # 检查PNG
            if header.startswith(b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A'):
                return True, 'png'
            
            # 检查JPEG
            if header.startswith(b'\xFF\xD8\xFF'):
                return True, 'jpeg'
            
            # 检查GIF
            if header.startswith(b'\x47\x49\x46\x38'):
                return True, 'gif'
            
            # 检查BMP
            if header.startswith(b'\x42\x4D'):
                return True, 'bmp'
            
            # 检查WebP (RIFF...WEBP)
            if header.startswith(b'\x52\x49\x46\x46'):
                # 需要检查是否包含WEBP
                f.seek(0)
                webp_header = f.read(12)
                if b'WEBP' in webp_header:
                    return True, 'webp'
            
            # 检查TIFF
            if header.startswith(b'\x49\x49\x2A\x00') or header.startswith(b'\x4D\x4D\x00\x2A'):
                return True, 'tiff'
            
            return False, None
            
    except Exception as e:
        print(f"[!] 检测文件失败 {file_path}: {e}")
        return False, None


def get_eve_resfiles_path() -> Optional[Path]:
    """获取EVE客户端ResFiles目录路径"""
    system = platform.system().lower()
    
    if system == "darwin":  # macOS
        base_path = Path.home() / "Library/Application Support/EVE Online/SharedCache/ResFiles"
        return base_path
    else:
        print(f"[x] 当前系统不支持: {system}")
        return None


def extract_res_icons(resfiles_dir: Path, output_dir: Path):
    """
    从ResFiles目录提取所有图片文件
    
    Args:
        resfiles_dir: ResFiles目录路径
        output_dir: 输出目录路径
    """
    if not resfiles_dir.exists():
        print(f"[x] ResFiles目录不存在: {resfiles_dir}")
        return
    
    # 确保输出目录存在
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"[+] 开始扫描资源文件: {resfiles_dir}")
    print(f"[+] 输出目录: {output_dir}")
    
    total_files = 0
    image_files = 0
    copied_files = 0
    skipped_files = 0
    
    # 递归遍历所有文件
    for root, dirs, files in os.walk(resfiles_dir):
        for filename in files:
            total_files += 1
            file_path = Path(root) / filename
            
            # 检测是否为图片
            is_image, image_type = is_image_file(file_path)
            
            if not is_image:
                continue
            
            image_files += 1
            
            # 生成输出文件名（使用相对路径结构，避免文件名冲突）
            relative_path = file_path.relative_to(resfiles_dir)
            # 将路径分隔符替换为下划线，并添加.png后缀
            safe_name = str(relative_path).replace(os.sep, '_').replace('/', '_').replace('\\', '_')
            output_filename = f"{safe_name}.png"
            output_path = output_dir / output_filename
            
            # 如果文件已存在，跳过
            if output_path.exists():
                skipped_files += 1
                if image_files % 100 == 0:
                    print(f"[+] 已处理 {image_files} 个图片文件...")
                continue
            
            try:
                # 复制文件并添加.png后缀
                shutil.copy2(file_path, output_path)
                copied_files += 1
                
                if copied_files % 100 == 0:
                    print(f"[+] 已复制 {copied_files} 个图片文件...")
                    
            except Exception as e:
                print(f"[!] 复制文件失败 {file_path} -> {output_path}: {e}")
    
    print("\n[+] 提取完成!")
    print(f"    - 总文件数: {total_files}")
    print(f"    - 图片文件数: {image_files}")
    print(f"    - 已复制: {copied_files}")
    print(f"    - 已跳过（已存在）: {skipped_files}")


def main():
    """主函数"""
    print("[+] EVE客户端资源图标提取工具")
    print("=" * 50)
    
    # 获取ResFiles目录
    resfiles_dir = get_eve_resfiles_path()
    if not resfiles_dir:
        print("[x] 无法获取ResFiles目录路径")
        return
    
    # 获取项目根目录和输出目录
    script_path = Path(__file__)
    project_root = script_path.parent.parent
    output_dir = project_root / "output" / "res_icons"
    
    print(f"[+] ResFiles目录: {resfiles_dir}")
    print(f"[+] 输出目录: {output_dir}")
    print()
    
    # 提取图标
    extract_res_icons(resfiles_dir, output_dir)


if __name__ == "__main__":
    main()

