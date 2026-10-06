#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一 HTTP 重试与响应资源管理，保留现有调用接口和默认策略。"""

import time

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class RetryableHTTPClient:
    """max_retries 沿用原语义，表示包含首次请求在内的总尝试次数。"""

    def __init__(self, max_retries: int = 5, retry_delay: float = 3.0,
                 default_timeout: int = 30, verify: bool = False):
        if max_retries < 1:
            raise ValueError("max_retries 必须至少为 1")
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.default_timeout = default_timeout
        self.verify = verify
        self.session = requests.Session()
        self.session.verify = verify

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.default_timeout)
        kwargs.setdefault("verify", self.verify)
        # GET 始终分块读取；显式 stream=True 时由调用方消费并关闭响应。
        buffer_response = method == "get" and not kwargs.get("stream", False)
        if method == "get":
            kwargs["stream"] = True
        for attempt in range(1, self.max_retries + 1):
            response = None
            try:
                response = getattr(self.session, method)(url, **kwargs)
                response.raise_for_status()
                if buffer_response:
                    response._content = b"".join(response.iter_content(chunk_size=65536))
                    response._content_consumed = True
                    response.close()
                return response
            except requests.RequestException as exc:
                if response is not None:
                    response.close()
                # 认证失败、资源不存在等永久错误不能当作暂时故障反复重试。
                if response is not None and 400 <= response.status_code < 500 and response.status_code not in (408, 429):
                    raise
                if attempt == self.max_retries:
                    print(f"[x] 请求失败，已达到最大重试次数 ({self.max_retries}): {url}")
                    raise
                print(f"[-] 请求失败 (尝试 {attempt}/{self.max_retries}): {url}: {exc}")
                print(f"[+] 等待 {self.retry_delay} 秒后重试...")
                time.sleep(self.retry_delay)

    def get(self, url: str, **kwargs) -> requests.Response:
        return self._request("get", url, **kwargs)

    def head(self, url: str, **kwargs) -> requests.Response:
        return self._request("head", url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        return self._request("post", url, **kwargs)

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()


_default_client = RetryableHTTPClient()


def get(url: str, **kwargs) -> requests.Response:
    return _default_client.get(url, **kwargs)


def head(url: str, **kwargs) -> requests.Response:
    return _default_client.head(url, **kwargs)


def post(url: str, **kwargs) -> requests.Response:
    return _default_client.post(url, **kwargs)


def create_session(max_retries: int = 5, retry_delay: float = 3.0,
                   default_timeout: int = 30, verify: bool = False) -> RetryableHTTPClient:
    return RetryableHTTPClient(max_retries, retry_delay, default_timeout, verify)
