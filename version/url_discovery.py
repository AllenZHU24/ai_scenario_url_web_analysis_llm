#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
URL发现模块
使用传统爬虫技术从电商网站主页提取内部链接
"""

import requests
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from typing import Dict, List, Set, Optional
import logging
import time

class URLDiscovery:
    """URL发现器"""
    
    def __init__(self):
        """初始化URL发现器"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # 排除的URL模式
        self.exclude_patterns = [
            r'\.pdf$', r'\.jpg$', r'\.png$', r'\.gif$', r'\.css$', r'\.js$',
            r'/legal/', r'/privacy/', r'/terms/', r'/cookie',
            r'/sitemap', r'/robots', r'/favicon', r'mailto:', r'tel:',
            r'#', r'javascript:'
        ]
        
        self.logger = logging.getLogger(__name__)
        
    def discover_internal_links(self, homepage_url: str, max_links: int = 50) -> List[str]:
        """
        从主页发现内部链接
        
        Args:
            homepage_url: 主页URL
            max_links: 最大链接数量
            
        Returns:
            内部链接列表
        """
        # ------------- 新增: 解析主页实际主域名 -------------
        def _extract_home_host(url: str) -> str:
            """提取主页对应的主域名（去除 www. 前缀）。

            同时兼容普通 URL 与 Wayback Machine 快照 URL。"""
            parsed = urlparse(url)
            host = parsed.netloc.lower()
            # Wayback 场景: host == web.archive.org，需要提取真实站点域名
            if "web.archive.org" in host:
                m = re.search(r"/web/\d+/(https?://[^/]+)", url)
                if m:
                    underlying = m.group(1)
                    # 修正常见的 http:/、https:/ 错误
                    if underlying.startswith("http:/") and not underlying.startswith("http://"):
                        underlying = underlying.replace("http:/", "http://", 1)
                    if underlying.startswith("https:/") and not underlying.startswith("https://"):
                        underlying = underlying.replace("https:/", "https://", 1)
                    host = urlparse(underlying).netloc.lower()
            # 去掉端口号
            if ":" in host:
                host = host.split(":")[0]
            # 去掉 leading 'www.'
            if host.startswith("www."):
                host = host[4:]
            return host
        # ---------------------------------------------------

        self.logger.info(f"开始发现URL: {homepage_url}")
        
        try:
            # 获取主页内容
            response = self.session.get(homepage_url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            home_host = _extract_home_host(homepage_url)
            discovered_links = set([homepage_url])  # 包含主页本身
            
            # 提取所有链接
            # 同时支持 <a> 与 <area>（imagemap）元素中的 href
            for a_tag in soup.find_all(['a', 'area'], href=True):
                href = a_tag.get('href')
                if not href:
                    continue
                
                # 转换为完整URL
                full_url = urljoin(homepage_url, href)
                
                # 修复 urljoin 在 Wayback URL 中的问题：http:/ -> http://
                if "/web/" in full_url and "http:/" in full_url and "http://" not in full_url:
                    full_url = full_url.replace("http:/", "http://")
                if "/web/" in full_url and "https:/" in full_url and "https://" not in full_url:
                    full_url = full_url.replace("https:/", "https://")
                
                # ------------- 提取候选链接的真实主域名（去掉 www. 与端口）-------------
                candidate_host = _extract_home_host(full_url)

                # ------------- 过滤同主域名 -------------
                if candidate_host == "" or candidate_host == home_host:
                    # 清理URL（保持 Wayback 前缀，便于后续用同一 URL 抓取内容）
                    clean_url = full_url.split("#")[0]  # 移除 fragment
                    
                    # 检查是否应该包含
                    if self._should_include_url(clean_url):
                        discovered_links.add(clean_url)
                        
                        if len(discovered_links) >= max_links:
                            break
            
            result = list(discovered_links)
            self.logger.info(f"发现 {len(result)} 个内部链接")
            return result
            
        except Exception as e:
            self.logger.error(f"发现URL时出错: {e}")
            return [homepage_url]  # 至少返回主页
    
    def _should_include_url(self, url: str) -> bool:
        """判断是否应该包含该URL"""
        url_lower = url.lower()
        
        # 排除不需要的URL
        for pattern in self.exclude_patterns:
            if re.search(pattern, url_lower):
                return False
        
        return True
    
    def get_page_content_for_analysis(self, url: str, max_length: Optional[int] = 3000) -> Optional[str]:
        """获取页面内容用于LLM分析

        Args:
            url: 目标URL
            max_length: 截取的最大字符数，默认为3000。传入 ``None`` 表示不进行长度限制。
        """
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 移除脚本和样式标签
            for script in soup(["script", "style"]):
                script.decompose()
            
            # 获取主要文本内容
            text = soup.get_text()
            # 清理文本
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            # 根据 max_length 限制文本长度以适应LLM
            if max_length is not None and len(text) > max_length:
                text = text[:max_length] + "..."
            
            return text
            
        except Exception as e:
            self.logger.warning(f"获取页面内容失败 {url}: {e}")
            return None


if __name__ == "__main__":
    # 测试代码
    discovery = URLDiscovery()
    test_url = "https://web.archive.org/web/20241231234159/https://www.apple.com/"
    
    links = discovery.discover_internal_links(test_url, max_links=10)
    print(f"发现的链接数: {len(links)}")
    
    for i, link in enumerate(links[:5], 1):
        print(f"{i}. {link}")
        
    # 测试获取页面内容
    if links:
        content = discovery.get_page_content_for_analysis(links[0])
        if content:
            print(f"\n页面内容预览 ({len(content)} 字符):")
            print(content[:200] + "...") 