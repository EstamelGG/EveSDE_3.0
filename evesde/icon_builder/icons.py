"""
图标生成核心逻辑模块
"""

import hashlib
import json
import os
import shutil
from enum import Enum
from pathlib import Path
from typing import Dict, Set, Optional, Tuple, List
from zipfile import ZipFile, ZIP_STORED
from PIL import Image, ImageChops
import numpy as np

from evesde.icon_builder.cache import SharedCache
from evesde.icon_builder.sde import TypeInfo

# 不再使用tqdm，改为简单的计数显示


# 反应蓝图使用不同的背景
REACTION_GROUPS = [1888, 1889, 1890, 4097]

# 某些类型有3D模型但使用2D图标
USE_ICON_INSTEAD_OF_GRAPHIC_GROUPS = [12, 340, 448, 479, 548, 649, 711, 4168]


class IconKind(Enum):
    """图标类型"""
    ICON = "icon"
    BLUEPRINT = "bp"
    BLUEPRINT_COPY = "bpc"
    REACTION = "reaction"
    RELIC = "relic"
    RENDER = "render"


class IconError(Exception):
    """图标处理错误"""
    pass


def techicon_resource_for_metagroup(metagroup_id: int) -> Optional[str]:
    """获取技术等级覆盖层资源路径"""
    mapping = {
        1: None,
        2: "res:/ui/texture/icons/73_16_242.png",
        3: "res:/ui/texture/icons/73_16_245.png",
        4: "res:/ui/texture/icons/73_16_246.png",
        5: "res:/ui/texture/icons/73_16_248.png",
        6: "res:/ui/texture/icons/73_16_247.png",
        14: "res:/ui/texture/icons/73_16_243.png",
        15: "res:/ui/texture/icons/itemoverlay/abyssal.png",
        17: "res:/ui/texture/icons/itemoverlay/nes.png",
        19: "res:/ui/texture/icons/itemoverlay/timelimited.png",
        52: "res:/ui/texture/shared/structureoverlayfaction.png",
        53: "res:/ui/texture/shared/structureoverlayt2.png",
        54: "res:/ui/texture/shared/structureoverlay.png",
    }
    return mapping.get(metagroup_id)


def _maybe_add_resource(cache: SharedCache, resources: Set[str], resource: Optional[str]) -> None:
    if resource and cache.has_resource(resource):
        resources.add(resource)


def collect_required_resources(
    data: "IconBuildData",
    cache: SharedCache,
    skip_skins: bool = False,
    test_type_id: Optional[int] = None,
) -> List[str]:
    resources: Set[str] = set()
    for overlay in (
        "res:/ui/texture/icons/relic.png",
        "res:/ui/texture/icons/relic_overlay.png",
        "res:/ui/texture/icons/reaction.png",
        "res:/ui/texture/icons/bpo_overlay.png",
        "res:/ui/texture/icons/bpo.png",
        "res:/ui/texture/icons/bpc.png",
        "res:/ui/texture/icons/bpc_overlay.png",
    ):
        _maybe_add_resource(cache, resources, overlay)

    for type_id, type_info in data.types.items():
        if test_type_id is not None and type_id != test_type_id:
            continue
        category_id = data.group_categories.get(type_info.group_id)
        if category_id is None:
            continue
        if type_info.icon_id is None and type_info.graphic_id is None and category_id != 91:
            continue
        if skip_skins and category_id in [91, 30, 2118]:
            continue

        if category_id in (9, 34):
            if type_info.graphic_id and type_info.graphic_id in data.graphics_folders:
                folder = data.graphics_folders[type_info.graphic_id].rstrip("/\\")
                _maybe_add_resource(cache, resources, f"{folder}/{type_info.graphic_id}_64_bp.png")
                _maybe_add_resource(cache, resources, f"{folder}/{type_info.graphic_id}_64_bpc.png")
            elif type_info.icon_id and type_info.icon_id in data.icon_files:
                icon_resource = data.icon_files[type_info.icon_id]
                _maybe_add_resource(cache, resources, icon_resource)
                _maybe_add_resource(cache, resources, techicon_resource_for_metagroup(type_info.meta_group_id or 1))
        else:
            icon_resource = None
            if type_info.graphic_id and type_info.graphic_id in data.graphics_folders:
                folder = data.graphics_folders[type_info.graphic_id].rstrip("/\\")
                icon_resource = f"{folder}/{type_info.graphic_id}_64.png"
                if not cache.has_resource(icon_resource) or type_info.group_id in USE_ICON_INSTEAD_OF_GRAPHIC_GROUPS:
                    if type_info.icon_id and type_info.icon_id in data.icon_files:
                        icon_resource = data.icon_files[type_info.icon_id]
                    else:
                        icon_resource = None
                _maybe_add_resource(cache, resources, f"{folder}/{type_info.graphic_id}_512.jpg")
            elif type_info.icon_id and type_info.icon_id in data.icon_files:
                icon_resource = data.icon_files[type_info.icon_id]
            elif category_id == 91 and type_id in data.skin_materials:
                icon_resource = f"res:/ui/texture/classes/skins/icons/{data.skin_materials[type_id]}.png"

            _maybe_add_resource(cache, resources, icon_resource)
            _maybe_add_resource(cache, resources, techicon_resource_for_metagroup(type_info.meta_group_id or 1))

    return list(resources)


