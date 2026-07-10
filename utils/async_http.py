#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""aiohttp 并发文件下载"""

import asyncio
import ssl
from pathlib import Path
from typing import List, Tuple

import aiohttp


async def _download_all(
    items: List[Tuple[Path, str]],
    concurrency: int,
    user_agent: str,
    timeout_sec: int,
) -> Tuple[int, int]:
    sem = asyncio.Semaphore(concurrency)
    success = failed = 0

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    timeout = aiohttp.ClientTimeout(total=timeout_sec)
    connector = aiohttp.TCPConnector(limit=concurrency, limit_per_host=concurrency, ssl=ssl_ctx)
    headers = {"User-Agent": user_agent}

    async with aiohttp.ClientSession(timeout=timeout, connector=connector, headers=headers) as session:
        async def one(dest: Path, url: str):
            nonlocal success, failed
            async with sem:
                try:
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            failed += 1
                            return
                        data = await resp.read()
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(data)
                    success += 1
                except Exception:
                    failed += 1

        await asyncio.gather(*(one(d, u) for d, u in items))

    return success, failed


def download_files(
    items: List[Tuple[Path, str]],
    concurrency: int = 32,
    user_agent: str = "EveSDE/3.0",
    timeout_sec: int = 120,
    label: str = "",
) -> Tuple[int, int]:
    pending = [(d, u) for d, u in items if not d.exists()]
    if not pending:
        return 0, 0
    if label:
        print(f"[+] 下载{label}: {len(pending)} 个文件")
    success, failed = asyncio.run(_download_all(pending, concurrency, user_agent, timeout_sec))
    if label or failed:
        print(f"[+] 下载完成: 成功 {success}, 失败 {failed}")
    return success, failed
