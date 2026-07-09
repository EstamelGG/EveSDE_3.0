#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从resfileindex.txt提取图标工具
从resfileindex.txt中读取文件列表，检测图片文件并复制到output/icons_search目录
"""

import os
import sys
import shutil
import platform
import argparse
from pathlib import Path
from typing import Optional, Tuple, Dict, List

# 添加项目根目录到路径，以便导入utils模块
script_path = Path(__file__).resolve()
project_root = script_path.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from utils.http_client import create_session


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


def get_eve_resfileindex_path() -> Optional[Path]:
    """获取EVE客户端resfileindex.txt文件路径"""
    system = platform.system().lower()
    
    if system == "darwin":  # macOS
        base_path = Path.home() / "Library/Application Support/EVE Online/SharedCache/tq/EVE.app/Contents/Resources/build/resfileindex.txt"
        return base_path
    else:
        return None


def get_resfile_index_content() -> Optional[str]:
    """从在线服务器获取resfileindex.txt内容"""
    try:
        session = create_session(verify=False)
        print("[+] 获取EVE客户端构建信息...")
        response = session.get("https://binaries.eveonline.com/eveclient_TQ.json")
        build_info = response.json()
        build_number = build_info.get('build')
        
        if not build_number:
            return None
        
        print(f"[+] 当前构建版本: {build_number}")
        print("[+] 从在线服务器获取resfileindex...")
        
        installer_url = f"https://binaries.eveonline.com/eveonline_{build_number}.txt"
        response = session.get(installer_url)
        
        # 解析installer文件找到resfileindex
        resfileindex_path = None
        for line in response.text.split('\n'):
            if not line.strip():
                continue
            
            parts = line.split(',')
            if len(parts) >= 2 and parts[0] == "app:/resfileindex.txt":
                resfileindex_path = parts[1]
                break
        
        if not resfileindex_path:
            print("[x] 在installer文件中未找到resfileindex路径")
            return None
        
        # 下载resfileindex文件内容
        resfile_url = f"https://binaries.eveonline.com/{resfileindex_path}"
        response = session.get(resfile_url)
        
        print("[+] resfileindex获取完成")
        return response.text
        
    except Exception as e:
        print(f"[x] 获取resfileindex失败: {e}")
        return None


def load_resfile_index(keyword: Optional[str] = None) -> List[Tuple[str, str]]:
    """
    加载resfileindex，返回文件列表
    
    Args:
        keyword: 可选的关键词，用于过滤资源路径
        
    Returns:
        [(resource_path, file_path), ...] 列表
    """
    file_list = []
    
    # 首先尝试从在线服务器获取
    resfile_content = get_resfile_index_content()
    
    # 如果在线获取失败，尝试本地客户端路径
    if not resfile_content:
        resfileindex_path = get_eve_resfileindex_path()
        
        if not resfileindex_path or not resfileindex_path.exists():
            print("[-] 无法获取resfileindex文件（在线和本地都失败）")
            return file_list
        
        try:
            with open(resfileindex_path, 'r', encoding='utf-8') as f:
                resfile_content = f.read()
        except Exception as e:
            print(f"[x] 读取本地resfileindex失败: {e}")
            return file_list
    
    print("[+] 解析资源索引...")
    
    try:
        for line_num, line in enumerate(resfile_content.split('\n'), 1):
            line = line.strip()
            if not line:
                continue
            
            parts = line.split(',')
            if len(parts) >= 2:
                resource_path = parts[0]  # 资源路径，如 res:/ui/texture/icon.png
                file_path = parts[1]       # 本地文件路径，如 res/ui/texture/icon.png
                
                # 如果提供了关键词，检查资源路径是否包含关键词
                if keyword:
                    if keyword.lower() not in resource_path.lower():
                        continue
                
                file_list.append((resource_path, file_path))
        
        print(f"[+] 加载了 {len(file_list)} 个资源文件")
        if keyword:
            print(f"[+] 过滤关键词: {keyword}")
        
    except Exception as e:
        print(f"[x] 解析资源索引时出错: {e}")
    
    return file_list


def extract_icons_from_index(resfiles_dir: Path, output_dir: Path, keyword: Optional[str] = None):
    """
    从resfileindex中提取图片文件
    
    Args:
        resfiles_dir: ResFiles目录路径
        output_dir: 输出目录路径
        keyword: 可选的关键词，用于过滤资源路径
    """
    if not resfiles_dir.exists():
        print(f"[x] ResFiles目录不存在: {resfiles_dir}")
        return
    
    # 加载resfileindex
    file_list = load_resfile_index(keyword=keyword)
    
    if not file_list:
        print("[x] 没有找到符合条件的文件")
        return
    
    # 确保输出目录存在
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"[+] 开始处理文件...")
    print(f"[+] ResFiles目录: {resfiles_dir}")
    print(f"[+] 输出目录: {output_dir}")
    print()
    
    total_files = len(file_list)
    image_files = 0
    copied_files = 0
    skipped_files = 0
    not_found_files = 0
    
    for idx, (resource_path, file_path) in enumerate(file_list, 1):
        # 构建完整的本地文件路径
        local_file_path = resfiles_dir / file_path
        
        # 检查文件是否存在
        if not local_file_path.exists():
            not_found_files += 1
            if idx % 1000 == 0:
                print(f"[+] 已处理 {idx}/{total_files} 个文件...")
            continue
        
        # 检测是否为图片
        is_image, image_type = is_image_file(local_file_path)
        
        if not is_image:
            if idx % 1000 == 0:
                print(f"[+] 已处理 {idx}/{total_files} 个文件...")
            continue
        
        image_files += 1
        
        # 从资源路径中提取文件名
        if resource_path.startswith('res:'):
            path_part = resource_path[4:]  # 去掉 "res:" 前缀
        else:
            path_part = resource_path
        
        # 提取文件名（最后一个路径分隔符后的部分）
        filename = os.path.basename(path_part.replace('\\', '/'))
        
        # 处理后缀：如果有扩展名则替换为.png，否则添加.png
        if '.' in filename:
            # 有扩展名：armor.png -> armor.png（替换扩展名）
            name_without_ext = filename.rsplit('.', 1)[0]
            base_filename = f"{name_without_ext}.png"
        else:
            # 没有扩展名：armor -> armor.png（添加扩展名）
            base_filename = f"{filename}.png"
        
        # 处理重名：如果文件已存在，在文件名后加数字
        output_filename = base_filename
        output_path = output_dir / output_filename
        counter = 1
        
        while output_path.exists():
            # 在文件名后添加数字
            name_without_ext = base_filename.rsplit('.', 1)[0]
            ext = base_filename.rsplit('.', 1)[1] if '.' in base_filename else ''
            if ext:
                output_filename = f"{name_without_ext}_{counter}.{ext}"
            else:
                output_filename = f"{name_without_ext}_{counter}"
            output_path = output_dir / output_filename
            counter += 1
        
        try:
            # 复制文件并添加.png后缀
            shutil.copy2(local_file_path, output_path)
            copied_files += 1
            
            if copied_files % 100 == 0:
                print(f"[+] 已复制 {copied_files} 个图片文件...")
                
        except Exception as e:
            print(f"[!] 复制文件失败 {local_file_path} -> {output_path}: {e}")
    
    print("\n[+] 提取完成!")
    print(f"    - 总文件数: {total_files}")
    print(f"    - 图片文件数: {image_files}")
    print(f"    - 已复制: {copied_files}")
    print(f"    - 已跳过（已存在）: {skipped_files}")
    print(f"    - 文件不存在: {not_found_files}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='从resfileindex.txt提取图标工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                          # 提取resfileindex中所有图片文件
  %(prog)s --keyword "icon"         # 只提取资源路径包含"icon"的图片
  %(prog)s --keyword "ui/texture"   # 只提取资源路径包含"ui/texture"的图片
        """
    )
    parser.add_argument(
        '--keyword',
        type=str,
        help='过滤关键词：只处理资源路径（res:/xxx）包含此关键词的文件'
    )
    
    args = parser.parse_args()
    
    print("[+] 从resfileindex.txt提取图标工具")
    print("=" * 50)
    
    # 获取ResFiles目录
    resfiles_dir = get_eve_resfiles_path()
    if not resfiles_dir:
        print("[x] 无法获取ResFiles目录路径")
        return
    
    # 获取项目根目录和输出目录
    script_path = Path(__file__)
    project_root = script_path.parent.parent
    output_dir = project_root / "output" / "icons_search"
    
    print(f"[+] ResFiles目录: {resfiles_dir}")
    print(f"[+] 输出目录: {output_dir}")
    if args.keyword:
        print(f"[+] 过滤关键词: {args.keyword}")
    print()
    
    # 提取图标
    extract_icons_from_index(resfiles_dir, output_dir, keyword=args.keyword)


if __name__ == "__main__":
    main()