def composite_tech(icon_path: Path, tech_icon_path: Path, out_path: Path):
    """合成技术等级覆盖层"""
    # 加载并调整主图标大小
    image = Image.open(icon_path).convert('RGBA')
    image = image.resize((64, 64), Image.Resampling.LANCZOS)
    
    # 加载并调整技术等级覆盖层
    tech_overlay = Image.open(tech_icon_path).convert('RGBA')
    tech_overlay = tech_overlay.resize((16, 16), Image.Resampling.LANCZOS)
    
    # 在左上角合成覆盖层
    image.paste(tech_overlay, (0, 0), tech_overlay)
    image.save(out_path, 'PNG')


def composite_blueprint(background_path: Path, overlay_path: Path, icon_path: Path,
                       tech_icon_path: Optional[Path], out_path: Path):
    """合成蓝图图标"""
    # 加载背景
    background = Image.open(background_path).convert('RGBA')
    
    # 加载并调整主图标
    icon = Image.open(icon_path).convert('RGBA')
    icon = icon.resize((64, 64), Image.Resampling.LANCZOS)
    
    # 合成主图标到背景
    background.paste(icon, (0, 0), icon)
    
    # 加载覆盖层并使用加法混合
    overlay = Image.open(overlay_path).convert('RGBA')
    background = image_add(background, overlay)
    
    # 如果有技术等级覆盖层
    if tech_icon_path:
        tech_overlay = Image.open(tech_icon_path).convert('RGBA')
        tech_overlay = tech_overlay.resize((16, 16), Image.Resampling.LANCZOS)
        background.paste(tech_overlay, (0, 0), tech_overlay)
    
    background.save(out_path, 'PNG')


def image_add(img1: Image.Image, img2: Image.Image) -> Image.Image:
    """图像加法混合（类似Photoshop的加法模式）
    
    正确实现加法混合，只对可见像素（alpha > 0）进行RGB加法。
    对应Rust版本的 pixel_add with blend_alpha=true, premultiply=false
    """
    # 转换为numpy数组
    arr1 = np.array(img1, dtype=np.float32)
    arr2 = np.array(img2, dtype=np.float32)
    
    # 分离RGB和Alpha通道
    rgb1 = arr1[:, :, :3]
    alpha1 = arr1[:, :, 3]
    rgb2 = arr2[:, :, :3]
    alpha2 = arr2[:, :, 3]
    
    # 归一化alpha到0-1范围
    alpha1_norm = alpha1 / 255.0
    alpha2_norm = alpha2 / 255.0
    
    # RGB通道加法混合：只对img2中不透明的像素进行加法
    # 使用img2的alpha作为权重
    result_rgb = rgb1 + rgb2 * (alpha2_norm[:, :, np.newaxis])
    result_rgb = np.clip(result_rgb, 0, 255)
    
    # Alpha通道混合：使用标准的over操作
    # alpha_out = alpha1 + alpha2 * (1 - alpha1)
    result_alpha_norm = alpha1_norm + alpha2_norm * (1.0 - alpha1_norm)
    result_alpha = np.clip(result_alpha_norm * 255.0, 0, 255)
    
    # 合并RGB和Alpha
    result = np.dstack([result_rgb, result_alpha]).astype(np.uint8)
    
    return Image.fromarray(result, 'RGBA')


