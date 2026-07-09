#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dogma效果修补数据处理器模块
用于修补dogmaEffects表中的特定效果数据

对应old版本: old/main.py中的dogmaEffect_patch函数
功能: 从JSON文件加载修补数据，更新dogmaEffects表的modifier_info字段
数据源: dogmaPatch/dogma_effect_patches.json
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional


class DogmaEffectPatchProcessor:
    """Dogma效果修补数据处理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化Dogma效果修补处理器"""
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.db_output_path = self.project_root / config["paths"]["db_output"]
        self.languages = config.get("languages", ["en"])
        self.patch_file_path = self.project_root / "dogmaPatch" / "dogma_effect_patches.json"
    
    def load_dogma_effect_patches(self) -> List[Dict[str, Any]]:
        """从JSON文件加载dogmaEffects的修补数据"""
        try:
            with open(self.patch_file_path, 'r', encoding='utf-8') as f:
                patches = json.load(f)
            print(f"[+] 成功从 {self.patch_file_path} 加载了 {len(patches)} 个修补项")
            return patches
        except FileNotFoundError:
            print(f"[!] 修补文件 {self.patch_file_path} 不存在，跳过dogmaEffects修补")
            return []
        except json.JSONDecodeError as e:
            print(f"[x] 解析修补文件 {self.patch_file_path} 失败: {e}")
            return []
        except Exception as e:
            print(f"[x] 加载修补文件 {self.patch_file_path} 时发生异常: {e}")
            return []
    
    def apply_dogma_effect_patches(self, cursor: sqlite3.Cursor, patches: List[Dict[str, Any]], lang: str):
        """应用dogmaEffects修补数据"""
        try:
            # 应用每个修补
            for patch in patches:
                effect_name = patch["effect_name"]
                # 将JSON对象转换为字符串存储到数据库中
                modifier_info = json.dumps(patch["modifier_info"], separators=(',', ':'))

                # 更新指定效果的modifier_info字段
                cursor.execute(
                    'UPDATE dogmaEffects SET modifier_info = ? WHERE effect_name = ?',
                    (modifier_info, effect_name)
                )

                # 获取受影响的行数
                affected_rows = cursor.rowcount
                print(f"[+] 数据库 {lang}: 已修补 {affected_rows} 条 {effect_name} 效果记录")
                
        except Exception as e:
            print(f"[x] 应用修补数据时出错: {e}")
            raise
    
    def process_dogma_effect_patch_for_language(self, language: str) -> bool:
        """为指定语言处理dogmaEffects修补数据"""
        print(f"[+] 开始处理dogmaEffects修补数据，语言: {language}")
        
        # 数据库文件路径
        db_path = self.db_output_path / f"item_db_{language}.sqlite"
        
        if not db_path.exists():
            print(f"[!] 数据库文件不存在: {db_path}")
            return False
        
        try:
            # 连接数据库
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # 加载修补数据
            patches = self.load_dogma_effect_patches()
            
            if not patches:
                print("[!] 没有可用的修补数据，跳过修补操作")
                return True
            
            # 应用修补数据
            self.apply_dogma_effect_patches(cursor, patches, language)
            
            # 提交更改
            conn.commit()
            print(f"[+] dogmaEffects修补数据处理完成，语言: {language}")
            return True
            
        except Exception as e:
            print(f"[x] 处理dogmaEffects修补数据时出错: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()
    
    def process_all_languages(self) -> bool:
        """为所有语言处理dogmaEffects修补数据"""
        print("[+] 开始处理dogmaEffects修补数据")
        
        # 检查修补文件是否存在
        if not self.patch_file_path.exists():
            print(f"[!] 修补文件不存在: {self.patch_file_path}")
            return False
        
        success_count = 0
        for language in self.languages:
            if self.process_dogma_effect_patch_for_language(language):
                success_count += 1
        
        print(f"[+] dogmaEffects修补数据处理完成，成功处理 {success_count}/{len(self.languages)} 个语言")
        return success_count > 0


def main(config=None):
    """主函数"""
    print("[+] Dogma效果修补数据处理器启动")
    
    # 如果没有传入配置，则尝试加载本地配置（用于独立运行）
    if config is None:
        import json
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # 创建处理器并执行
    processor = DogmaEffectPatchProcessor(config)
    processor.process_all_languages()
    
    print("\n[+] Dogma效果修补数据处理器完成")


if __name__ == "__main__":
    main()
