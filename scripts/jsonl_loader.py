#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSONL加载器模块
高性能的JSONL文件流式加载工具
"""

import orjson
from pathlib import Path
from typing import List, Dict, Any


def load_jsonl(file_path: str) -> List[Dict[str, Any]]:
    """
    流式加载JSONL文件并返回JSON数组
    使用orjson获得最佳性能
    
    Args:
        file_path: JSONL文件路径
        
    Returns:
        List[Dict[str, Any]]: JSON对象数组
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        print(f"[x] 文件不存在: {file_path}")
        return []
    
    print(f"[+] 加载JSONL文件: {file_path.name}")
    
    result = []
    
    try:
        with open(file_path, 'rb') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    # 使用orjson进行超快JSON解析
                    data = orjson.loads(line)
                    result.append(data)
                except orjson.JSONDecodeError as e:
                    print(f"[!] 文件 {file_path.name} 第 {line_num} 行JSON解析错误: {e}")
                    continue
                    
    except Exception as e:
        print(f"[x] 读取文件失败 {file_path}: {e}")
        return []
    
    print(f"[+] 加载完成: {len(result)} 条记录")
    return result