def copy_or_convert(from_path: Path, to_path: Path, resource: str, extension: str):
    """复制或转换图像格式"""
    if resource.endswith(extension):
        shutil.copy(from_path, to_path)
    else:
        img = Image.open(from_path)
        if extension == '.png':
            img.save(to_path, 'PNG')
        elif extension in ['.jpg', '.jpeg']:
            img.save(to_path, 'JPEG')
        else:
            raise ValueError(f"未知的图像扩展名: {extension}")


class IconBuildData:
    """图标构建数据"""
    def __init__(self, types: Dict[int, TypeInfo], group_categories: Dict[int, int],
                 icon_files: Dict[int, str], graphics_folders: Dict[int, str],
                 skin_materials: Dict[int, int]):
        self.types = types
        self.group_categories = group_categories
        self.icon_files = icon_files
        self.graphics_folders = graphics_folders
        self.skin_materials = skin_materials


def build_icon_export(output_mode: str, skip_output_if_fresh: bool, data: IconBuildData,
                     cache: SharedCache, icon_dir: Path, force_rebuild: bool,
                     silent_mode: bool, log_file=None, out=None, show_progress: bool = True, 
                     skip_skins: bool = False, test_type_id: Optional[int] = None, **output_params) -> Tuple[int, int]:
    """构建图标导出"""
    
    icon_dir.mkdir(parents=True, exist_ok=True)
    
    # 加载旧的索引
    old_index = set()
    index_path = icon_dir / "cache.csv"
    if index_path.exists():
        content = index_path.read_bytes()
        for entry in content.split(b'\x1E'):
            if entry:
                old_index.add(entry.decode('utf-8'))
    
    service_metadata: Dict[int, Dict[IconKind, str]] = {}
    new_index: Set[str] = set()
    
    def is_up_to_date(filename: str) -> bool:
        """检查文件是否已是最新"""
        new_index.add(filename)
        return filename in old_index and not force_rebuild
    
    # 预处理：计算需要处理的物品数量
    processable_types = []
    for type_id, type_info in data.types.items():
        # 测试模式：只处理指定的type_id
        if test_type_id is not None and type_id != test_type_id:
            continue
        
        category_id = data.group_categories.get(type_info.group_id)
        if category_id is None:
            if not silent_mode:
                print(f"\t[!] 分组没有分类: {type_info.group_id}")
            continue
        
        # 跳过没有图标的物品（SKIN除外）
        if type_info.icon_id is None and type_info.graphic_id is None and category_id != 91:
            continue
        
        # 如果设置了跳过SKIN，则跳过SKIN类型（category_id == 91）
        if skip_skins and category_id in [91, 30, 2118]:
            continue
        
        processable_types.append((type_id, type_info, category_id))
    
    if hasattr(cache, "ensure_resources"):
        needed = collect_required_resources(data, cache, skip_skins, test_type_id)
        cache.ensure_resources(needed, label="图标资源")

    # 处理每个物品类型
    total_count = len(processable_types)
    processed_count = 0
    
    for type_id, type_info, category_id in processable_types:
        processed_count += 1
        
        # 每500个显示一次进度
        if show_progress and not silent_mode and processed_count % 500 == 0:
            percentage = (processed_count / total_count) * 100
            print(f"\t构建进度: {processed_count}/{total_count} ({percentage:.1f}%)")
            if log_file:
                log_file.write(f"\t构建进度: {processed_count}/{total_count} ({percentage:.1f}%)\n")
        
        if category_id == 9 or category_id == 34:
            # 蓝图或反应
            _process_blueprint(type_id, type_info, category_id, data, cache, icon_dir,
                             is_up_to_date, service_metadata, silent_mode, log_file)
        else:
            # 普通物品
            _process_regular_item(type_id, type_info, category_id, data, cache, icon_dir,
                                is_up_to_date, service_metadata, silent_mode, log_file)
    
    # 显示最终完成进度
    if show_progress and not silent_mode:
        print(f"\t构建完成: {processed_count}/{total_count} (100.0%)")
        if log_file:
            log_file.write(f"\t构建完成: {processed_count}/{total_count} (100.0%)\n")
    
    # 保存新索引
    index_bytes = b'\x1E'.join(filename.encode('utf-8') for filename in sorted(new_index))
    index_path.write_bytes(index_bytes)
    
    # 计算变更
    to_remove = [f for f in old_index if f not in new_index]
    to_add = [f for f in new_index if f not in old_index]
    
    # 生成输出
    if len(to_add) == 0 and len(to_remove) == 0 and skip_output_if_fresh:
        if not silent_mode:
            print("图标未变化，跳过输出...")
        if log_file:
            log_file.write("图标未变化，跳过输出...\n")
    else:
        if not silent_mode:
            print("图标已构建，生成输出...")
        if log_file:
            log_file.write("图标已构建，生成输出...\n")
        
        # 合并out参数到output_params（如果output_params中没有out参数）
        if out and 'out' not in output_params:
            output_params['out'] = out
        
        _generate_output(output_mode, output_params, icon_dir, new_index, 
                        service_metadata, old_index, force_rebuild, silent_mode, log_file, cache, data)
    
    # 删除旧文件
    for filename in to_remove:
        try:
            (icon_dir / filename).unlink()
        except Exception:
            pass
    
    return len(to_add), len(to_remove)


