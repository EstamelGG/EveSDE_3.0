#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
物品变更分析器
用于分析新增物品、属性变更、蓝图变更等，生成详细的变更报告
完全按照 tmp 项目的格式生成
从 JSONL 文件读取数据，而不是从数据库
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from collections import defaultdict
import scripts.jsonl_loader as jsonl_loader


class ItemChangesAnalyzer:
    """物品变更分析器"""
    
    def __init__(self, config: Dict[str, Any], old_jsonl_path: Path, current_jsonl_path: Path):
        """初始化分析器
        
        Args:
            config: 配置字典
            old_jsonl_path: 旧版本 JSONL 文件目录路径
            current_jsonl_path: 当前版本 JSONL 文件目录路径
        """
        self.config = config
        self.old_jsonl_path = old_jsonl_path
        self.current_jsonl_path = current_jsonl_path
        self.project_root = Path(__file__).parent.parent
        
        # 缓存数据
        self.current_types_data = {}
        self.old_types_data = {}
        self.current_groups_data = {}
        self.old_groups_data = {}
        self.current_categories_data = {}
        self.old_categories_data = {}
        self.current_blueprints_data = {}
        self.old_blueprints_data = {}
        self.current_typedogma_data = {}
        self.old_typedogma_data = {}
        self.current_dogma_attributes_data = {}
    
    def load_jsonl_dict(self, file_path: Path) -> Dict[str, Any]:
        """加载 JSONL 文件并返回字典（使用 _key 作为键，兼容 id）"""
        if not file_path.exists():
            return {}
        
        data = {}
        try:
            items = jsonl_loader.load_jsonl(str(file_path))
            for item in items:
                # 优先使用 _key，如果没有则使用 id
                key = item.get('_key') or item.get('id')
                if key:
                    data[str(key)] = item
        except Exception as e:
            print(f"[!] 加载文件失败 {file_path}: {e}")
        
        return data
    
    def load_all_data(self):
        """加载所有需要的数据"""
        print("[+] 加载当前版本 JSONL 数据...")
        self.current_types_data = self.load_jsonl_dict(self.current_jsonl_path / "types.jsonl")
        self.current_groups_data = self.load_jsonl_dict(self.current_jsonl_path / "groups.jsonl")
        self.current_categories_data = self.load_jsonl_dict(self.current_jsonl_path / "categories.jsonl")
        self.current_blueprints_data = self.load_jsonl_dict(self.current_jsonl_path / "blueprints.jsonl")
        self.current_typedogma_data = self.load_jsonl_dict(self.current_jsonl_path / "typeDogma.jsonl")
        self.current_dogma_attributes_data = self.load_jsonl_dict(self.current_jsonl_path / "dogmaAttributes.jsonl")
        
        print("[+] 加载旧版本 JSONL 数据...")
        self.old_types_data = self.load_jsonl_dict(self.old_jsonl_path / "types.jsonl")
        self.old_groups_data = self.load_jsonl_dict(self.old_jsonl_path / "groups.jsonl")
        self.old_categories_data = self.load_jsonl_dict(self.old_jsonl_path / "categories.jsonl")
        self.old_blueprints_data = self.load_jsonl_dict(self.old_jsonl_path / "blueprints.jsonl")
        self.old_typedogma_data = self.load_jsonl_dict(self.old_jsonl_path / "typeDogma.jsonl")
        
        print(f"[+] 数据加载完成")
        print(f"    - 当前版本 Types: {len(self.current_types_data)}")
        print(f"    - 旧版本 Types: {len(self.old_types_data)}")
        print(f"    - 当前版本 Blueprints: {len(self.current_blueprints_data)}")
        print(f"    - 旧版本 Blueprints: {len(self.old_blueprints_data)}")
    
    def get_type_name(self, type_id: str, types_data: Dict[str, Any]) -> str:
        """获取物品名称"""
        if type_id not in types_data:
            return f"TypeID {type_id}"
        
        type_data = types_data[type_id]
        name_data = type_data.get('name', {})
        
        if isinstance(name_data, dict):
            return name_data.get('zh') or name_data.get('en', f"TypeID {type_id}")
        else:
            return str(name_data) if name_data else f"TypeID {type_id}"
    
    def get_attribute_name(self, attribute_id: str) -> str:
        """获取属性名称，优先级：displayName.zh > displayName.en > name"""
        if attribute_id not in self.current_dogma_attributes_data:
            return f"AttributeID {attribute_id}"
        
        attr_data = self.current_dogma_attributes_data[attribute_id]
        
        # 优先使用 displayName 字段（多语言字典）
        display_name = attr_data.get('displayName', {})
        if isinstance(display_name, dict):
            # 优先使用中文
            if 'zh' in display_name and display_name['zh']:
                return display_name['zh']
            # 其次使用英文
            if 'en' in display_name and display_name['en']:
                return display_name['en']
            # 如果字典中有其他语言，使用第一个非空值
            for lang, value in display_name.items():
                if value:
                    return value
        
        # 最后使用 name 字段
        if 'name' in attr_data and attr_data['name']:
            return attr_data['name']
        
        return f"AttributeID {attribute_id}"
    
    def analyze_new_items(self, target_categories: Set[int] = None) -> List[Dict[str, Any]]:
        """分析所有新增物品，获取类别和组别信息，对指定类别的物品收集属性信息"""
        if target_categories is None:
            target_categories = {4, 6, 7, 18, 20, 65, 66, 87}
        
        print("[+] 分析新增物品...")
        
        # 找出新增的 types
        added_types = {}
        for type_id in self.current_types_data:
            if type_id not in self.old_types_data:
                added_types[type_id] = self.current_types_data[type_id]
        
        new_items = []
        
        for type_id, type_data in added_types.items():
            # 获取物品名称
            name_data = type_data.get('name', {})
            if isinstance(name_data, dict):
                item_name = name_data.get('zh') or name_data.get('en', f"TypeID {type_id}")
            else:
                item_name = f"TypeID {type_id}"
            
            # 获取物品描述
            description_data = type_data.get('description', {})
            if isinstance(description_data, dict):
                raw_description = description_data.get('zh') or description_data.get('en', '')
            else:
                raw_description = ''
            
            # 格式化描述：清除HTML标签、换行符和多余空白
            if raw_description:
                clean_description = re.sub(r'<[^>]+>', '', raw_description)
                item_description = ' '.join(clean_description.split())
            else:
                item_description = ''
            
            # 获取组别信息
            group_id = type_data.get('groupID')
            group_name = '未知组别'
            category_name = '未知类别'
            category_id = None
            
            if group_id and str(group_id) in self.current_groups_data:
                group_data = self.current_groups_data[str(group_id)]
                group_name_data = group_data.get('name', {})
                if isinstance(group_name_data, dict):
                    group_name = group_name_data.get('zh') or group_name_data.get('en', f"GroupID {group_id}")
                else:
                    group_name = str(group_name_data) if group_name_data else f"GroupID {group_id}"
                
                # 获取类别信息
                category_id = group_data.get('categoryID')
                if category_id is not None and str(category_id) in self.current_categories_data:
                    category_data = self.current_categories_data[str(category_id)]
                    category_name_data = category_data.get('name', {})
                    if isinstance(category_name_data, dict):
                        category_name = category_name_data.get('zh') or category_name_data.get('en', f"CategoryID {category_id}")
                    else:
                        category_name = str(category_name_data) if category_name_data else f"CategoryID {category_id}"
            
            item_info = {
                'name': item_name,
                'description': item_description,
                'type_id': type_id,
                'group_id': group_id,
                'category_id': category_id,
                'group_name': group_name,
                'category_name': category_name
            }
            
            # 只对指定类别的物品收集属性信息
            if category_id in target_categories:
                # 从完整的 typedogma_data 获取
                item_typedogma = self.current_typedogma_data.get(type_id, {})
                
                if item_typedogma:
                    attributes = []
                    dogma_attributes = item_typedogma.get('dogmaAttributes', [])
                    
                    for attr in dogma_attributes:
                        attribute_id = str(attr.get('attributeID'))
                        attribute_value = attr.get('value', 0)
                        
                        # 跳过值为 0 的属性（通常表示未设置）
                        if attribute_value == 0:
                            continue
                        
                        # 获取属性名称
                        attribute_name = self.get_attribute_name(attribute_id)
                        
                        # 格式化数值显示
                        if isinstance(attribute_value, float) and attribute_value.is_integer():
                            attribute_value = int(attribute_value)
                        
                        attributes.append({
                            'attributeID': attribute_id,
                            'attributeName': attribute_name,
                            'value': attribute_value
                        })
                    
                    # 按属性名称排序
                    attributes.sort(key=lambda x: x['attributeName'])
                    item_info['attributes'] = attributes
                else:
                    item_info['attributes'] = []
            else:
                # 非目标类别，不收集属性
                item_info['attributes'] = None
            
            new_items.append(item_info)
        
        return new_items
    
    def compare_typedogma_attributes(self, old_typedogma: Dict, new_typedogma: Dict) -> List[Dict]:
        """比对 typeDogma 中 dogmaAttributes 的变化"""
        changes = []
        
        # 将属性列表转换为字典，方便比对
        old_attrs = {}
        if old_typedogma and 'dogmaAttributes' in old_typedogma:
            for attr in old_typedogma['dogmaAttributes']:
                old_attrs[str(attr.get('attributeID'))] = attr.get('value', 0)
        
        new_attrs = {}
        if new_typedogma and 'dogmaAttributes' in new_typedogma:
            for attr in new_typedogma['dogmaAttributes']:
                new_attrs[str(attr.get('attributeID'))] = attr.get('value', 0)
        
        # 获取所有属性ID
        all_attr_ids = set(old_attrs.keys()) | set(new_attrs.keys())
        
        for attr_id in all_attr_ids:
            # 检查属性是否在旧版本中存在（不仅仅是值是否为 0）
            is_new_attribute = attr_id not in old_attrs
            old_value = old_attrs.get(attr_id, 0)
            new_value = new_attrs.get(attr_id, 0)
            
            # 只关注有变化的属性
            if old_value != new_value:
                attr_name = self.get_attribute_name(attr_id)
                changes.append({
                    'attributeID': attr_id,
                    'attributeName': attr_name,
                    'oldValue': old_value,
                    'newValue': new_value,
                    'isNewAttribute': is_new_attribute
                })
        
        return changes
    
    def analyze_item_attribute_changes(self, target_categories: Set[int] = None) -> Dict[str, Any]:
        """分析物品属性变更"""
        if target_categories is None:
            target_categories = {4, 6, 7, 18, 20, 65, 66, 87}
        
        print(f"[+] 分析物品属性变更（关注类别: {target_categories}）...")
        
        items_with_changes = {}
        
        # 找出所有变更的物品
        all_type_ids = set(self.current_typedogma_data.keys()) | set(self.old_typedogma_data.keys())
        
        for type_id in all_type_ids:
            # 检查物品类别
            if type_id in self.current_types_data:
                type_data = self.current_types_data[type_id]
                group_id = type_data.get('groupID')
                if group_id and str(group_id) in self.current_groups_data:
                    group_data = self.current_groups_data[str(group_id)]
                    category_id = group_data.get('categoryID')
                    if category_id not in target_categories:
                        continue
            
            # 获取新旧属性数据
            old_typedogma = self.old_typedogma_data.get(type_id, {})
            new_typedogma = self.current_typedogma_data.get(type_id, {})
            
            # 如果两个版本都没有，跳过
            if not old_typedogma and not new_typedogma:
                continue
            
            # 比较属性
            changes = self.compare_typedogma_attributes(old_typedogma, new_typedogma)
            
            if changes:
                items_with_changes[type_id] = {
                    'type_id': type_id,
                    'changes': changes
                }
        
        return items_with_changes
    
    def analyze_blueprint_changes(self) -> Dict[str, Any]:
        """分析蓝图变更"""
        print("[+] 分析蓝图变更...")
        
        added_blueprints = {}
        removed_blueprints = {}
        changed_blueprints = {}
        
        # 找出新增的蓝图
        for blueprint_id in self.current_blueprints_data:
            if blueprint_id not in self.old_blueprints_data:
                added_blueprints[blueprint_id] = self.current_blueprints_data[blueprint_id]
        
        # 找出删除的蓝图
        for blueprint_id in self.old_blueprints_data:
            if blueprint_id not in self.current_blueprints_data:
                removed_blueprints[blueprint_id] = self.old_blueprints_data[blueprint_id]
        
        # 找出变更的蓝图
        for blueprint_id in self.current_blueprints_data:
            if blueprint_id in self.old_blueprints_data:
                old_blueprint = self.old_blueprints_data[blueprint_id]
                new_blueprint = self.current_blueprints_data[blueprint_id]
                
                if old_blueprint != new_blueprint:
                    changed_blueprints[blueprint_id] = new_blueprint
        
        return {
            'added': added_blueprints,
            'removed': removed_blueprints,
            'changed': changed_blueprints
        }
    
    def compare_activity_changes(self, old_activity: Dict, new_activity: Dict) -> Dict[str, List]:
        """比对活动（manufacturing 或 reaction）的变化"""
        changes = {
            'materials': [],
            'products': []
        }
        
        # 比对材料变化
        old_materials = {str(m.get('typeID')): m.get('quantity', 0) for m in old_activity.get('materials', [])}
        new_materials = {str(m.get('typeID')): m.get('quantity', 0) for m in new_activity.get('materials', [])}
        
        all_material_ids = set(old_materials.keys()) | set(new_materials.keys())
        for material_id in all_material_ids:
            old_qty = old_materials.get(material_id, 0)
            new_qty = new_materials.get(material_id, 0)
            
            if old_qty != new_qty:
                material_name = self.get_type_name(material_id, self.current_types_data)
                changes['materials'].append({
                    'name': material_name,
                    'change': f"{old_qty} -> {new_qty}",
                    'oldValue': old_qty,
                    'newValue': new_qty
                })
        
        # 比对产品变化
        old_products = {str(p.get('typeID')): p.get('quantity', 0) for p in old_activity.get('products', [])}
        new_products = {str(p.get('typeID')): p.get('quantity', 0) for p in new_activity.get('products', [])}
        
        all_product_ids = set(old_products.keys()) | set(new_products.keys())
        for product_id in all_product_ids:
            old_qty = old_products.get(product_id, 0)
            new_qty = new_products.get(product_id, 0)
            
            if old_qty != new_qty:
                product_name = self.get_type_name(product_id, self.current_types_data)
                changes['products'].append({
                    'name': product_name,
                    'change': f"{old_qty} -> {new_qty}",
                    'oldValue': old_qty,
                    'newValue': new_qty
                })
        
        return changes
    
    def analyze_blueprint_changes_detail(self, blueprint_id: str, old_blueprint: Dict, new_blueprint: Dict) -> Dict[str, Any]:
        """分析单个蓝图的变化"""
        changes = {
            'manufacturing': {
                'materials': [],
                'products': []
            },
            'reaction': {
                'materials': [],
                'products': []
            }
        }
        
        old_activities = old_blueprint.get('activities', {})
        new_activities = new_blueprint.get('activities', {})
        
        # 比对 manufacturing 活动
        old_manufacturing = old_activities.get('manufacturing', {})
        new_manufacturing = new_activities.get('manufacturing', {})
        
        if old_manufacturing or new_manufacturing:
            manufacturing_changes = self.compare_activity_changes(old_manufacturing, new_manufacturing)
            changes['manufacturing']['materials'] = manufacturing_changes['materials']
            changes['manufacturing']['products'] = manufacturing_changes['products']
        
        # 比对 reaction 活动
        old_reaction = old_activities.get('reaction', {})
        new_reaction = new_activities.get('reaction', {})
        
        if old_reaction or new_reaction:
            reaction_changes = self.compare_activity_changes(old_reaction, new_reaction)
            changes['reaction']['materials'] = reaction_changes['materials']
            changes['reaction']['products'] = reaction_changes['products']
        
        return changes
    
    def find_blueprints_for_ships(self, new_ships: Dict[str, Any]) -> Dict[str, Any]:
        """为新飞船查找相关蓝图"""
        ship_blueprints = {}
        
        for ship_id, ship_data in new_ships.items():
            # 在蓝图中查找制造该飞船的蓝图
            blueprint_found = False
            for blueprint_id, blueprint_data in self.current_blueprints_data.items():
                activities = blueprint_data.get('activities', {})
                if 'manufacturing' in activities:
                    manufacturing = activities['manufacturing']
                    if 'products' in manufacturing:
                        for product in manufacturing['products']:
                            if str(product.get('typeID')) == str(ship_id):
                                # 找到制造该飞船的蓝图
                                blueprint_found = True
                                ship_blueprints[ship_id] = {
                                    'blueprint_id': blueprint_id,
                                    'blueprint_data': blueprint_data,
                                    'materials': manufacturing.get('materials', [])
                                }
                                break
                if blueprint_found:
                    break
            
            if not blueprint_found:
                ship_blueprints[ship_id] = {
                    'blueprint_id': None,
                    'blueprint_data': None,
                    'materials': [],
                    'status': '未找到蓝图'
                }
        
        return ship_blueprints
    
    def get_material_names(self, materials: List[Dict]) -> List[Dict]:
        """获取材料名称"""
        material_info = []
        
        for material in materials:
            type_id = str(material.get('typeID'))
            quantity = material.get('quantity', 0)
            
            material_name = self.get_type_name(type_id, self.current_types_data)
            
            material_info.append({
                'name': material_name,
                'quantity': quantity,
                'typeID': type_id
            })
        
        return material_info
    
    def create_blueprint_comparison_markdown(self, added_blueprints: Dict, removed_blueprints: Dict, 
                                             changed_blueprints: Dict) -> str:
        """创建蓝图比对的 Markdown 内容"""
        lines = []
        
        lines.append("# 蓝图变更\n\n")
        
        # 新增蓝图
        if added_blueprints:
            lines.append("## 新增蓝图\n\n")
            for blueprint_id, blueprint_data in sorted(added_blueprints.items()):
                # 获取蓝图名称（通过 blueprintTypeID）
                blueprint_type_id = str(blueprint_data.get('blueprintTypeID', blueprint_id))
                blueprint_name = self.get_type_name(blueprint_type_id, self.current_types_data)
                lines.append(f"### {blueprint_name} (Blueprint ID: {blueprint_id})\n\n")
                
                # 获取 activities 信息
                activities = blueprint_data.get('activities', {})
                
                # 显示 manufacturing 活动
                manufacturing = activities.get('manufacturing', {})
                if manufacturing:
                    lines.append("**制造活动 (Manufacturing):**\n")
                    # 材料
                    materials = manufacturing.get('materials', [])
                    if materials:
                        lines.append("  - 材料:\n")
                        for material in materials:
                            material_name = self.get_type_name(str(material.get('typeID')), self.current_types_data)
                            quantity = material.get('quantity', 0)
                            lines.append(f"    - {material_name} × {quantity}\n")
                    
                    # 产品
                    products = manufacturing.get('products', [])
                    if products:
                        lines.append("  - 输出物品:\n")
                        for product in products:
                            product_name = self.get_type_name(str(product.get('typeID')), self.current_types_data)
                            quantity = product.get('quantity', 0)
                            lines.append(f"    - {product_name} × {quantity}\n")
                    lines.append("\n")
                
                # 显示 reaction 活动
                reaction = activities.get('reaction', {})
                if reaction:
                    lines.append("**反应活动 (Reaction):**\n")
                    # 材料
                    materials = reaction.get('materials', [])
                    if materials:
                        lines.append("  - 材料:\n")
                        for material in materials:
                            material_name = self.get_type_name(str(material.get('typeID')), self.current_types_data)
                            quantity = material.get('quantity', 0)
                            lines.append(f"    - {material_name} × {quantity}\n")
                    
                    # 产品
                    products = reaction.get('products', [])
                    if products:
                        lines.append("  - 输出物品:\n")
                        for product in products:
                            product_name = self.get_type_name(str(product.get('typeID')), self.current_types_data)
                            quantity = product.get('quantity', 0)
                            lines.append(f"    - {product_name} × {quantity}\n")
                    lines.append("\n")
        else:
            lines.append("## 新增蓝图\n\n")
            lines.append("本次更新未发现新增蓝图。\n\n")
        
        # 改动蓝图
        if changed_blueprints:
            lines.append("## 蓝图变更\n\n")
            if not self.old_blueprints_data:
                lines.append("⚠️ 警告: 未找到旧版本蓝图数据，无法进行详细的变更比对。\n\n")
            
            for blueprint_id, new_blueprint_data in sorted(changed_blueprints.items()):
                # 获取旧蓝图数据
                old_blueprint_data = self.old_blueprints_data.get(blueprint_id, {}) if self.old_blueprints_data else {}
                
                blueprint_type_id = str(new_blueprint_data.get('blueprintTypeID', blueprint_id))
                blueprint_name = self.get_type_name(blueprint_type_id, self.current_types_data)
                lines.append(f"### {blueprint_name} (Blueprint ID: {blueprint_id})\n\n")
                
                if self.old_blueprints_data:
                    # 分析变化
                    changes = self.analyze_blueprint_changes_detail(blueprint_id, old_blueprint_data, new_blueprint_data)
                    
                    has_changes = False
                    
                    # 制造活动 (Manufacturing) 变化
                    manufacturing_changes = changes.get('manufacturing', {})
                    if manufacturing_changes.get('materials') or manufacturing_changes.get('products'):
                        has_changes = True
                        lines.append("**制造活动 (Manufacturing) 变更:**\n")
                        
                        # 材料变化
                        if manufacturing_changes['materials']:
                            lines.append("  - 材料变更:\n")
                            for material_change in manufacturing_changes['materials']:
                                lines.append(f"    - {material_change['name']}: {material_change['change']}\n")
                        
                        # 产品变化
                        if manufacturing_changes['products']:
                            lines.append("  - 输出物品变更:\n")
                            for product_change in manufacturing_changes['products']:
                                lines.append(f"    - {product_change['name']}: {product_change['change']}\n")
                        
                        lines.append("\n")
                    
                    # 反应活动 (Reaction) 变化
                    reaction_changes = changes.get('reaction', {})
                    if reaction_changes.get('materials') or reaction_changes.get('products'):
                        has_changes = True
                        lines.append("**反应活动 (Reaction) 变更:**\n")
                        
                        # 材料变化
                        if reaction_changes['materials']:
                            lines.append("  - 材料变更:\n")
                            for material_change in reaction_changes['materials']:
                                lines.append(f"    - {material_change['name']}: {material_change['change']}\n")
                        
                        # 产品变化
                        if reaction_changes['products']:
                            lines.append("  - 输出物品变更:\n")
                            for product_change in reaction_changes['products']:
                                lines.append(f"    - {product_change['name']}: {product_change['change']}\n")
                        
                        lines.append("\n")
                    
                    # 如果没有材料或产品变化，但蓝图确实改变了，说明可能是其他字段变化
                    if not has_changes:
                        lines.append("蓝图配置已变更（非制造/反应活动变化）\n\n")
                else:
                    # 没有旧版本数据时，只显示当前版本的配置
                    activities = new_blueprint_data.get('activities', {})
                    
                    # 显示 manufacturing 活动
                    manufacturing = activities.get('manufacturing', {})
                    if manufacturing:
                        lines.append("**制造活动 (Manufacturing):**\n")
                        materials = manufacturing.get('materials', [])
                        if materials:
                            lines.append("  - 材料:\n")
                            for material in materials:
                                material_name = self.get_type_name(str(material.get('typeID')), self.current_types_data)
                                quantity = material.get('quantity', 0)
                                lines.append(f"    - {material_name} × {quantity}\n")
                        
                        products = manufacturing.get('products', [])
                        if products:
                            lines.append("  - 输出物品:\n")
                            for product in products:
                                product_name = self.get_type_name(str(product.get('typeID')), self.current_types_data)
                                quantity = product.get('quantity', 0)
                                lines.append(f"    - {product_name} × {quantity}\n")
                        lines.append("\n")
                    
                    # 显示 reaction 活动
                    reaction = activities.get('reaction', {})
                    if reaction:
                        lines.append("**反应活动 (Reaction):**\n")
                        materials = reaction.get('materials', [])
                        if materials:
                            lines.append("  - 材料:\n")
                            for material in materials:
                                material_name = self.get_type_name(str(material.get('typeID')), self.current_types_data)
                                quantity = material.get('quantity', 0)
                                lines.append(f"    - {material_name} × {quantity}\n")
                        
                        products = reaction.get('products', [])
                        if products:
                            lines.append("  - 输出物品:\n")
                            for product in products:
                                product_name = self.get_type_name(str(product.get('typeID')), self.current_types_data)
                                quantity = product.get('quantity', 0)
                                lines.append(f"    - {product_name} × {quantity}\n")
                        lines.append("\n")
        else:
            lines.append("## 蓝图变更\n\n")
            lines.append("本次更新未发现蓝图变更。\n\n")
        
        return ''.join(lines)
    
    def create_attribute_changes_markdown(self, items_with_changes: Dict[str, Any]) -> str:
        """创建属性变化比对的 Markdown 内容"""
        lines = []
        
        lines.append("# 物品属性变更\n\n")
        
        if not items_with_changes:
            lines.append("本次更新未发现物品属性变更。\n\n")
        else:
            for type_id, item_info in sorted(items_with_changes.items()):
                # 获取物品名称
                item_name = self.get_type_name(type_id, self.current_types_data)
                lines.append(f"## {item_name}\n\n")
                
                # 列出所有属性变化
                for change in item_info['changes']:
                    attr_name = change['attributeName']
                    old_value = change['oldValue']
                    new_value = change['newValue']
                    is_new_attribute = change.get('isNewAttribute', False)
                    
                    # 格式化数值显示
                    if isinstance(old_value, float) and old_value.is_integer():
                        old_value = int(old_value)
                    if isinstance(new_value, float) and new_value.is_integer():
                        new_value = int(new_value)
                    
                    # 如果是新增的属性类型，显示更清晰
                    if is_new_attribute:
                        lines.append(f"- {attr_name}: 新增属性 (值: {new_value})\n")
                    else:
                        lines.append(f"- {attr_name}: {old_value} -> {new_value}\n")
                
                lines.append("\n")
        
        return ''.join(lines)
    
    def create_blueprint_analysis(self, new_ships: Dict[str, Any], ship_blueprints: Dict[str, Any]) -> List[Dict]:
        """创建蓝图分析报告"""
        analysis = []
        
        for ship_id, ship_data in new_ships.items():
            ship_name_data = ship_data.get('name', {})
            if isinstance(ship_name_data, dict):
                ship_name = ship_name_data.get('zh') or ship_name_data.get('en', f"TypeID {ship_id}")
            else:
                ship_name = f"TypeID {ship_id}"
            
            ship_info = {
                'ship_id': ship_id,
                'ship_name': ship_name,
                'blueprint_info': ship_blueprints.get(ship_id, {})
            }
            
            if ship_blueprints.get(ship_id, {}).get('status') == '未找到蓝图':
                ship_info['materials'] = []
                ship_info['status'] = '未找到蓝图'
            else:
                materials = ship_blueprints[ship_id].get('materials', [])
                ship_info['materials'] = self.get_material_names(materials)
                ship_info['status'] = '找到蓝图'
            
            analysis.append(ship_info)
        
        return analysis
    
    def generate_markdown_report(self, output_path: Path) -> bool:
        """生成 Markdown 格式的变更报告（完全按照 tmp 项目的格式）"""
        try:
            print("[+] 生成变更报告...")
            
            # 加载所有数据
            self.load_all_data()
            
            # 分析新增物品
            target_categories = {4, 6, 7, 18, 20, 65, 66, 87}
            all_new_items = self.analyze_new_items(target_categories)
            
            # 分析新增飞船（categoryID == 6）
            new_ships = {}
            for item in all_new_items:
                if item.get('category_id') == 6:
                    type_id = item.get('type_id')
                    if type_id in self.current_types_data:
                        new_ships[type_id] = self.current_types_data[type_id]
            
            # 查找新飞船的蓝图
            ship_blueprints = self.find_blueprints_for_ships(new_ships)
            blueprint_analysis = self.create_blueprint_analysis(new_ships, ship_blueprints)
            
            # 分析蓝图变更
            blueprint_changes = self.analyze_blueprint_changes()
            
            # 分析物品属性变更
            items_with_attribute_changes = self.analyze_item_attribute_changes(target_categories)
            
            # 生成报告（完全按照 tmp 项目的格式）
            lines = []
            lines.append("# 新增物品\n\n")
            
            if not all_new_items:
                lines.append("本次更新未发现新增物品。\n\n")
            else:
                # 按 categoryID 和 groupID 分组
                grouped_items = {}
                for item in all_new_items:
                    category_id = item.get('category_id', 999)  # 未知类别排在最后
                    group_id = item.get('group_id', 999)  # 未知组别排在最后
                    
                    if category_id not in grouped_items:
                        grouped_items[category_id] = {}
                    if group_id not in grouped_items[category_id]:
                        grouped_items[category_id][group_id] = []
                    
                    grouped_items[category_id][group_id].append(item)
                
                # 按 categoryID 排序并输出
                for category_id in sorted(grouped_items.keys()):
                    category_items = grouped_items[category_id]
                    
                    # 获取类别名称（从第一个物品中获取）
                    first_item = next(iter(category_items.values()))[0]
                    category_display_name = first_item.get('category_name', '未知类别')
                    
                    lines.append(f"## {category_display_name}\n\n")
                    
                    # 按 groupID 排序并输出
                    for group_id in sorted(category_items.keys()):
                        group_items = category_items[group_id]
                        
                        # 获取组别名称
                        group_display_name = group_items[0].get('group_name', '未知组别')
                        
                        lines.append(f"### {group_display_name}\n\n")
                        
                        # 输出该组别的所有物品
                        for item in group_items:
                            description = item.get('description', '')
                            attributes = item.get('attributes')
                            
                            if description:
                                lines.append(f"- **{item['name']}**\n")
                                lines.append(f"  - {description}\n")
                            else:
                                lines.append(f"- **{item['name']}**\n")
                            
                            # 如果是目标类别且有属性信息，显示属性
                            if attributes is not None and attributes:
                                lines.append(f"  - 属性:\n")
                                for attr in attributes:
                                    attr_name = attr.get('attributeName', f"AttributeID {attr.get('attributeID')}")
                                    attr_value = attr.get('value', 0)
                                    lines.append(f"    - {attr_name}: {attr_value}\n")
                            
                            lines.append("\n")
            
            lines.append("# 新增飞船\n\n")
            
            if not blueprint_analysis:
                lines.append("本次更新未发现新飞船。\n")
            else:
                for ship_info in blueprint_analysis:
                    lines.append(f"## {ship_info['ship_name']}\n")
                    
                    if ship_info['status'] == "未找到蓝图":
                        lines.append("- 未找到蓝图\n")
                    else:
                        for material in ship_info['materials']:
                            lines.append(f"- {material['name']} × {material['quantity']}\n")
                    lines.append("\n")
            
            # 添加蓝图比对部分
            lines.append("\n")
            blueprint_comparison = self.create_blueprint_comparison_markdown(
                blueprint_changes['added'],
                blueprint_changes['removed'],
                blueprint_changes['changed']
            )
            lines.append(blueprint_comparison)
            
            # 添加物品属性变更部分
            lines.append("\n")
            attribute_changes = self.create_attribute_changes_markdown(items_with_attribute_changes)
            lines.append(attribute_changes)
            
            # 保存报告
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(''.join(lines))
            
            print(f"[+] 变更报告已生成: {output_path}")
            return True
            
        except Exception as e:
            print(f"[x] 生成报告失败: {e}")
            import traceback
            traceback.print_exc()
            return False


def main(config: Dict[str, Any], old_jsonl_path: Path, current_jsonl_path: Path, output_path: Path) -> bool:
    """主函数
    
    Args:
        config: 配置字典
        old_jsonl_path: 旧版本 JSONL 文件目录路径
        current_jsonl_path: 当前版本 JSONL 文件目录路径
        output_path: 输出文件路径
    """
    analyzer = ItemChangesAnalyzer(config, old_jsonl_path, current_jsonl_path)
    return analyzer.generate_markdown_report(output_path)


if __name__ == "__main__":
    # 测试代码
    import sys
    sys.path.append(str(Path(__file__).parent.parent))
    
    # 加载配置
    config_path = Path(__file__).parent.parent / "config.json"
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 测试
    old_path = Path("/tmp/old_jsonl")
    current_path = Path(config["paths"]["sde_jsonl"])
    output_path = Path("/tmp/item_changes_report.md")
    
    success = main(config, old_path, current_path, output_path)
    print(f"测试结果: {'成功' if success else '失败'}")
