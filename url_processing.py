#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
URL处理模块
负责URL发现、筛选和按年保存
"""

import json
import logging
import os
import re
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from typing import Dict, List, Set, Optional, Tuple
from datetime import datetime


class URLProcessor:
    """URL处理器"""
    
    def __init__(self):
        """初始化URL处理器"""
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
    
    def process_urls_for_company(self, historical_urls: List[Tuple[str, str]], company_url: str) -> str:
        """
        处理公司的所有历史URLs，按年筛选并保存
        
        Args:
            historical_urls: [(year, url), ...] 历史URL列表
            company_url: 公司URL标识符
            
        Returns:
            输出文件路径
        """
        self.logger.info(f"🌐 开始处理公司URLs: {company_url}")
        
        # 准备输出目录
        output_dir = os.path.join("outputs", company_url)
        os.makedirs(output_dir, exist_ok=True)
        
        # 输出文件路径
        output_file = os.path.join(output_dir, f"{company_url}_filtered_links.json")
        
        # 初始化或加载已存在结果，实现增量"断点续跑"
        year_links_map: Dict[str, List[str]] = {}
        if os.path.exists(output_file):
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    year_links_map = data.get("year_links_map", {})
                self.logger.info(
                    f"🔄 发现已存在的链接文件: {output_file}，已加载 {len(year_links_map)} 年的数据，将进行增量处理"
                )
            except Exception as e:
                self.logger.warning(f"⚠️ 读取已存在链接文件失败，将重新生成: {e}")
        
        # 开始按年处理URLs（仅处理缺失或为空的年份）
        for year, homepage_url in historical_urls:
            # 如果该年已经有非空链接，则跳过，实现增量处理
            if year in year_links_map and len(year_links_map[year]) > 0:
                self.logger.info(f"⏭️ 跳过 {year} 年，已有 {len(year_links_map[year])} 个链接")
                continue

            self.logger.info(f"🔍 处理 {year} 年的URLs...")
            
            try:
                # 发现内部链接
                internal_links = self.discover_internal_links(homepage_url, max_links=10000)
                
                # 过滤有效链接
                filtered_links = self._filter_valid_links(internal_links)
                
                year_links_map[year] = filtered_links
                
                self.logger.info(f"✅ {year} 年处理完成: {len(filtered_links)} 个有效链接")
                
            except Exception as e:
                self.logger.error(f"❌ {year} 年处理失败: {e}")
                year_links_map[year] = []
        
        # 保存结果
        result_data = {
            "generation_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "company_url": company_url,
            "total_years": len(year_links_map),
            "year_links_map": year_links_map
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        
        total_links = sum(len(links) for links in year_links_map.values())
        self.logger.info(f"💾 链接处理完成，共 {total_links} 个链接已保存到: {output_file}")
        
        return output_file
    
    def discover_internal_links(self, homepage_url: str, max_links: int = 10000) -> List[str]:
        """
        从主页发现内部链接
        
        Args:
            homepage_url: 主页URL
            max_links: 最大链接数量
            
        Returns:
            内部链接列表
        """
        self.logger.info(f"🔍 开始发现URL: {homepage_url}")
        
        try:
            # 获取主页内容
            response = self.session.get(homepage_url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            home_host = self._extract_home_host(homepage_url)
            discovered_links = set([homepage_url])  # 包含主页本身
            
            # 提取所有链接
            for a_tag in soup.find_all(['a', 'area'], href=True):
                href = a_tag.get('href')
                if not href:
                    continue
                
                # 转换为完整URL
                full_url = urljoin(homepage_url, href)
                
                # 修复 urljoin 在 Wayback URL 中的问题
                if "/web/" in full_url and "http:/" in full_url and "http://" not in full_url:
                    full_url = full_url.replace("http:/", "http://")
                if "/web/" in full_url and "https:/" in full_url and "https://" not in full_url:
                    full_url = full_url.replace("https:/", "https://")
                
                # 提取候选链接的真实主域名
                candidate_host = self._extract_home_host(full_url)

                # 过滤同主域名
                if candidate_host == "" or candidate_host == home_host:
                    # 清理URL
                    clean_url = full_url.split("#")[0]  # 移除 fragment
                    
                    # 检查是否应该包含
                    if self._should_include_url(clean_url):
                        discovered_links.add(clean_url)
                        
                        if len(discovered_links) >= max_links:
                            break
            
            result = list(discovered_links)
            self.logger.info(f"✅ 发现 {len(result)} 个内部链接")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 发现URL时出错: {e}")
            return [homepage_url]  # 至少返回主页
    
    def _extract_home_host(self, url: str) -> str:
        """提取主页对应的主域名（去除 www. 前缀）"""
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
    
    def _should_include_url(self, url: str) -> bool:
        """判断是否应该包含该URL"""
        url_lower = url.lower()
        
        # 排除不需要的URL
        for pattern in self.exclude_patterns:
            if re.search(pattern, url_lower):
                return False
        
        return True
    
    def _filter_valid_links(self, links: List[str]) -> List[str]:
        """过滤有效链接：只过滤技术文件，不进行内容检查"""
        valid_links: List[str] = []

        for link in links:
            if not self._is_meaningful_url(link):
                self.logger.debug(f"🚫 [Structure] {link}")
                continue
        
            # if not self._is_url_reachable(link):
            #     self.logger.debug(f"🚫 [Unreachable] {link}")
            #     continue

            valid_links.append(link)
            self.logger.debug(f"✅ Valid URL: {link}")

        self.logger.info(
            f"✅ URL过滤完成: {len(valid_links)}/{len(links)} 链接通过结构过滤"
        )
        return valid_links

    def _is_meaningful_url(self, url: str) -> bool:
        """基于URL结构判断是否有意义（过滤技术文件）"""
        # 过滤明显的技术文件和静态资源
        excluded_extensions = ['.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', 
                             '.pdf', '.xml', '.json', '.txt', '.zip', '.woff', '.ttf']
        excluded_paths = ['/static/', '/assets/', '/css/', '/js/', '/images/', '/img/', 
                         '/fonts/', '/media/', '/resources/', '/ajax/', '/api/']
        
        url_lower = url.lower()
        
        # 排除技术文件扩展名
        if any(url_lower.endswith(ext) for ext in excluded_extensions):
            return False
        
        # 排除技术路径
        if any(path in url_lower for path in excluded_paths):
            return False
        
        return True

    def _is_url_reachable(self, url: str) -> bool:
        """快速判断 URL 是否可访问且非典型错误页。
        仅下载少量 HTML；若状态码不在 200-399 范围或命中 Wayback 典型错误提示，则判定为不可用。"""

        try:
            import requests  # 延迟导入，避免顶层依赖

            resp = self.url_discovery.session.get(url, timeout=10, allow_redirects=True, stream=True)
            if resp.status_code >= 400:
                return False

            # 读取前 2KB 文本用于错误检测
            snippet = resp.text[:2048].lower()

            wayback_errors = [
                "got an http", "response at crawl time", "redirecting to", "impatient?",
                "page cannot be crawled", "not in archive", "page not found", "robots.txt",
                "this content is not available", "excluded from the wayback machine", "calendar not available"
            ]

            hits = sum(1 for kw in wayback_errors if kw in snippet)
            return hits < 2

        except Exception:
            return False

    def get_page_content(self, url: str, max_length: Optional[int] = 3000) -> Optional[str]:
        """获取页面内容用于分析"""
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
            
            # 根据 max_length 限制文本长度
            if max_length is not None and len(text) > max_length:
                text = text[:max_length] + "..."
            
            return text
            
        except Exception as e:
            self.logger.warning(f"❌ 获取页面内容失败 {url}: {e}")
            return None

    def load_filtered_links(self, company_url: str) -> Dict[str, List[str]]:
        """加载已保存的过滤链接"""
        output_dir = os.path.join("outputs", company_url)
        links_file = os.path.join(output_dir, f"{company_url}_filtered_links.json")
        
        if not os.path.exists(links_file):
            self.logger.error(f"❌ 链接文件不存在: {links_file}")
            return {}
        
        try:
            with open(links_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            year_links_map = data.get("year_links_map", {})
            self.logger.info(f"✅ 成功加载 {len(year_links_map)} 年的链接数据")
            return year_links_map
            
        except Exception as e:
            self.logger.error(f"❌ 加载链接文件失败: {e}")
            return {}


def extract_company_url_from_filepath(file_path: str) -> str:
    """从文件路径中提取公司URL"""
    import os
    # 获取文件名（去除路径和扩展名）
    filename = os.path.basename(file_path)
    # 去除扩展名
    company_url = os.path.splitext(filename)[0]
    return company_url


if __name__ == "__main__":
    # 测试代码
    processor = URLProcessor()
    test_url = "https://web.archive.org/web/20241231234159/https://www.apple.com/"
    
    links = processor.discover_internal_links(test_url, max_links=10)
    print(f"发现的链接数: {len(links)}")
    
    for i, link in enumerate(links[:5], 1):
        print(f"{i}. {link}") 