def _process_blueprint(type_id: int, type_info: TypeInfo, category_id: int,
                      data: IconBuildData, cache: SharedCache, icon_dir: Path,
                      is_up_to_date, service_metadata: Dict, silent_mode: bool, log_file):
    """处理蓝图类型图标"""
    
    if type_info.graphic_id and type_info.graphic_id in data.graphics_folders:
        folder = data.graphics_folders[type_info.graphic_id].rstrip('/\\')
        icon_resource_bp = f"{folder}/{type_info.graphic_id}_64_bp.png"
        icon_resource_bpc = f"{folder}/{type_info.graphic_id}_64_bpc.png"
        
        if cache.has_resource(icon_resource_bp) and type_info.group_id not in USE_ICON_INSTEAD_OF_GRAPHIC_GROUPS:
            techicon = techicon_resource_for_metagroup(type_info.meta_group_id or 1)
            
            if techicon:
                filename = f"bp;{cache.hash_of(icon_resource_bp)};{cache.hash_of(techicon)}.png"
                service_metadata.setdefault(type_id, {})[IconKind.ICON] = filename
                service_metadata[type_id][IconKind.BLUEPRINT] = filename
                
                if not is_up_to_date(filename):
                    composite_tech(cache.path_of(icon_resource_bp), 
                                 cache.path_of(techicon),
                                 icon_dir / filename)
                
                if cache.has_resource(icon_resource_bpc):
                    filename = f"bpc;{cache.hash_of(icon_resource_bpc)};{cache.hash_of(techicon)}.png"
                    service_metadata[type_id][IconKind.BLUEPRINT_COPY] = filename
                    
                    if not is_up_to_date(filename):
                        composite_tech(cache.path_of(icon_resource_bpc),
                                     cache.path_of(techicon),
                                     icon_dir / filename)
            else:
                filename = f"bp;{cache.hash_of(icon_resource_bp)}.png"
                service_metadata.setdefault(type_id, {})[IconKind.ICON] = filename
                service_metadata[type_id][IconKind.BLUEPRINT] = filename
                
                if not is_up_to_date(filename):
                    copy_or_convert(cache.path_of(icon_resource_bp), icon_dir / filename,
                                  icon_resource_bp, '.png')
                
                if cache.has_resource(icon_resource_bpc):
                    filename = f"bpc;{cache.hash_of(icon_resource_bpc)}.png"
                    service_metadata[type_id][IconKind.BLUEPRINT_COPY] = filename
                    
                    if not is_up_to_date(filename):
                        copy_or_convert(cache.path_of(icon_resource_bpc), icon_dir / filename,
                                      icon_resource_bpc, '.png')
    
    elif type_info.icon_id and type_info.icon_id in data.icon_files:
        icon_resource = data.icon_files[type_info.icon_id]
        
        if cache.has_resource(icon_resource):
            tech_overlay = techicon_resource_for_metagroup(type_info.meta_group_id or 1)
            tech_hash = cache.hash_of(tech_overlay) if tech_overlay else ""
            
            if category_id == 34:
                # 遗迹
                filename = f"relic;{cache.hash_of(icon_resource)};{tech_hash}.png"
                service_metadata.setdefault(type_id, {})[IconKind.ICON] = filename
                service_metadata[type_id][IconKind.RELIC] = filename
                
                if not is_up_to_date(filename):
                    composite_blueprint(
                        cache.path_of("res:/ui/texture/icons/relic.png"),
                        cache.path_of("res:/ui/texture/icons/relic_overlay.png"),
                        cache.path_of(icon_resource),
                        cache.path_of(tech_overlay) if tech_overlay else None,
                        icon_dir / filename
                    )
            
            elif type_info.group_id in REACTION_GROUPS:
                # 反应
                filename = f"reaction;{cache.hash_of(icon_resource)};{tech_hash}.png"
                service_metadata.setdefault(type_id, {})[IconKind.ICON] = filename
                service_metadata[type_id][IconKind.REACTION] = filename
                service_metadata[type_id][IconKind.BLUEPRINT] = filename
                
                if not is_up_to_date(filename):
                    composite_blueprint(
                        cache.path_of("res:/ui/texture/icons/reaction.png"),
                        cache.path_of("res:/ui/texture/icons/bpo_overlay.png"),
                        cache.path_of(icon_resource),
                        cache.path_of(tech_overlay) if tech_overlay else None,
                        icon_dir / filename
                    )
            
            else:
                # 普通蓝图
                filename = f"bp;{cache.hash_of(icon_resource)};{tech_hash}.png"
                service_metadata.setdefault(type_id, {})[IconKind.ICON] = filename
                service_metadata[type_id][IconKind.BLUEPRINT] = filename
                
                if not is_up_to_date(filename):
                    composite_blueprint(
                        cache.path_of("res:/ui/texture/icons/bpo.png"),
                        cache.path_of("res:/ui/texture/icons/bpo_overlay.png"),
                        cache.path_of(icon_resource),
                        cache.path_of(tech_overlay) if tech_overlay else None,
                        icon_dir / filename
                    )
                
                # 蓝图副本
                filename = f"bpc;{cache.hash_of(icon_resource)};{tech_hash}.png"
                service_metadata[type_id][IconKind.BLUEPRINT_COPY] = filename
                
                if not is_up_to_date(filename):
                    composite_blueprint(
                        cache.path_of("res:/ui/texture/icons/bpc.png"),
                        cache.path_of("res:/ui/texture/icons/bpc_overlay.png"),
                        cache.path_of(icon_resource),
                        cache.path_of(tech_overlay) if tech_overlay else None,
                        icon_dir / filename
                    )
        else:
            if not silent_mode:
                print(f"\t[x] 缺失图标: {type_id}")
            if log_file:
                log_file.write(f"\t[x] 缺失图标: {type_id}\n")


