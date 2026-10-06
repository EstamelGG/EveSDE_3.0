"""
SDE (Static Data Export) 数据获取和解析模块
"""

import json
from pathlib import Path
from typing import Dict, Optional
from zipfile import ZipFile

from evesde.paths import load_config
from evesde.processors.sde_downloader import download_sde as download_sde_archive


class TypeInfo:
    """物品类型信息"""
    def __init__(self, group_id: int, icon_id: Optional[int] = None, 
                 graphic_id: Optional[int] = None, meta_group_id: Optional[int] = None):
        self.group_id = group_id
        self.icon_id = icon_id
        self.graphic_id = graphic_id
        self.meta_group_id = meta_group_id


def update_sde(silent_mode=False, build_number=None, source_zip=None) -> ZipFile:
    """主流水线直接传入同次下载的压缩包；开发入口复用公共下载器。"""
    if source_zip is not None:
        return ZipFile(source_zip)
    config = load_config()
    if build_number is None:
        from evesde.build_prep import get_latest_sde_info
        info = get_latest_sde_info(config)
        if not info:
            raise RuntimeError("无法获取 SDE 版本")
        build_number = info["build_number"]
    success, filename = download_sde_archive(config, build_number)
    if not success:
        raise RuntimeError("SDE 下载失败")
    return ZipFile(filename)


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
    
    license_materials = {}
    for license_id, skin_id in license_skins.items():
        if skin_id in skin_materials:
            license_materials[license_id] = skin_materials[skin_id]
    
    return license_materials


def read_build_data(sde: ZipFile, silent_mode=False):
    """项目流水线与图标开发入口共用同一套 SDE 解析。"""
    from evesde.icon_builder.icons import IconBuildData
    return IconBuildData(
        types=read_types(sde, silent_mode),
        group_categories=read_group_categories(sde, silent_mode),
        icon_files=read_icons(sde, silent_mode),
        graphics_folders=read_graphics(sde, silent_mode),
        skin_materials=read_skin_materials(sde, silent_mode),
    )
