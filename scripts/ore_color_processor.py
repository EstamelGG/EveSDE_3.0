#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
矿石主题色提取器
从types表中提取所有矿石，根据图标名称分组，计算每个图标的主色调，并保存到数据库
"""

import sqlite3
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from PIL import Image
import colorsys


class OreColorProcessor:
    """矿石主题色提取器"""
    
    def __init__(self, db_path: str, icons_dir: str):
        """
        初始化提取器
        
        Args:
            db_path: 数据库文件路径
            icons_dir: 图标文件目录路径
        """
        self.db_path = Path(db_path)
        self.icons_dir = Path(icons_dir)
        
        # 检查数据库文件是否存在
        if not self.db_path.exists():
            raise FileNotFoundError(f"数据库文件不存在: {self.db_path}")
        
        # 检查图标目录是否存在
        if not self.icons_dir.exists():
            raise FileNotFoundError(f"图标目录不存在: {self.icons_dir}")
        
        print(f"[+] 初始化矿石主题色提取器")
        print(f"[+] 数据库路径: {self.db_path}")
        print(f"[+] 图标目录: {self.icons_dir}")
    
    def get_ore_types(self) -> List[Tuple[int, str, str]]:
        """
        获取所有矿石的type_id、name和icon_filename
        
        Returns:
            list: [(type_id, name, icon_filename), ...]
        """
        print("[+] 开始检索矿石数据...")
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            query = """
            SELECT type_id, name, icon_filename 
            FROM types 
            WHERE categoryID = 25 
            AND published = 1 
            AND NOT en_name LIKE '%Compressed%'
            ORDER BY type_id
            """
            
            cursor.execute(query)
            results = cursor.fetchall()
            
            print(f"[+] 找到 {len(results)} 个矿石")
            return results
            
        except Exception as e:
            print(f"[x] 检索矿石数据失败: {e}")
            return []
        finally:
            conn.close()
    
    def group_by_icon(self, ore_types: List[Tuple[int, str, str]]) -> Dict[str, List[int]]:
        """
        根据图标名称分组
        
        Args:
            ore_types: [(type_id, name, icon_filename), ...]
        
        Returns:
            dict: {icon_filename: [type_id, ...], ...}
        """
        print("[+] 开始按图标名称分组...")
        
        icon_groups = defaultdict(list)
        
        for type_id, name, icon_filename in ore_types:
            if icon_filename:
                icon_groups[icon_filename].append(type_id)
        
        print(f"[+] 共 {len(icon_groups)} 个不同的图标")
        return dict(icon_groups)
    
    def apply_mosaic(self, img: Image.Image, grid_size: int = 32) -> Image.Image:
        """
        对图片应用马赛克效果（模糊化处理）
        
        处理流程：
        1. 处理透明图片：将RGBA转换为RGB，使用白色背景
        2. 按指定网格大小进行模糊化处理
        
        Args:
            img: PIL Image 对象
            grid_size: 马赛克强度，表示横纵各分成多少个色块（数值越大越清晰，越小越模糊）
        
        Returns:
            马赛克处理后的图片
        """
        # 处理透明图片：将RGBA转换为RGB，使用白色背景
        if img.mode == "RGBA":
            # 创建白色背景
            rgb_img = Image.new("RGB", img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[3])  # 使用alpha通道作为mask
            img = rgb_img
        elif img.mode != "RGB":
            img = img.convert("RGB")
        
        width, height = img.size
        pixels = img.load()
        
        # 创建新图片
        mosaic_img = Image.new("RGB", (width, height))
        mosaic_pixels = mosaic_img.load()
        
        # 计算每个网格块的尺寸
        block_width = width / grid_size
        block_height = height / grid_size
        
        # 遍历每个网格块
        for grid_y in range(grid_size):
            for grid_x in range(grid_size):
                # 计算当前块在图片中的像素范围
                x_start = int(grid_x * block_width)
                y_start = int(grid_y * block_height)
                x_end = int((grid_x + 1) * block_width)
                y_end = int((grid_y + 1) * block_height)
                
                # 确保不越界
                x_end = min(x_end, width)
                y_end = min(y_end, height)
                
                # 计算该块的平均颜色
                r_sum, g_sum, b_sum = 0, 0, 0
                pixel_count = 0
                
                for y in range(y_start, y_end):
                    for x in range(x_start, x_end):
                        r, g, b = pixels[x, y]
                        r_sum += r
                        g_sum += g
                        b_sum += b
                        pixel_count += 1
                
                if pixel_count > 0:
                    avg_r = int(r_sum / pixel_count)
                    avg_g = int(g_sum / pixel_count)
                    avg_b = int(b_sum / pixel_count)
                    
                    # 用平均颜色填充整个块
                    for y in range(y_start, y_end):
                        for x in range(x_start, x_end):
                            mosaic_pixels[x, y] = (avg_r, avg_g, avg_b)
        
        return mosaic_img
    
    def get_highlight_color(self, image_path: Path) -> Optional[Tuple[int, int, int]]:
        """
        提取图片最"亮眼"的颜色
        
        处理流程：
        1. 加载原图片
        2. 应用背景色处理（解决PNG透明度问题）
        3. 应用模糊化处理（grid_size=32）
        4. 从模糊后的图片中提取特征色
        
        提取规则：
        - 忽略灰度色（饱和度 < 0.25）
        - 忽略黑色（亮度 V < 0.2）
        - 忽略白色（亮度 V > 0.95）
        - 按 (饱和度 * 亮度) 得分排序
        
        Args:
            image_path: 图片文件路径
        
        Returns:
            tuple: (r, g, b) 或 None
        """
        try:
            # 1. 加载原图片
            original_img = Image.open(image_path)
            
            # 2. 应用模糊化处理（内部会处理透明背景）
            mosaic_img = self.apply_mosaic(original_img, grid_size=32)
            
            # 3. 从模糊后的图片中提取特征色
            # 转换为RGBA以便处理（虽然已经是RGB，但为了统一处理）
            if mosaic_img.mode != "RGBA":
                mosaic_img = mosaic_img.convert("RGBA")
            
            pixels = mosaic_img.getdata()
            candidates = []
            
            for r, g, b, a in pixels:
                if a < 32:   # 忽略透明（虽然模糊后应该没有透明了，但保留检查）
                    continue
                
                # 转换到 HSV（0~1 浮点）
                h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
                
                if s < 0.25:     # 忽略灰色/无彩色
                    continue
                
                if v < 0.2:      # 忽略接近黑色
                    continue
                
                if v > 0.95:     # 忽略接近白色
                    continue
                
                # 亮眼程度评分：亮度 * 饱和度
                score = s * v
                candidates.append((score, (r, g, b)))
            
            if not candidates:
                return None  # 没找到彩色像素
            
            # 分数最高的即为最"亮眼"
            candidates.sort(reverse=True)
            return candidates[0][1]
            
        except Exception as e:
            print(f"[!] 处理图片 {image_path} 时出错: {e}")
            return None
    
    def calculate_colors(self, icon_groups: Dict[str, List[int]]) -> Dict[int, str]:
        """
        计算每个图标的主题色，并映射到对应的type_id
        
        Args:
            icon_groups: {icon_filename: [type_id, ...], ...}
        
        Returns:
            dict: {type_id: hex_color, ...}
        """
        print("[+] 开始计算图标主题色...")
        
        type_colors = {}
        processed_icons = 0
        failed_icons = 0
        
        for icon_filename, type_ids in icon_groups.items():
            icon_path = self.icons_dir / icon_filename
            
            if not icon_path.exists():
                print(f"[!] 图标文件不存在: {icon_filename}")
                failed_icons += 1
                continue
            
            # 计算主题色
            color = self.get_highlight_color(icon_path)
            
            if color:
                r, g, b = color
                hex_color = f"#{r:02x}{g:02x}{b:02x}"
                
                # 为所有使用此图标的type_id分配相同的颜色
                for type_id in type_ids:
                    type_colors[type_id] = hex_color
                
                processed_icons += 1
                if processed_icons % 10 == 0:
                    print(f"[+] 已处理 {processed_icons} 个图标...")
            else:
                print(f"[!] 无法提取图标 {icon_filename} 的主题色")
                failed_icons += 1
        
        print(f"[+] 主题色计算完成")
        print(f"[+] 成功: {processed_icons} 个图标")
        print(f"[+] 失败: {failed_icons} 个图标")
        print(f"[+] 共为 {len(type_colors)} 个矿石分配了主题色")
        
        return type_colors
    
    def create_color_table(self, cursor: sqlite3.Cursor):
        """创建矿石主题色表"""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ore_colors (
                type_id INTEGER PRIMARY KEY,
                hex_color TEXT NOT NULL,
                FOREIGN KEY (type_id) REFERENCES types(type_id)
            )
        ''')
    
    def save_colors_to_db(self, type_colors: Dict[int, str]) -> bool:
        """
        将主题色保存到数据库
        
        Args:
            type_colors: {type_id: hex_color, ...}
        
        Returns:
            bool: 保存是否成功
        """
        print("[+] 开始保存主题色到数据库...")
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            # 创建表
            self.create_color_table(cursor)
            
            # 清空现有数据
            cursor.execute('DELETE FROM ore_colors')
            
            # 批量插入数据
            data = [(type_id, hex_color) for type_id, hex_color in type_colors.items()]
            cursor.executemany(
                'INSERT INTO ore_colors (type_id, hex_color) VALUES (?, ?)',
                data
            )
            
            # 提交事务
            conn.commit()
            
            print(f"[+] 成功保存 {len(data)} 条主题色记录到数据库")
            return True
            
        except Exception as e:
            print(f"[x] 保存主题色到数据库失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def process(self) -> bool:
        """
        执行完整的处理流程
        
        Returns:
            bool: 处理是否成功
        """
        print("[+] 开始处理矿石主题色...")
        
        # 1. 获取所有矿石
        ore_types = self.get_ore_types()
        if not ore_types:
            print("[x] 未找到矿石数据，处理终止")
            return False
        
        # 2. 按图标分组
        icon_groups = self.group_by_icon(ore_types)
        if not icon_groups:
            print("[x] 未找到有效的图标分组，处理终止")
            return False
        
        # 3. 计算主题色
        type_colors = self.calculate_colors(icon_groups)
        if not type_colors:
            print("[x] 未计算出任何主题色，处理终止")
            return False
        
        # 4. 保存到数据库
        success = self.save_colors_to_db(type_colors)
        
        if success:
            print("[+] 矿石主题色处理完成")
        else:
            print("[x] 矿石主题色处理失败")
        
        return success


def ore_color_process(db_path: str, icons_dir: str) -> bool:
    """
    矿石主题色提取主函数
    
    Args:
        db_path: 数据库文件路径
        icons_dir: 图标文件目录路径
    
    Returns:
        bool: 处理是否成功
    """
    try:
        processor = OreColorProcessor(db_path, icons_dir)
        success = processor.process()
        return success
        
    except Exception as e:
        print(f"[x] 矿石主题色提取失败: {e}")
        return False


def process_all_languages(config):
    """
    为所有语言处理矿石主题色
    
    Args:
        config: 配置字典
    
    Returns:
        bool: 处理是否成功
    """
    project_root = Path(__file__).parent.parent
    db_output_path = project_root / config["paths"]["db_output"]
    icons_dir = project_root / "custom_icons"
    languages = config.get("languages", ["en"])
    
    all_success = True
    
    for language in languages:
        print(f"\n[+] 处理语言: {language}")
        db_path = db_output_path / f"item_db_{language}.sqlite"
        
        if not db_path.exists():
            print(f"[!] 数据库文件不存在: {db_path}，跳过")
            continue
        
        success = ore_color_process(str(db_path), str(icons_dir))
        if not success:
            print(f"[x] 语言 {language} 的矿石主题色处理失败")
            all_success = False
        else:
            print(f"[+] 语言 {language} 的矿石主题色处理完成")
    
    return all_success


def main(config=None):
    """主函数"""
    import json
    
    print("[+] 矿石主题色处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        project_root = Path(__file__).parent.parent
        config_path = project_root / "config.json"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            print("[x] 配置文件不存在: config.json")
            return False
    
    # 为所有语言处理矿石主题色
    success = process_all_languages(config)
    
    if success:
        print("\n[+] 矿石主题色处理器完成")
    else:
        print("\n[x] 矿石主题色处理器部分失败")
    
    return success


if __name__ == "__main__":
    """独立运行时的入口"""
    main()

