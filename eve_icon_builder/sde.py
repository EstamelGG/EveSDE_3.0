"""
SDE (Static Data Export) 数据获取和解析模块
"""

import json
import sys
import os
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.http_client import get
from typing import Dict, Optional, Tuple
from zipfile import ZipFile
import io


class TypeInfo:
    """物品类型信息"""
    def __init__(self, group_id: int, icon_id: Optional[int] = None, 
                 graphic_id: Optional[int] = None, meta_group_id: Optional[int] = None):
        self.group_id = group_id
        self.icon_id = icon_id
        self.graphic_id = graphic_id
        self.meta_group_id = meta_group_id


def get_sde_version() -> int:
    """获取最新的SDE版本号"""
    response = get("https://binaries.eveonline.com/eveclient_TQ.json")
    data = response.json()
    build = data.get("build_number") or data.get("buildNumber")
    if build is None:
        raise ValueError("未找到SDE版本信息")

    return build


def download_sde(dest_path: Path):
    """下载SDE数据包"""
    response = get("https://developers.eveonline.com/static-data/eve-online-static-data-latest-jsonl.zip", 
                          stream=True)
    
    with open(dest_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)


def parse_version(content: str) -> int:
    """解析版本信息"""
    for line in content.strip().split('\n'):
        data = json.loads(line)
        if data.get('_key') == 'sde':
            return data.get('build_number', data.get('buildNumber'))
    raise ValueError("未找到SDE版本信息")


def update_sde(silent_mode: bool = False) -> ZipFile:
    """更新SDE数据，返回打开的ZIP文件对象"""
    cache_dir = Path("./cache")
    cache_dir.mkdir(exist_ok=True)
    sde_path = cache_dir / "sde.zip"
    
    download = True
    new_version = get_sde_version()
    
    if sde_path.exists():
        with ZipFile(sde_path, 'r') as zf:
            version_content = zf.read('_sde.jsonl').decode('utf-8')
            current_version = parse_version(version_content)
            download = (current_version != new_version)
    
    if download:
        if not silent_mode:
            print("正在下载新的SDE数据...")
        download_sde(sde_path)
    
    if not silent_mode:
        print("SDE数据已是最新!")
    
    return ZipFile(sde_path, 'r')


def read_types(sde: ZipFile, silent_mode: bool = False) -> Dict[int, TypeInfo]:
    """读取物品类型信息"""
    if not silent_mode:
        print("\t加载物品类型...")
    
    types = {}
    content = sde.read('types.jsonl').decode('utf-8')
    
    for line in content.strip().split('\n'):
        if not line.strip():
            continue
        data = json.loads(line)
        type_id = data['_key']
        
        type_info = TypeInfo(
            group_id=data.get('groupID', 0),
            icon_id=data.get('iconID'),
            graphic_id=data.get('graphicID'),
            meta_group_id=data.get('metaGroupID')
        )
        
        # 过滤：只保留有图标或图形ID的物品，或特定的SKIN组
        if (type_info.graphic_id is not None or 
            type_info.icon_id is not None or 
            (1950 <= type_info.group_id <= 1955) or 
            type_info.group_id == 4040):
            types[type_id] = type_info
    
    return types


def read_group_categories(sde: ZipFile, silent_mode: bool = False) -> Dict[int, int]:
    """读取组别分类映射"""
    if not silent_mode:
        print("\t加载物品分组...")
    
    group_categories = {}
    content = sde.read('groups.jsonl').decode('utf-8')
    
    for line in content.strip().split('\n'):
        if not line.strip():
            continue
        data = json.loads(line)
        group_id = data['_key']
        category_id = data.get('categoryID')
        if category_id is not None:
            group_categories[group_id] = category_id
    
    return group_categories


def read_icons(sde: ZipFile, silent_mode: bool = False) -> Dict[int, str]:
    """读取图标文件映射"""
    if not silent_mode:
        print("\t加载图标信息...")
    
    icon_files = {}
    content = sde.read('icons.jsonl').decode('utf-8')
    
    for line in content.strip().split('\n'):
        if not line.strip():
            continue
        data = json.loads(line)
        icon_id = data['_key']
        icon_file = data.get('iconFile')
        if icon_file:
            icon_files[icon_id] = icon_file
    
    return icon_files


def read_graphics(sde: ZipFile, silent_mode: bool = False) -> Dict[int, str]:
    """读取图形文件夹映射"""
    if not silent_mode:
        print("\t加载图形信息...")
    
    graphics_folders = {}
    content = sde.read('graphics.jsonl').decode('utf-8')
    
    for line in content.strip().split('\n'):
        if not line.strip():
            continue
        data = json.loads(line)
        graphic_id = data['_key']
        icon_folder = data.get('iconFolder')
        if icon_folder:
            graphics_folders[graphic_id] = icon_folder.replace('\\', '/').rstrip('/')
    
    return graphics_folders


def read_skin_materials(sde: ZipFile, silent_mode: bool = False) -> Dict[int, int]:
    """读取皮肤材质映射"""
    if not silent_mode:
        print("\t加载皮肤信息...")
    
    # 读取皮肤许可证
    license_skins = {}
    content = sde.read('skinLicenses.jsonl').decode('utf-8')
    for line in content.strip().split('\n'):
        if not line.strip():
            continue
        data = json.loads(line)
        license_id = data['_key']
        skin_id = data.get('skinID')
        if skin_id is not None:
            license_skins[license_id] = skin_id
    
    # 读取皮肤材质
    skin_materials = {}
    content = sde.read('skinMaterials.jsonl').decode('utf-8')
    for line in content.strip().split('\n'):
        if not line.strip():
            continue
        data = json.loads(line)
        skin_id = data['_key']
        material_id = data.get('skinMaterialID')
        if material_id is not None:
            skin_materials[skin_id] = material_id
    
    # 映射许可证到材质
    license_materials = {}
    for license_id, skin_id in license_skins.items():
        if skin_id in skin_materials:
            license_materials[license_id] = skin_materials[skin_id]
    
    return license_materials
