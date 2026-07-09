#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SDE下载器模块
从EVE Online官方下载最新的SDE数据并解压
"""

import json
import zipfile
import shutil
from pathlib import Path
from utils.http_client import get

def get_latest_build_info(config):
    """获取最新的SDE构建信息"""
    try:
        sde_update_url = config["urls"]["sde_update"]
        print(f"[+] 获取最新SDE构建信息: {sde_update_url}")
        response = get(sde_update_url, timeout=30, verify=False)
        
        build_info = response.json()
        build_number = build_info.get('build_number', build_info.get('buildNumber'))
        release_date = build_info.get("releaseDate")
        
        print(f"[+] 最新构建信息:")
        print(f"    构建编号: {build_number}")
        print(f"    发布时间: {release_date}")
        
        return build_number, release_date
    
    except Exception as e:
        print(f"[x] 获取构建信息失败: {e}")
        return None, None
    except json.JSONDecodeError as e:
        print(f"[x] 解析构建信息失败: {e}")
        return None, None

def check_existing_download(config, build_number):
    """检查是否已经下载过指定构建版本的SDE"""
    project_root = Path(__file__).parent.parent
    sde_zip_path = project_root / config["paths"]["sde_zip"]
    zip_filename = f"eve-online-static-data-{build_number}-jsonl.zip"
    zip_path = sde_zip_path / zip_filename
    
    if zip_path.exists():
        print(f"[+] 发现已存在该版本的SDE压缩包: {zip_path}")
        
        # 检查ZIP文件是否损坏
        try:
            with zipfile.ZipFile(zip_path, 'r') as test_zip:
                test_zip.testzip()  # 测试ZIP文件完整性
            print("[+] SDE压缩包完整，可以使用")
            return True, zip_path
        except (zipfile.BadZipFile, zipfile.LargeZipFile) as e:
            print(f"[!] SDE压缩包损坏: {e}")
            print("[+] 将重新下载SDE压缩包")
            zip_path.unlink()  # 删除损坏的文件
            return False, zip_path
        except Exception as e:
            print(f"[!] 检查SDE压缩包时出错: {e}")
            print("[+] 将重新下载SDE压缩包")
            zip_path.unlink()  # 删除可能有问题的文件
            return False, zip_path
    
    return False, zip_path

def download_sde(config, build_number):
    """下载SDE压缩包"""
    project_root = Path(__file__).parent.parent
    sde_zip_path = project_root / config["paths"]["sde_zip"]
    download_url = config["urls"]["sde_download_template"].format(build_number=build_number)
    zip_filename = f"eve-online-static-data-{build_number}-jsonl.zip"
    zip_path = sde_zip_path / zip_filename
    
    try:
        print(f"[+] 开始下载SDE: {download_url}")
        
        response = get(download_url, stream=True, timeout=60, verify=False)
        
        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        print(f"[+] SDE下载完成: {zip_path}")
        return True, zip_path
        
    except Exception as e:
        print(f"[x] SDE下载失败: {e}")
        if zip_path.exists():
            zip_path.unlink()  # 删除不完整的文件
        return False, None

def extract_sde(config, zip_path):
    """解压SDE到指定目录"""
    try:
        project_root = Path(__file__).parent.parent
        sde_input_path = project_root / config["paths"]["sde_input"]
        
        print(f"[+] 开始解压SDE: {zip_path}")
        
        # 清理旧的解压目录
        if sde_input_path.exists():
            print(f"[+] 清理旧的SDE数据: {sde_input_path}")
            shutil.rmtree(sde_input_path)
        
        sde_input_path.mkdir(parents=True, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(sde_input_path)
        
        print(f"[+] SDE解压完成: {sde_input_path}")
        return sde_input_path
        
    except zipfile.BadZipFile as e:
        print(f"[x] 压缩包损坏: {e}")
        return False
    except Exception as e:
        print(f"[x] 解压失败: {e}")
        return False

def main(config=None):
    """
    主函数
    
    Returns:
        bool: True表示SDE下载和解压成功，False表示失败
    """
    print("[+] SDE下载器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        config_path = Path(__file__).parent.parent / "config.json"
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception as e:
            print(f"[x] 加载配置文件失败: {e}")
            return False
    
    # 获取最新构建信息
    build_number, release_date = get_latest_build_info(config)
    if not build_number:
        print("[x] 无法获取构建信息，退出")
        return False
    
    # 检查是否已下载
    exists, zip_path = check_existing_download(config, build_number)
    
    if not exists:
        # 下载SDE
        success, zip_path = download_sde(config, build_number)
        if not success:
            print("[x] SDE下载失败，退出")
            return False
    else:
        print("[+] 跳过下载，使用现有文件")
    
    # 解压SDE
    sde_input_path = extract_sde(config, zip_path)
    if sde_input_path:
        print("[+] SDE下载和解压完成")
        return True
    else:
        print("[x] SDE解压失败")
        return False

if __name__ == "__main__":
    main()
