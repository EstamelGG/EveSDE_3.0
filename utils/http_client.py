#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网络请求工具模块
提供带自动重试机制的HTTP请求功能
"""

import time
import requests
import urllib3
from typing import Optional, Dict, Any, Union
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class RetryableHTTPClient:
    """带自动重试机制的HTTP客户端"""
    
    def __init__(self, max_retries: int = 5, retry_delay: float = 3.0, 
                 default_timeout: int = 30, verify: bool = False):
        """
        初始化HTTP客户端
        
        Args:
            max_retries: 最大重试次数，默认5次
            retry_delay: 重试延迟时间（秒），默认3秒
            default_timeout: 默认超时时间（秒），默认30秒
            verify: 是否验证SSL证书，默认False
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.default_timeout = default_timeout
        self.verify = verify
        self.session = requests.Session()
        self.session.verify = verify
    
    def get(self, url: str, **kwargs) -> requests.Response:
        """
        发送GET请求，带自动重试机制
        
        Args:
            url: 请求URL
            **kwargs: 传递给requests.get的其他参数
            
        Returns:
            requests.Response对象
            
        Raises:
            requests.RequestException: 所有重试都失败后抛出异常
        """
        # 设置默认超时时间
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.default_timeout
        
        # 设置默认verify
        if 'verify' not in kwargs:
            kwargs['verify'] = self.verify
        
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, **kwargs)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    print(f"[-] 请求失败 (尝试 {attempt + 1}/{self.max_retries}): {url}")
                    print(f"[-] 错误信息: {str(e)}")
                    print(f"[+] 等待 {self.retry_delay} 秒后重试...")
                    time.sleep(self.retry_delay)
                else:
                    print(f"[x] 请求失败，已达到最大重试次数 ({self.max_retries}): {url}")
                    print(f"[x] 最后错误: {str(e)}")
        
        # 所有重试都失败，抛出异常
        raise last_exception
    
    def head(self, url: str, **kwargs) -> requests.Response:
        """
        发送HEAD请求，带自动重试机制
        
        Args:
            url: 请求URL
            **kwargs: 传递给requests.head的其他参数
            
        Returns:
            requests.Response对象
            
        Raises:
            requests.RequestException: 所有重试都失败后抛出异常
        """
        # 设置默认超时时间
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.default_timeout
        
        # 设置默认verify
        if 'verify' not in kwargs:
            kwargs['verify'] = self.verify
        
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                response = self.session.head(url, **kwargs)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    print(f"[-] 请求失败 (尝试 {attempt + 1}/{self.max_retries}): {url}")
                    print(f"[-] 错误信息: {str(e)}")
                    print(f"[+] 等待 {self.retry_delay} 秒后重试...")
                    time.sleep(self.retry_delay)
                else:
                    print(f"[x] 请求失败，已达到最大重试次数 ({self.max_retries}): {url}")
                    print(f"[x] 最后错误: {str(e)}")
        
        # 所有重试都失败，抛出异常
        raise last_exception
    
    def post(self, url: str, **kwargs) -> requests.Response:
        """
        发送POST请求，带自动重试机制
        
        Args:
            url: 请求URL
            **kwargs: 传递给requests.post的其他参数
            
        Returns:
            requests.Response对象
            
        Raises:
            requests.RequestException: 所有重试都失败后抛出异常
        """
        # 设置默认超时时间
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.default_timeout
        
        # 设置默认verify
        if 'verify' not in kwargs:
            kwargs['verify'] = self.verify
        
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                response = self.session.post(url, **kwargs)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    print(f"[-] 请求失败 (尝试 {attempt + 1}/{self.max_retries}): {url}")
                    print(f"[-] 错误信息: {str(e)}")
                    print(f"[+] 等待 {self.retry_delay} 秒后重试...")
                    time.sleep(self.retry_delay)
                else:
                    print(f"[x] 请求失败，已达到最大重试次数 ({self.max_retries}): {url}")
                    print(f"[x] 最后错误: {str(e)}")
        
        # 所有重试都失败，抛出异常
        raise last_exception
    
    def close(self):
        """关闭会话"""
        self.session.close()


# 创建全局默认客户端实例
_default_client = RetryableHTTPClient()


def get(url: str, **kwargs) -> requests.Response:
    """
    便捷函数：发送GET请求，带自动重试机制
    
    Args:
        url: 请求URL
        **kwargs: 传递给requests.get的其他参数
        
    Returns:
        requests.Response对象
        
    Raises:
        requests.RequestException: 所有重试都失败后抛出异常
    """
    return _default_client.get(url, **kwargs)


def head(url: str, **kwargs) -> requests.Response:
    """
    便捷函数：发送HEAD请求，带自动重试机制
    
    Args:
        url: 请求URL
        **kwargs: 传递给requests.head的其他参数
        
    Returns:
        requests.Response对象
        
    Raises:
        requests.RequestException: 所有重试都失败后抛出异常
    """
    return _default_client.head(url, **kwargs)


def post(url: str, **kwargs) -> requests.Response:
    """
    便捷函数：发送POST请求，带自动重试机制
    
    Args:
        url: 请求URL
        **kwargs: 传递给requests.post的其他参数
        
    Returns:
        requests.Response对象
        
    Raises:
        requests.RequestException: 所有重试都失败后抛出异常
    """
    return _default_client.post(url, **kwargs)


def create_session(max_retries: int = 5, retry_delay: float = 3.0, 
                   default_timeout: int = 30, verify: bool = False) -> RetryableHTTPClient:
    """
    创建一个新的HTTP客户端会话
    
    Args:
        max_retries: 最大重试次数，默认5次
        retry_delay: 重试延迟时间（秒），默认3秒
        default_timeout: 默认超时时间（秒），默认30秒
        verify: 是否验证SSL证书，默认False
        
    Returns:
        RetryableHTTPClient实例
    """
    return RetryableHTTPClient(
        max_retries=max_retries,
        retry_delay=retry_delay,
        default_timeout=default_timeout,
        verify=verify
    )

