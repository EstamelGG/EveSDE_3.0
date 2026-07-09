#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图标处理器模块
基于本地service_metadata.json处理EVE物品图标
"""

import json
import shutil
from pathlib import Path
from typing import List, Dict, Any
from PIL import Image
from scripts.jsonl_loader import load_jsonl


class IconProcessor:
    """EVE物品图标处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化图标处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.sde_input_path = self.project_root / config["paths"]["sde_input"]
        self.icons_input_path = self.project_root / config["paths"]["icons_input"]
        self.icons_output_path = self.project_root / config["paths"]["icons_output"]
        
        # 确保输出目录存在
        self.icons_output_path.mkdir(parents=True, exist_ok=True)
        
        # 统计信息
        self.stats = {
            'total_types': 0,
            'processed_success': 0,
            'partial_success': 0,
            'already_exists': 0,
            'not_found_in_metadata': 0,
            'file_not_found': 0,
            'process_failed': 0
        }
        
        # 记录示例
        self.examples = {
            'not_found_in_metadata': [],
            'file_not_found': [],
            'process_failed': []
        }
        
        # 加载service_metadata.json
        self.metadata = self.load_service_metadata()
    
    def load_service_metadata(self) -> Dict[str, Any]:
        """加载service_metadata.json文件"""
        print("[+] 加载service_metadata.json...")
        
        # 查找service_metadata.json文件
        metadata_files = list(self.icons_input_path.glob("**/service_metadata.json"))
        
        if not metadata_files:
            print(f"[x] 未找到service_metadata.json文件在: {self.icons_input_path}")
            return {}
        
        metadata_file = metadata_files[0]
        print(f"[+] 找到metadata文件: {metadata_file}")
        
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            # 转换键为整数
            int_metadata = {int(k): v for k, v in metadata.items() if k.isdigit()}
            print(f"[+] 加载了 {len(int_metadata)} 个Type ID的图标元数据")
            return int_metadata
            
        except Exception as e:
            print(f"[x] 加载service_metadata.json失败: {e}")
            return {}
    
    def get_type_ids_from_sde(self) -> List[int]:
        """从SDE的types.jsonl文件中获取所有Type IDs"""
        print("[+] 从SDE获取Type IDs...")
        
        types_file = self.sde_input_path / "types.jsonl"
        if not types_file.exists():
            print(f"[x] 未找到types.jsonl文件: {types_file}")
            return []
        
        # 使用我们的jsonl_loader加载数据
        types_data = load_jsonl(str(types_file))
        if not types_data:
            print("[x] types.jsonl文件为空或加载失败")
            return []
        
        # 提取所有type_id
        type_ids = []
        for item in types_data:
            if '_key' in item:
                type_ids.append(item['_key'])
        
        type_ids.sort()
        print(f"[+] 从SDE获取到 {len(type_ids)} 个Type ID")
        
        return type_ids
    
    
    def resize_image_to_64(self, image_path: Path, output_path: Path) -> bool:
        """将图片调整到64x64分辨率"""
        try:
            with Image.open(image_path) as img:
                # 如果已经是64x64，直接复制
                if img.size == (64, 64):
                    shutil.copy2(image_path, output_path)
                    return True
                
                # 调整到64x64
                resized_img = img.resize((64, 64), Image.Resampling.LANCZOS)
                resized_img.save(output_path, 'PNG', optimize=True)
                return True
                
        except Exception as e:
            print(f"\n[!] 调整图片尺寸失败 {image_path}: {e}")
            return False
    
    def find_icon_from_metadata(self, type_id: int, variant: str = 'icon') -> Path:
        """根据service_metadata.json查找图标文件"""
        if type_id not in self.metadata:
            return None
        
        type_metadata = self.metadata[type_id]
        if variant not in type_metadata:
            return None
        
        filename = type_metadata[variant]
        icon_path = self.icons_input_path / filename
        
        if icon_path.exists():
            return icon_path
        
        return None
    
    def process_icon(self, type_id: int) -> str:
        """处理单个图标"""
        # 检查metadata中是否有此type_id
        if type_id not in self.metadata:
            return 'not_in_metadata'
        
        # 尝试不同的变体
        variants = ['icon', 'bp', 'bpc']
        processed_count = 0
        failed_count = 0
        
        for variant in variants:
            # 根据变体确定输出文件名
            if variant == 'bpc':
                output_filename = f"type_{type_id}_bpc_64.png"
            else:
                output_filename = f"type_{type_id}_64.png"
            
            output_path = self.icons_output_path / output_filename
            
            # 如果文件已存在，跳过
            if output_path.exists():
                processed_count += 1
                continue
            
            # 查找图标文件
            icon_path = self.find_icon_from_metadata(type_id, variant)
            if icon_path:
                # 调整尺寸并保存
                if self.resize_image_to_64(icon_path, output_path):
                    processed_count += 1
                else:
                    failed_count += 1
        
        # 返回处理结果
        if processed_count > 0 and failed_count == 0:
            return 'success'
        elif processed_count > 0 and failed_count > 0:
            return 'partial_success'
        elif failed_count > 0:
            return 'failed'
        else:
            return 'file_not_found'
    
    def process_icons_batch(self, type_ids: List[int]):
        """批量处理图标"""
        if not self.icons_input_path.exists():
            print(f"[x] 图标输入目录不存在: {self.icons_input_path}")
            return
        
        if not self.metadata:
            print("[x] service_metadata.json未加载或为空")
            return
        
        print(f"[+] 开始处理图标...")
        
        for i, type_id in enumerate(type_ids, 1):
            if i % 1000 == 0:
                print(f"\r[+] 图标处理进度: {i}/{len(type_ids)} ({i/len(type_ids)*100:.1f}%)", end='', flush=True)
            
            result = self.process_icon(type_id)
            
            if result == 'success':
                self.stats['processed_success'] += 1
            elif result == 'partial_success':
                self.stats['partial_success'] += 1
            elif result == 'not_in_metadata':
                self.stats['not_found_in_metadata'] += 1
                if len(self.examples['not_found_in_metadata']) < 10:
                    self.examples['not_found_in_metadata'].append(type_id)
            elif result == 'file_not_found':
                self.stats['file_not_found'] += 1
                if len(self.examples['file_not_found']) < 10:
                    self.examples['file_not_found'].append(type_id)
            else:  # failed
                self.stats['process_failed'] += 1
                if len(self.examples['process_failed']) < 10:
                    self.examples['process_failed'].append(type_id)
        
        print(f"\n[+] 图标处理完成")

    def process_all_icons(self):
        """处理所有图标的主流程"""
        print("[+] 开始处理EVE物品图标")
        
        # 1. 获取Type IDs
        type_ids = self.get_type_ids_from_sde()
        if not type_ids:
            print("[x] 无法获取Type IDs，退出")
            return
        
        self.stats['total_types'] = len(type_ids)
        
        # 2. 批量处理图标
        self.process_icons_batch(type_ids)
        
        # 3. 输出统计信息
        print("\n" + "="*50)
        print("图标处理统计:")
        print(f"总Type数量: {self.stats['total_types']}")
        print(f"完全成功: {self.stats['processed_success']}")
        print(f"部分成功: {self.stats['partial_success']}")
        print(f"metadata中未找到: {self.stats['not_found_in_metadata']}")
        print(f"文件未找到: {self.stats['file_not_found']}")
        print(f"处理失败: {self.stats['process_failed']}")
        
        total_success = self.stats['processed_success'] + self.stats['partial_success']
        success_rate = total_success / self.stats['total_types'] * 100 if self.stats['total_types'] > 0 else 0
        print(f"成功率: {success_rate:.2f}%")
        
        # 显示示例
        if self.examples['not_found_in_metadata']:
            print(f"\n[!] metadata中未找到的Type ID示例: {self.examples['not_found_in_metadata']}")
        
        if self.examples['file_not_found']:
            print(f"[!] 文件未找到的Type ID示例: {self.examples['file_not_found']}")
        
        if self.examples['process_failed']:
            print(f"[!] 处理失败的Type ID示例: {self.examples['process_failed']}")
        
        print(f"\n[+] 图标已保存到: {self.icons_output_path}")


def main(config=None):
    """主函数"""
    print("[+] 图标处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建图标处理器并执行
    processor = IconProcessor(config)
    processor.process_all_icons()
    
    print("\n[+] 图标处理器完成")


if __name__ == "__main__":
    main()