def _process_regular_item(type_id: int, type_info: TypeInfo, category_id: int,
                         data: IconBuildData, cache: SharedCache, icon_dir: Path,
                         is_up_to_date, service_metadata: Dict, silent_mode: bool, log_file):
    """处理普通物品图标"""
    
    icon_resource = None
    
    # 尝试使用图形资源
    if type_info.graphic_id and type_info.graphic_id in data.graphics_folders:
        folder = data.graphics_folders[type_info.graphic_id].rstrip('/\\')
        icon_resource = f"{folder}/{type_info.graphic_id}_64.png"
        
        if not cache.has_resource(icon_resource) or type_info.group_id in USE_ICON_INSTEAD_OF_GRAPHIC_GROUPS:
            if type_info.icon_id and type_info.icon_id in data.icon_files:
                icon_resource = data.icon_files[type_info.icon_id]
            else:
                return
        
        # 处理高分辨率渲染图
        render_resource = f"{folder}/{type_info.graphic_id}_512.jpg"
        if cache.has_resource(render_resource):
            filename = f"{cache.hash_of(render_resource)}.jpg"
            service_metadata.setdefault(type_id, {})[IconKind.RENDER] = filename
            
            if not is_up_to_date(filename):
                copy_or_convert(cache.path_of(render_resource), icon_dir / filename,
                              render_resource, '.jpg')
    
    elif type_info.icon_id and type_info.icon_id in data.icon_files:
        icon_resource = data.icon_files[type_info.icon_id]
    
    elif category_id == 91:
        # SKIN
        if type_id in data.skin_materials:
            material_id = data.skin_materials[type_id]
            icon_resource = f"res:/ui/texture/classes/skins/icons/{material_id}.png"
        else:
            return
    else:
        return
    
    # 处理主图标
    if icon_resource and cache.has_resource(icon_resource):
        techicon = techicon_resource_for_metagroup(type_info.meta_group_id or 1)
        
        if techicon:
            filename = f"{cache.hash_of(icon_resource)};{cache.hash_of(techicon)}.png"
            service_metadata.setdefault(type_id, {})[IconKind.ICON] = filename
            
            if not is_up_to_date(filename):
                composite_tech(cache.path_of(icon_resource),
                             cache.path_of(techicon),
                             icon_dir / filename)
        else:
            filename = f"{cache.hash_of(icon_resource)}.png"
            service_metadata.setdefault(type_id, {})[IconKind.ICON] = filename
            
            if not is_up_to_date(filename):
                copy_or_convert(cache.path_of(icon_resource), icon_dir / filename,
                              icon_resource, '.png')
    else:
        if not silent_mode:
            print(f"\t[x] 缺失图标: {type_id}")
        if log_file:
            log_file.write(f"\t[x] 缺失图标: {type_id}\n")


