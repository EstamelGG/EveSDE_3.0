#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图标下载器模块
下载并解压EVE图标包，支持版本检查和智能缓存
"""

import json
import zipfile
import shutil
from pathlib import Path
from utils.http_client import get


def get_current_build_number(config):
    """获取当前SDE的构建版本号"""
    project_root = Path(__file__).parent.parent
    sde_input_path = project_root / config["paths"]["sde_input"]
    build_info_path = sde_input_path / "build_info.json"
    
    if build_info_path.exists():
        try:
            with open(build_info_path, 'r', encoding='utf-8') as f:
                build_info = json.load(f)
                return build_info.get("build_number")
        except:
            pass
    return None


def get_cached_build_number(icons_zip_dir):
    """获取缓存的图标包对应的构建版本号"""
    build_cache_path = icons_zip_dir / "icons_build_info.json"
    
    if build_cache_path.exists():
        try:
            with open(build_cache_path, 'r', encoding='utf-8') as f:
                cache_info = json.load(f)
                return cache_info.get("build_number")
        except:
            pass
    return None


def save_icons_build_info(icons_zip_dir, build_number):
    """保存图标包的构建版本信息"""
    build_cache_path = icons_zip_dir / "icons_build_info.json"
    
    try:
        with open(build_cache_path, 'w', encoding='utf-8') as f:
            json.dump({"build_number": build_number}, f)
        print(f"[+] 已保存图标包构建信息: {build_number}")
    except Exception as e:
        print(f"[!] 保存构建信息失败: {e}")


def download_icons_zip(config):
    """下载图标压缩包"""
    project_root = Path(__file__).parent.parent
    icons_zip_dir = project_root / "icons_zip"
    icons_zip_dir.mkdir(exist_ok=True)
    
    icons_zip_path = icons_zip_dir / "icons_dedup.zip"
    icons_input_path = project_root / config["paths"]["icons_input"]
    icons_output_path = project_root / config["paths"]["icons_output"]

    icons_zip_url = config["urls"]["icons_zip"]
    
    # 获取当前SDE构建版本号
    current_build = get_current_build_number(config)
    cached_build = get_cached_build_number(icons_zip_dir)
    
    print(f"[+] 当前SDE构建版本: {current_build}")
    print(f"[+] 缓存图标构建版本: {cached_build}")
    
    # 检查是否需要重新下载
    need_download = False
    
    if not icons_zip_path.exists():
        print("[+] 未找到图标包，需要下载")
        need_download = True
    elif current_build and cached_build and current_build != cached_build:
        print("[+] SDE版本更新，需要重新下载图标包")
        icons_zip_path.unlink()  # 删除旧文件
        need_download = True
    elif icons_zip_path.exists():
        # 检查ZIP文件是否损坏
        try:
            with zipfile.ZipFile(icons_zip_path, 'r') as test_zip:
                test_zip.testzip()  # 测试ZIP文件完整性
            print("[+] 图标包已存在且完整，跳过下载")
            if not cached_build and current_build:
                # 保存当前构建版本信息
                save_icons_build_info(icons_zip_dir, current_build)
        except (zipfile.BadZipFile, zipfile.LargeZipFile) as e:
            print(f"[!] 图标包损坏: {e}")
            print("[+] 将重新下载图标包")
            icons_zip_path.unlink()  # 删除损坏的文件
            need_download = True
        except Exception as e:
            print(f"[!] 检查图标包时出错: {e}")
            print("[+] 将重新下载图标包")
            icons_zip_path.unlink()  # 删除可能有问题的文件
            need_download = True
    
    # 下载文件
    if need_download:
        try:
            print(f"[+] 开始下载图标包: {icons_zip_url}")
            response = get(icons_zip_url, stream=True, timeout=60)
            
            with open(icons_zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            print(f"[+] 图标包下载完成: {icons_zip_path}")
            
            # 保存构建版本信息
            if current_build:
                save_icons_build_info(icons_zip_dir, current_build)
            
        except Exception as e:
            print(f"[x] 图标包下载失败: {e}")
            if icons_zip_path.exists():
                icons_zip_path.unlink()
            return False
    
    # 解压文件
    try:
        print(f"[+] 开始解压图标包: {icons_zip_path}")
        
        # 清理旧的解压目录
        if icons_input_path.exists():
            print(f"[+] 清理旧的图标输入数据: {icons_input_path}")
            shutil.rmtree(icons_input_path)
            print(f"[+] 清理旧的图标输出数据: {icons_output_path}")
            shutil.rmtree(icons_output_path)
        
        icons_input_path.mkdir(parents=True, exist_ok=True)
        
        with zipfile.ZipFile(icons_zip_path, 'r') as zip_ref:
            zip_ref.extractall(icons_input_path)
        
        print(f"[+] 图标包解压完成: {icons_input_path}")
        
        # 统计解压的文件数量
        png_files = list(icons_input_path.glob("**/*.png"))
        json_files = list(icons_input_path.glob("**/*.json"))
        
        print(f"[+] 解压得到:")
        print(f"    - PNG图标文件: {len(png_files)} 个")
        print(f"    - JSON元数据文件: {len(json_files)} 个")
        
        # 查找service_metadata.json
        metadata_files = list(icons_input_path.glob("**/service_metadata.json"))
        if metadata_files:
            print(f"[+] 找到service_metadata.json: {metadata_files[0]}")
        else:
            print("[!] 未找到service_metadata.json文件")
        
        return True
        
    except zipfile.BadZipFile as e:
        print(f"[x] 压缩包损坏: {e}")
        return False
    except Exception as e:
        print(f"[x] 解压失败: {e}")
        return False


def main(config=None):
    """主函数"""
    print("[+] 图标下载器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 下载并解压图标包
    success = download_icons_zip(config)
    
    if success:
        print("[+] 图标下载器完成")
    else:
        print("[x] 图标下载器失败")
        exit(-1)


if __name__ == "__main__":
    main()
