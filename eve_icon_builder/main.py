#!/usr/bin/env python3
"""
EVE Online 图标生成器 - Python版本
多用途物品图标生成工具
"""

import argparse
import sys
import time
from pathlib import Path
from datetime import datetime

from cache import CacheDownloader, CacheError
from sde import update_sde, read_types, read_group_categories, read_icons, read_graphics, read_skin_materials
from icons import IconBuildData, build_icon_export, IconError


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='EVE Online多用途物品图标生成器'
    )
    
    # 全局参数
    parser.add_argument('-u', '--user_agent', required=True,
                       help='HTTP请求的用户代理')
    parser.add_argument('-c', '--cache_folder', default='./cache',
                       help='游戏数据缓存文件夹 (默认: ./cache)')
    parser.add_argument('-i', '--icon_folder', default='./icons',
                       help='图标输出/缓存文件夹 (默认: ./icons)')
    parser.add_argument('-l', '--logfile',
                       help='日志文件路径')
    parser.add_argument('--append_log', action='store_true',
                       help='追加到日志文件而非覆盖')
    parser.add_argument('--silent', action='store_true',
                       help='静默模式')
    parser.add_argument('-f', '--force_rebuild', action='store_true',
                       help='强制重建未改变的图标')
    parser.add_argument('-s', '--skip_if_fresh', action='store_true',
                       help='如果图标未改变则跳过输出')
    parser.add_argument('--no_progress', action='store_true',
                       help='禁用进度显示')
    parser.add_argument('--skip_skins', action='store_true',
                       help='跳过SKIN类型图标的构造')
    parser.add_argument('--test_type_id', type=int,
                       help='测试模式：只构造指定typeID的图标')
    
    # 子命令
    subparsers = parser.add_subparsers(dest='command', required=True,
                                       help='输出模式')
    
    # service_bundle 子命令
    service_bundle = subparsers.add_parser('service_bundle',
                                          help='图像服务托管包 (zip含元数据)')
    service_bundle.add_argument('-o', '--out', required=True,
                               help='输出文件')
    
    # iec 子命令
    iec = subparsers.add_parser('iec',
                               help='图像导出集合 (zip)')
    iec.add_argument('-o', '--out', required=True,
                    help='输出文件')
    
    # web_dir 子命令
    web_dir = subparsers.add_parser('web_dir',
                                   help='准备Web托管目录')
    web_dir.add_argument('-o', '--out', required=True,
                        help='输出目录')
    web_dir.add_argument('--copy_files', action='store_true',
                        help='复制图像文件而非创建符号链接')
    web_dir.add_argument('--hardlink', action='store_true',
                        help='使用硬链接而非软链接')
    
    # checksum 子命令
    checksum = subparsers.add_parser('checksum',
                                    help='打印（或写入）当前图标集的校验和')
    checksum.add_argument('-o', '--out',
                         help='输出文件，如果省略则打印到stdout')
    
    # aux_icons 子命令
    aux_icons = subparsers.add_parser('aux_icons',
                                     help='辅助图标转储 (zip)')
    aux_icons.add_argument('-o', '--out', required=True,
                          help='输出文件')
    
    # aux_all 子命令
    aux_all = subparsers.add_parser('aux_all',
                                   help='辅助所有图像转储 (zip)')
    aux_all.add_argument('-o', '--out', required=True,
                        help='输出文件')
    
    args = parser.parse_args()
    
    # 确定输出模式和参数
    output_mode = args.command
    output_params = {}
    
    if output_mode == 'service_bundle':
        output_params['out'] = args.out
    elif output_mode == 'iec':
        output_params['out'] = args.out
    elif output_mode == 'web_dir':
        out_path = Path(args.out)
        if not out_path.exists():
            out_path.mkdir(parents=True, exist_ok=True)
        elif out_path.is_file():
            print(f"[x] 输出必须是目录! ({args.out})")
            return 1
        output_params['out'] = args.out
        output_params['copy_files'] = args.copy_files
        output_params['hard_link'] = args.hardlink
    elif output_mode == 'checksum':
        output_params['out'] = args.out
    elif output_mode == 'aux_icons':
        output_params['out'] = args.out
    elif output_mode == 'aux_all':
        output_params['out'] = args.out
    
    silent_mode = args.silent or (output_mode == 'checksum' and not args.out)
    skip_if_fresh = args.skip_if_fresh and not (output_mode == 'checksum' and not args.out)
    
    # 设置日志
    log_file = None
    if args.logfile:
        mode = 'a' if args.append_log else 'w'
        log_file = open(args.logfile, mode, encoding='utf-8')
        log_file.write(f"图标生成运行, 输出: {output_mode} - {datetime.now()}\n")
    
    try:
        start_time = time.time()
        
        # 初始化缓存
        if not silent_mode:
            print(f"初始化缓存 (UA:`{args.user_agent}`)")
        if log_file:
            log_file.write(f"初始化缓存 (UA:`{args.user_agent}`)\n")
        
        cache = CacheDownloader(
            Path(args.cache_folder),
            args.user_agent,
            use_macos_build=False
        )
        cache_init_duration = time.time() - start_time
        
        # 加载SDE数据
        data_load_start = time.time()
        if not silent_mode:
            print("加载SDE...")
        if log_file:
            log_file.write("加载SDE...\n")
        
        sde = update_sde(silent_mode)
        
        icon_build_data = IconBuildData(
            types=read_types(sde, silent_mode),
            group_categories=read_group_categories(sde, silent_mode),
            icon_files=read_icons(sde, silent_mode),
            graphics_folders=read_graphics(sde, silent_mode),
            skin_materials=read_skin_materials(sde, silent_mode)
        )
        
        sde.close()
        data_load_duration = time.time() - data_load_start
        
        # 构建图标
        if not silent_mode:
            print("构建图标...")
        if log_file:
            log_file.write("构建图标...\n")
        
        build_start = time.time()
        added, removed = build_icon_export(
            output_mode=output_mode,
            skip_output_if_fresh=skip_if_fresh,
            data=icon_build_data,
            cache=cache,
            icon_dir=Path(args.icon_folder),
            force_rebuild=args.force_rebuild,
            silent_mode=silent_mode,
            log_file=log_file,
            show_progress=not args.no_progress,
            skip_skins=args.skip_skins,
            test_type_id=args.test_type_id,
            **output_params
        )
        build_duration = time.time() - build_start
        
        # 输出统计信息
        total_duration = time.time() - start_time
        
        s1 = f"完成于: {total_duration:.1f} 秒"
        s2 = f"\t缓存初始化: {cache_init_duration:.1f} 秒"
        s3 = f"\t数据加载: {data_load_duration:.1f} 秒"
        s4 = f"\t图像构建: {build_duration:.1f} 秒 ({added} 新增, {removed} 删除)"
        
        if not silent_mode:
            print(s1)
            print(s2)
            print(s3)
            print(s4)
        
        if log_file:
            log_file.write(s1 + '\n')
            log_file.write(s2 + '\n')
            log_file.write(s3 + '\n')
            log_file.write(s4 + '\n')
        
        # 清理不必要的缓存文件
        cache.purge(['sde.zip', 'checksum.txt'])
        
        return 0
        
    except (CacheError, IconError, Exception) as e:
        print(f"[x] 错误: {e}", file=sys.stderr)
        if log_file:
            log_file.write(f"[x] 错误: {e}\n")
        return 1
    finally:
        if log_file:
            log_file.close()


if __name__ == '__main__':
    sys.exit(main())