def _generate_output(output_mode: str, output_params: dict, icon_dir: Path,
                    new_index: Set[str], service_metadata: Dict,
                    old_index: Set[str], force_rebuild: bool, silent_mode: bool, log_file,
                    cache: SharedCache, data: IconBuildData):
    """生成输出文件"""
    
    if output_mode == 'service_bundle':
        out_path = Path(output_params['out'])
        # 确保输出目录存在
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if log_file:
            log_file.write(f"写入服务包到 {out_path}\n")
        
        with ZipFile(out_path, 'w', ZIP_STORED) as zf:
            for filename in new_index:
                if log_file:
                    log_file.write(f"\t{filename}\n")
                zf.write(icon_dir / filename, filename)
            
            # 写入元数据
            metadata_json = {}
            for type_id, icons in service_metadata.items():
                metadata_json[type_id] = {kind.value: filename for kind, filename in icons.items()}
            
            zf.writestr('service_metadata.json', json.dumps(metadata_json, indent=2))
    
    elif output_mode == 'iec':
        out_path = Path(output_params['out'])
        # 确保输出目录存在
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if log_file:
            log_file.write(f"写入IEC归档到 {out_path}\n")

        # 去重：相同源文件(hash)的图标共享首个 type 的输出文件名
        hash_to_output: Dict[str, str] = {}
        icon_index: Dict[str, str] = {}

        with ZipFile(out_path, 'w', ZIP_STORED) as zf:
            for type_id, icons in service_metadata.items():
                if IconKind.ICON not in icons:
                    continue
                filename = icons[IconKind.ICON]
                if filename not in hash_to_output:
                    output_name = f"type_{type_id}.png"
                    hash_to_output[filename] = output_name
                    if log_file:
                        log_file.write(f"\t{filename} -> {output_name}\n")
                    zf.write(icon_dir / filename, output_name)
                icon_index[str(type_id)] = hash_to_output[filename]

            # 写入图标索引（type_id → 文件名映射）
            zf.writestr('icon_index.json', json.dumps(icon_index, ensure_ascii=False))

        if not silent_mode:
            print(f"\t输出 {len(hash_to_output)} 个唯一图标，索引 {len(icon_index)} 个映射")
    
    elif output_mode == 'web_dir':
        out_dir = Path(output_params['out'])
        # 确保输出目录存在
        out_dir.mkdir(parents=True, exist_ok=True)
        copy_files = output_params.get('copy_files', False)
        hard_link = output_params.get('hard_link', False)
        
        mode_name = "复制" if copy_files else ("硬链接" if hard_link else "符号链接")
        if log_file:
            log_file.write(f"构建Web目录到 {out_dir} ({mode_name})\n")
        
        created_files = {}
        index_path = out_dir / 'index.json'
        
        old_links = {}
        if index_path.exists():
            with open(index_path, 'r') as f:
                old_links = json.load(f)
        
        for type_id, icons in service_metadata.items():
            # 写入类型的JSON元数据
            json_name = f"{type_id}.json"
            json_content = json.dumps([kind.value for kind in icons.keys()])
            
            if force_rebuild or old_links.get(json_name) != json_content:
                (out_dir / json_name).write_text(json_content)
            
            created_files[json_name] = json_content
            
            # 创建图标文件链接
            for icon_kind, filename in icons.items():
                ext = 'jpg' if icon_kind == IconKind.RENDER else 'png'
                link_name = f"{type_id}_{icon_kind.value}.{ext}"
                link_source = (icon_dir / filename).resolve()
                link_file = (out_dir / link_name).resolve()
                
                if force_rebuild or old_links.get(link_name) != filename:
                    if log_file:
                        log_file.write(f"\t{filename} -> {link_name}\n")
                    
                    if copy_files:
                        shutil.copy(link_source, link_file)
                    elif hard_link:
                        if link_file.exists():
                            link_file.unlink()
                        os.link(link_source, link_file)
                    else:
                        if link_file.exists():
                            link_file.unlink()
                        os.symlink(link_source, link_file)
                else:
                    if log_file:
                        log_file.write(f"\t跳过: {link_name}\n")
                
                created_files[link_name] = filename
        
        # 删除旧文件
        for entry in old_links.keys():
            if entry not in created_files:
                if log_file:
                    log_file.write(f"\t删除: {entry}\n")
                try:
                    (out_dir / entry).unlink()
                except Exception:
                    pass
        
        # 保存索引
        with open(index_path, 'w') as f:
            json.dump(created_files, f)
    
    elif output_mode == 'checksum':
        index_bytes = b'\x1E'.join(f.encode('utf-8') for f in sorted(new_index))
        checksum = hashlib.md5(index_bytes).hexdigest()
        
        if log_file:
            log_file.write(f"校验和: {checksum}\n")
        
        out_path = output_params.get('out')
        if out_path:
            out_path = Path(out_path)
            # 确保输出目录存在
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(checksum)
        else:
            print(checksum, end='')
    
    elif output_mode == 'aux_icons':
        out_path = Path(output_params['out'])
        # 确保输出目录存在
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if log_file:
            log_file.write(f"写入辅助图标转储到 {out_path}\n")
        
        with ZipFile(out_path, 'w', ZIP_STORED) as zf:
            for icon_id, resource in data.icon_files.items():
                parts = resource.rsplit('.', 1)
                if len(parts) == 2:
                    extension = parts[1]
                else:
                    extension = resource.rsplit('/', 1)[-1]
                
                if log_file:
                    log_file.write(f"\t{icon_id}: {resource}\n")
                
                try:
                    resource_path = cache.path_of(resource)
                    zf.write(resource_path, f"{icon_id}.{extension}")
                except Exception:
                    pass
    
    elif output_mode == 'aux_all':
        out_path = Path(output_params['out'])
        # 确保输出目录存在
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if log_file:
            log_file.write(f"写入所有图像转储到 {out_path}\n")
        
        with ZipFile(out_path, 'w', ZIP_STORED) as zf:
            for resource in cache.iter_resources():
                if resource.endswith('png') or resource.endswith('jpg'):
                    parts = resource.split(':/', 1)
                    filename = parts[1] if len(parts) == 2 else resource
                    
                    if log_file:
                        log_file.write(f"\t{resource}\n")
                    
                    resource_path = cache.path_of(resource)
                    zf.write(resource_path, filename)
