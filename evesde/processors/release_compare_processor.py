#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Release比较处理器
用于比较当前构建与最新Release的差异
"""

from evesde.paths import PROJECT_ROOT
import json
import os
import zipfile
import subprocess
import difflib
import tempfile
import shutil
from pathlib import Path
from evesde.utils.http_client import get
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Union


class ReleaseCompareProcessor:
    """Release比较处理器"""
    
    def __init__(self, config: Dict[str, Any], build_number: Union[int, str]):
        """初始化Release比较处理器"""
        self.config = config
        self.build_number = build_number
        self.project_root = PROJECT_ROOT
        paths = config.get("paths", {})
        self.output_sde_path = self.project_root / paths.get("sde_output", "output/sde")
        self.output_icons_path = self.project_root / paths.get("icons_output", "output/icons")
        self.tools_path = self.project_root / "tools"
        # Release比较仅对 en 和 zh 版本执行
        self.languages = ["en", "zh"]
        
        # 比较报告写到 output/release/
        release_dir = self.project_root / paths.get("release_output", "output/release")
        release_dir.mkdir(parents=True, exist_ok=True)
        self.compare_md_path = release_dir / f"release_compare_{build_number}.md"
        
        # 临时目录用于下载和解压旧版本
        self.temp_dir = None
        
    def __enter__(self):
        """上下文管理器入口"""
        self.temp_dir = Path(tempfile.mkdtemp())
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口，清理临时文件"""
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def write_md(self, content: str):
        """直接写入Markdown内容"""
        with open(self.compare_md_path, 'a', encoding='utf-8') as f:
            f.write(content)
    
    def _github_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "EVE-SDE-Processor",
        }
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _resolve_github_repo(self) -> str:
        """优先 CI 的 GITHUB_REPOSITORY，否则用 config（本仓库）。"""
        return (
            os.environ.get("GITHUB_REPOSITORY")
            or self.config.get("github_repo")
            or ""
        ).strip()

    def get_latest_release_info(self) -> Optional[Dict[str, Any]]:
        """
        获取本仓库最新 Release（排除 draft / prerelease），按 id 取最大。
        """
        try:
            github_repo = self._resolve_github_repo()
            if not github_repo:
                print("[!] 未配置 github_repo / GITHUB_REPOSITORY，跳过 Release 比较")
                return None

            print(f"[+] Release 比较目标仓库: {github_repo}")
            repo_url = f"https://api.github.com/repos/{github_repo}/releases"
            response = get(repo_url, headers=self._github_headers(), timeout=30)

            all_releases = response.json()
            if not isinstance(all_releases, list):
                return None

            valid_releases = [
                r for r in all_releases
                if not r.get("draft", False) and not r.get("prerelease", False)
            ]
            if not valid_releases:
                return None

            valid_releases.sort(key=lambda x: x.get("id", 0), reverse=True)
            latest = valid_releases[0]
            print(f"[+] 对比上一 Release: {latest.get('tag_name')}")
            return latest

        except Exception as e:
            print(f"[!] 获取最新 Release 失败: {e}")
            return None
    
    def download_release_assets(self, release_info: Dict[str, Any]) -> bool:
        """下载Release资源文件"""
        try:
            assets = release_info.get('assets', [])
            downloaded_files = {}
            
            for asset in assets:
                asset_name = asset.get('name', '')
                download_url = asset.get('browser_download_url', '')
                
                if asset_name in ['icons.zip', 'sde.zip']:
                    headers = {
                        'Accept': 'application/octet-stream',
                        'User-Agent': 'EVE-SDE-Processor',
                    }
                    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                    
                    response = get(download_url, headers=headers, timeout=300)
                    
                    file_path = self.temp_dir / asset_name
                    with open(file_path, 'wb') as f:
                        f.write(response.content)
                    
                    downloaded_files[asset_name] = file_path
            
            # 解压sde.zip
            if 'sde.zip' in downloaded_files:
                sde_zip_path = downloaded_files['sde.zip']
                sde_extract_path = self.temp_dir / "sde_old"
                sde_extract_path.mkdir()
                
                try:
                    # 使用zipfile处理ZIP格式的文件
                    with zipfile.ZipFile(sde_zip_path, 'r') as zip_ref:
                        zip_ref.extractall(sde_extract_path)
                        
                except Exception as e:
                    return False
            
            return True
            
        except Exception as e:
            return False
    
    def compare_icons(self) -> bool:
        """比较图标文件差异（直接比较ZIP文件内容）"""
        try:
            self.write_md("## 图标文件比较\n\n")
            
            # 当前版本图标ZIP文件
            current_icons_zip = self.output_icons_path / "icons.zip"
            old_icons_zip = self.temp_dir / "icons.zip"
            
            if not current_icons_zip.exists():
                self.write_md("当前版本图标ZIP文件不存在\n\n")
                return False
            
            if not old_icons_zip.exists():
                self.write_md("旧版本图标ZIP文件不存在\n\n")
                return False
            
            # 读取ZIP文件内容列表
            current_files = set()
            old_files = set()
            
            # 读取当前版本ZIP文件列表
            with zipfile.ZipFile(current_icons_zip, 'r') as zip_ref:
                current_files = set(zip_ref.namelist())
            
            # 读取旧版本ZIP文件列表
            with zipfile.ZipFile(old_icons_zip, 'r') as zip_ref:
                old_files = set(zip_ref.namelist())
            
            # 分析差异
            added_files = current_files - old_files
            removed_files = old_files - current_files
            common_files = current_files & old_files
            
            # 记录到Markdown
            self.write_md(f"**文件统计**:\n")
            self.write_md(f"- 当前版本: {len(current_files)} 个文件\n")
            self.write_md(f"- 旧版本: {len(old_files)} 个文件\n")
            self.write_md(f"- 新增: {len(added_files)} 个文件\n")
            self.write_md(f"- 删除: {len(removed_files)} 个文件\n")
            self.write_md(f"- 共同: {len(common_files)} 个文件\n\n")
            
            # 详细列出新增/删除（截断，避免报告过大无法入库）
            max_list = 100
            if added_files:
                self.write_md(f"**新增文件** ({len(added_files)} 个):\n")
                for file_name in sorted(added_files)[:max_list]:
                    self.write_md(f"- `{file_name}`\n")
                if len(added_files) > max_list:
                    self.write_md(f"- ... 另有 {len(added_files) - max_list} 个未列出\n")
                self.write_md("\n")

            if removed_files:
                self.write_md(f"**删除文件** ({len(removed_files)} 个):\n")
                for file_name in sorted(removed_files)[:max_list]:
                    self.write_md(f"- `{file_name}`\n")
                if len(removed_files) > max_list:
                    self.write_md(f"- ... 另有 {len(removed_files) - max_list} 个未列出\n")
                self.write_md("\n")
            
            # 检查文件大小变化（只检查前10个文件，避免输出过多）
            changed_files = []
            for file_name in sorted(common_files)[:10]:
                try:
                    with zipfile.ZipFile(current_icons_zip, 'r') as current_zip:
                        current_info = current_zip.getinfo(file_name)
                        current_size = current_info.file_size
                    
                    with zipfile.ZipFile(old_icons_zip, 'r') as old_zip:
                        old_info = old_zip.getinfo(file_name)
                        old_size = old_info.file_size
                    
                    if current_size != old_size:
                        changed_files.append(f"{file_name} ({old_size} -> {current_size} bytes)")
                except KeyError:
                    # 文件在某个ZIP中不存在，跳过
                    continue
            
            if changed_files:
                self.write_md(f"**内容变化文件** ({len(changed_files)} 个):\n")
                for file_name in changed_files:
                    self.write_md(f"- `{file_name}`\n")
                self.write_md("\n")
            
            return True
            
        except Exception as e:
            return False
    
    def compare_databases(self) -> bool:
        """比较数据库差异"""
        try:
            self.write_md("## 数据库比较\n\n")
            
            sqldiff_path = self.tools_path / "sqldiff"
            if not sqldiff_path.exists():
                self.write_md("sqldiff工具不存在\n\n")
                return False
            
            # 确保sqldiff有执行权限
            sqldiff_path.chmod(0o755)
            
            from evesde.utils.single_db import get_db_path

            current_db = get_db_path(self.config)
            old_db = self.temp_dir / "sde_old" / "db" / current_db.name
            # 兼容旧版多库命名
            if not old_db.exists():
                old_db = self.temp_dir / "sde_old" / "db" / "item_db_en.sqlite"

            self.write_md("### 单库 (item_db.sqlite)\n\n")

            if not current_db.exists():
                self.write_md("当前版本数据库不存在\n\n")
                return False

            if not old_db.exists():
                self.write_md("旧版本数据库不存在\n\n")
                return False

            try:
                result = subprocess.run(
                    [str(sqldiff_path), '--primarykey', str(old_db), str(current_db)],
                    capture_output=True,
                    text=True,
                    timeout=300
                )

                if result.returncode == 0:
                    if result.stdout.strip():
                        lines = result.stdout.strip().split("\n")
                        # 摘要统计，避免整库 SQL 写入导致报告超 100MB
                        inserts = sum(1 for L in lines if L.startswith("INSERT"))
                        updates = sum(1 for L in lines if L.startswith("UPDATE"))
                        deletes = sum(1 for L in lines if L.startswith("DELETE"))
                        other = len(lines) - inserts - updates - deletes
                        self.write_md("**数据库差异摘要**:\n")
                        self.write_md(f"- 语句总数: {len(lines)}\n")
                        self.write_md(f"- INSERT: {inserts} / UPDATE: {updates} / DELETE: {deletes}")
                        if other:
                            self.write_md(f" / 其他: {other}")
                        self.write_md("\n\n")

                        max_sql_lines = 200
                        self.write_md(f"**差异样例**（前 {min(max_sql_lines, len(lines))} 行）:\n")
                        self.write_md("```sql\n")
                        for line in lines[:max_sql_lines]:
                            self.write_md(f"{line}\n")
                        if len(lines) > max_sql_lines:
                            self.write_md(
                                f"-- ... 另有 {len(lines) - max_sql_lines} 行未列出\n"
                            )
                        self.write_md("```\n\n")
                    else:
                        self.write_md("数据库无差异\n\n")
                else:
                    self.write_md(f"sqldiff执行失败: {result.stderr}\n\n")

            except subprocess.TimeoutExpired:
                self.write_md("sqldiff执行超时\n\n")
            except Exception as e:
                self.write_md(f"sqldiff执行异常: {e}\n\n")
            
            return True
            
        except Exception as e:
            return False
    
    def compare_json(self) -> bool:
        """比较地图文件和本地化文件差异"""
        try:
            self.write_md("## 地图和本地化文件比较\n\n")
            
            # 当前版本地图目录
            current_maps_path = self.output_sde_path / "maps"
            # 旧版本地图目录：GitHub Actions压缩时是平铺结构，文件在sde_old/maps目录
            old_maps_path = self.temp_dir / "sde_old" / "maps"
            
            if not current_maps_path.exists():
                self.write_md("当前版本地图目录不存在\n\n")
                return False
            
            # 地图文件列表
            map_files = ['regions_data.json', 'systems_data.json', 'neighbors_data.json']
            
            # 本地化文件列表
            localization_files = ['accountingentrytypes_localized.json']
            
            for map_file in map_files:
                self.write_md(f"### {map_file}\n\n")
                
                current_file = current_maps_path / map_file
                old_file = old_maps_path / map_file
                
                if not current_file.exists():
                    self.write_md("当前版本文件不存在\n\n")
                    continue
                
                if not old_file.exists():
                    self.write_md("旧版本文件不存在\n\n")
                    continue
                
                # 读取文件内容
                try:
                    with open(current_file, 'r', encoding='utf-8') as f:
                        current_content = f.readlines()
                    
                    with open(old_file, 'r', encoding='utf-8') as f:
                        old_content = f.readlines()
                    
                    # 使用difflib比较
                    diff = list(difflib.unified_diff(
                        old_content,
                        current_content,
                        fromfile=f"old_{map_file}",
                        tofile=f"new_{map_file}",
                        lineterm=''
                    ))
                    
                    if diff:
                        self.write_md("**文件差异**:\n")
                        self.write_md("```diff\n")
                        for line in diff[:50]:  # 只显示前50行差异
                            self.write_md(f"{line}\n")
                        if len(diff) > 50:
                            self.write_md(f"... (还有 {len(diff) - 50} 行差异)\n")
                        self.write_md("```\n\n")
                    else:
                        self.write_md("文件无差异\n\n")
                        
                except Exception as e:
                    self.write_md(f"比较失败: {e}\n\n")
            
            # 比较本地化文件
            self.write_md("## 本地化文件比较\n\n")
            current_localization_path = self.output_sde_path / "localization"
            old_localization_path = self.temp_dir / "sde_old" / "localization"
            
            for localization_file in localization_files:
                self.write_md(f"### {localization_file}\n\n")
                
                current_file = current_localization_path / localization_file
                old_file = old_localization_path / localization_file
                
                if not current_file.exists():
                    self.write_md("当前版本文件不存在\n\n")
                    continue
                
                if not old_file.exists():
                    self.write_md("旧版本文件不存在\n\n")
                    continue
                
                # 读取文件内容
                try:
                    with open(current_file, 'r', encoding='utf-8') as f:
                        current_content = f.readlines()
                    
                    with open(old_file, 'r', encoding='utf-8') as f:
                        old_content = f.readlines()
                    
                    # 使用difflib比较
                    diff = difflib.unified_diff(
                        old_content,
                        current_content,
                        fromfile=str(old_file),
                        tofile=str(current_file),
                        lineterm=''
                    )
                    
                    diff_lines = list(diff)
                    if diff_lines:
                        self.write_md("**文件差异**:\n")
                        self.write_md("```diff\n")
                        for line in diff_lines[:50]:  # 只显示前50行差异
                            self.write_md(f"{line}\n")
                        if len(diff_lines) > 50:
                            self.write_md(f"... (还有 {len(diff_lines) - 50} 行差异)\n")
                        self.write_md("```\n\n")
                    else:
                        self.write_md("文件无差异\n\n")
                        
                except Exception as e:
                    self.write_md(f"比较失败: {e}\n\n")
            
            return True
            
        except Exception as e:
            return False
    
    def process_release_compare(self) -> bool:
        """执行完整的Release比较流程"""
        try:
            # 初始化Markdown文件
            with open(self.compare_md_path, 'w', encoding='utf-8') as f:
                f.write(f"# EVE SDE Build {self.build_number} - 版本比较报告\n\n")
                f.write(f"**构建时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # 1. 获取最新Release信息
            release_info = self.get_latest_release_info()
            if not release_info:
                # 添加首次构建说明到Markdown
                self.write_md("## 首次构建\n\n")
                self.write_md("这是首次构建，无历史版本可比较。\n\n")
                self.write_md("## 下载文件\n\n")
                self.write_md("- **icons.zip**: 图标压缩包\n")
                self.write_md("- **sde.zip**: SDE数据压缩包\n")
                self.write_md("- **release_compare_{}.md**: 详细比较报告\n".format(self.build_number))
                
                return False
            
            # 2. 下载Release资源
            if not self.download_release_assets(release_info):
                self.write_md("## 下载失败\n\n")
                self.write_md("下载Release资源失败，跳过比较\n\n")
                return False
            
            # 3. 比较图标文件
            self.compare_icons()
            
            # 4. 比较数据库文件
            self.compare_databases()
            
            # 5. 比较地图和本地化文件
            self.compare_json()
            
            # 添加下载文件说明到Markdown
            self.write_md("\n## 下载文件\n\n")
            self.write_md("- **icons.zip**: 图标压缩包\n")
            self.write_md("- **sde.zip**: SDE数据压缩包\n")
            self.write_md("- **release_compare_{}.md**: 详细比较报告\n".format(self.build_number))
            
            return True
            
        except Exception as e:
            return False


def main(config: Dict[str, Any], build_number: Union[int, str]) -> bool:
    """主函数"""
    with ReleaseCompareProcessor(config, build_number) as processor:
        return processor.process_release_compare()


if __name__ == "__main__":
    config_path = PROJECT_ROOT / "config.json"
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 测试Release比较
    success = main(config, build_number=999999)
    print(f"测试结果: {'成功' if success else '失败'}")
