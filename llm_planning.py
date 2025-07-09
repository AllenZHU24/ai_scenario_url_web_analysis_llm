#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM规划模块
负责识别核心页面类型和推荐核心URLs
"""

import json
import logging
import os
import re
import urllib.parse
import random
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from openai import OpenAI
import pathlib


class LLMPlanner:
    """LLM规划器"""
    
    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1"):
        """初始化LLM规划器"""
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        
        self.logger = logging.getLogger(__name__)
        
        # 模型配置
        self.high_model = "google/gemini-2.5-pro"          # 高性能模型（核心页面类型识别）
        self.medium_model = "openai/gpt-4o-mini"           # 中等性能模型（URL推荐）
        
        # 核心页面类型存储
        self.core_page_types = []
        self.core_page_types_nested = {}
        
        # 编译后的正则表达式模式
        self._compiled_patterns = None
        
        self.logger.info(f"🚀 LLM规划器已初始化")
    
    def generate_core_page_types(self, year_links_map, company_url, expected_types=50):
        """生成核心页面类型并保存"""
        self.logger.info(f"🧠 开始识别核心页面类型...")
        
        # 准备输出目录和文件
        output_dir = os.path.join("outputs", company_url)
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f"{company_url}_core_page_types.json")
        
        # 检查是否已存在结果
        if os.path.exists(output_file):
            self.logger.info(f"✅ 发现已存在的核心页面类型文件: {output_file}")
            self._load_core_page_types(output_file)
            return output_file
        
        # 合并并抽样 URL
        merged = []
        for links in year_links_map.values():
            merged.extend(links)
        unique_links = list(dict.fromkeys(merged))  # 保序去重
        sample_links = unique_links[:]
        random.shuffle(sample_links)  # 随机打乱顺序

        sample_block = "\n".join(sample_links)

        prompt = (
            f"You are a senior e-commerce website analyst. Below are internal URLs from multiple archive years of THE SAME website.\n\n"
            f"Please summarise ≈{expected_types} CORE PAGE TYPES covering the complete customer journey "
            f"(Awareness, Interest, Consideration, Decision, Fulfillment, Retention).\n\n"
            f"For better readability, structure the final JSON as *nested by stage*:\n"
            f"```json\n{{\n  \"Awareness Stage\": [\n    {{\n      \"type_name\": \"Home\",\n      \"typical_url_patterns\": [\"/\"]\n    }}\n  ],\n  \"Interest Stage\": [],\n  \"Consideration Stage\": [],\n  \"Decision Stage\": [],\n  \"Fulfillment Stage\": [],\n  \"Retention Stage\": []\n}}\n```\n"
            f"Explanation: keys are the six customer-journey stages; each value is an array of page-type objects containing *type_name* and *typical_url_patterns*. Do NOT include any other keys.\n\n"
            f"# Sample internal links (first {len(sample_links)})\n{sample_block}"
        )

        # 调用高性能LLM
        llm_resp = self._call_llm(prompt, model=self.high_model, task_tag="识别核心页面类型")
        parsed = self._parse_llm_response(llm_resp)

        # 处理LLM响应并构建数据结构
        self._process_core_page_types_response(parsed)
        
        # 保存结果
        result_data = {
            "generation_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "company_url": company_url,
            "core_page_types": self.core_page_types_nested or self.core_page_types,
            "total_types": len(self.core_page_types)
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"✅ 核心页面类型识别完成，共 {len(self.core_page_types)} 个类型已保存到: {output_file}")
        return output_file

    def _process_core_page_types_response(self, parsed: Dict):
        """处理LLM响应，构建核心页面类型数据结构"""
        if "core_page_types" in parsed:
            # 旧格式：平铺列表
            flat_list = parsed["core_page_types"]
            nested: Dict[str, List[Dict]] = {}
            for item in flat_list:
                stage = item.get("related_journey_stage", "Unknown Stage")
                item_copy = item.copy()
                item_copy.pop("related_journey_stage", None)
                nested.setdefault(stage, []).append(item_copy)
            self.core_page_types = flat_list
            self.core_page_types_nested = nested
        else:
            # 新格式：嵌套结构
            transformed: List[Dict] = []
            self.core_page_types_nested = {}
            for stage_name, type_list in parsed.items():
                if not isinstance(type_list, list):
                    continue
                for item in type_list:
                    if isinstance(item, dict):
                        item_cp = item.copy()
                        item_cp["related_journey_stage"] = stage_name
                        self.core_page_types_nested.setdefault(stage_name, []).append({k:v for k,v in item.items() if k!="related_journey_stage"})
                        transformed.append(item_cp)
            self.core_page_types = transformed
    
    def _load_core_page_types(self, file_path: str):
        """从文件加载核心页面类型"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            nested = data.get("core_page_types", {})
            flat = []
            for stage, items in nested.items():
                for it in items:
                    item_cp = it.copy()
                    item_cp["related_journey_stage"] = stage
                    flat.append(item_cp)
            
            self.core_page_types_nested = nested
            self.core_page_types = flat
            self.logger.info(f"✅ 从文件加载核心页面类型: {len(flat)} 个类型")
            
        except Exception as e:
            self.logger.error(f"❌ 加载核心页面类型失败: {e}")

    def generate_llm_planning(self, year_links_map: Dict[str, List[str]], company_url: str, crawl_num: int = 15) -> str:
        """
        生成LLM规划结果并保存
        
        Args:
            year_links_map: 年份到链接列表的映射
            company_url: 公司URL标识符
            crawl_num: 每年推荐的核心URL数量
            
        Returns:
            输出文件路径
        """
        self.logger.info(f"🤖 开始生成LLM规划...")
        
        # 准备输出目录和文件
        output_dir = os.path.join("outputs", company_url)
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f"{company_url}_llm_planning.json")
        
        # 检查是否已存在结果
        existing_results = {}
        if os.path.exists(output_file):
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                existing_results = data.get("yearly_analysis_results", {})
                self.logger.info(f"✅ 加载已存在的规划结果: {len(existing_results)} 年")
            except Exception as e:
                self.logger.warning(f"⚠️ 加载已存在规划结果失败: {e}")
        
        # 确保核心页面类型已加载
        if not self.core_page_types:
            core_types_file = os.path.join(output_dir, f"{company_url}_core_page_types.json")
            if os.path.exists(core_types_file):
                self._load_core_page_types(core_types_file)
            else:
                raise RuntimeError("核心页面类型未生成，请先运行 generate_core_page_types()")
        
        # 编译正则表达式模式
        self._compile_core_type_patterns()
        
        # 按年处理
        yearly_analysis = existing_results.copy()
        
        for year, valid_links in year_links_map.items():
            if year in yearly_analysis:
                self.logger.info(f"⏩ {year} 年规划已存在，跳过")
                continue
            
            self.logger.info(f"🔍 处理 {year} 年的规划...")
            
            try:
                # 分类候选URLs
                classified_urls = self._classify_candidate_urls(year, valid_links)
                
                # LLM选择核心URLs
                llm_analysis = self._select_core_urls_from_classification(year, classified_urls, crawl_num)
                
                # 优化爬取策略
                final_analysis = self._optimize_crawl_strategy(llm_analysis, valid_links, year, enforce_in_valid=False)
                
                # 合并classified_urls中的信息（方便后续排查）
                final_analysis["classified_urls_count"] = len(classified_urls) 
                final_analysis["classified_urls"] = classified_urls

                yearly_analysis[year] = final_analysis
                
                self.logger.info(f"✅ {year} 年规划完成: 推荐 {len(final_analysis.get('recommended_crawl_pages', []))} 个核心URL")
                
                # 增量写入、断点续跑
                self._write_planning_file(output_file, company_url, yearly_analysis)
                
            except Exception as e:
                self.logger.error(f"❌ {year} 年规划失败: {e}")
                # 失败时不保存该年份结果，让后续运行重新尝试
        
        # 最终汇总保存（再次写入，确保时间戳为最终完成时间）
        self._write_planning_file(output_file, company_url, yearly_analysis)
        total_urls = sum(len(data.get("recommended_crawl_pages", [])) for data in yearly_analysis.values())
        self.logger.info(f"💾 LLM规划全部年份处理完成，共 {total_urls} 个推荐URL已保存到: {output_file}")
        
        return output_file
    
    def _compile_core_type_patterns(self):
        """编译核心页面类型的正则表达式模式"""
        if self._compiled_patterns:
            return

        # 确保有嵌套映射
        nested: Dict[str, List[Dict]] = self.core_page_types_nested
        if not nested:
            nested = {}
            for item in self.core_page_types:
                stage = item.get("related_journey_stage", "Unknown Stage")
                item_cp = item.copy()
                item_cp.pop("related_journey_stage", None)
                nested.setdefault(stage, []).append(item_cp)
            self.core_page_types_nested = nested

        compiled: List[Tuple[str, str, "re.Pattern", int]] = []

        for stage, type_list in nested.items():
            for type_obj in type_list:
                type_name = type_obj.get("type_name", "Unknown")
                for raw_pat in type_obj.get("typical_url_patterns", []):
                    # 特殊处理根路径模式
                    if raw_pat.strip() == "/":
                        pat_regex = r"^/$"  # 严格匹配根路径
                    else:
                        # 转换通配符模式为正则表达式
                        pat_regex = re.escape(raw_pat).replace(r"\\*", ".*")
                    
                    try:
                        regex = re.compile(pat_regex, re.IGNORECASE)
                    except re.error:
                        self.logger.debug(f"⚠️ 无效的正则表达式模式 {raw_pat}，跳过")
                        continue
                    
                    compiled.append((stage, type_name, regex, len(raw_pat)))

        # 按模式长度排序，确保更具体的模式优先匹配
        compiled.sort(key=lambda x: -x[3])
        self._compiled_patterns = compiled
    
    def _classify_candidate_urls(self, year: str, valid_links: List[str], homepage_url: str = "") -> List[Dict]:
        """使用正则表达式模式分类候选URLs"""
        results: List[Dict] = []

        # 获取主域名用于过滤
        home_host = ""
        if homepage_url:
            home_host = self._get_home_host(homepage_url)

        for url in valid_links:
            # 提取真实站点路径
            real_part = url
            candidate_host = ""
            
            if "web.archive.org" in url:
                # 从Wayback URL中提取原始URL
                m = re.search(r"/web/\d+/(https?://.*)", url)
                if m:
                    underlying = m.group(1)
                    # 修正常见错误
                    if underlying.startswith("http:/") and not underlying.startswith("http://"):
                        underlying = underlying.replace("http:/", "http://", 1)
                    if underlying.startswith("https:/") and not underlying.startswith("https://"):
                        underlying = underlying.replace("https:/", "https://", 1)
                    
                    parsed_under = urllib.parse.urlparse(underlying)
                    candidate_host = parsed_under.netloc.lower()
                    
                    # 去掉端口号和www前缀
                    if ":" in candidate_host:
                        candidate_host = candidate_host.split(":")[0]
                    if candidate_host.startswith("www."):
                        candidate_host = candidate_host[4:]
                    
                    # 为regex匹配做准备
                    real_part = parsed_under.path
                    if real_part == "":
                        real_part = "/"
                    if parsed_under.query:
                        real_part += '?' + parsed_under.query
                # else:
                #     # Fall back to stripping manually
                #     real_part = re.sub(r"^https://web\.archive\.org/web/\d+/", "", url)
            else:
                parsed = urllib.parse.urlparse(url)
                candidate_host = parsed.netloc.lower()
                real_part = parsed.path
                if real_part == "":
                    real_part = "/"
                if parsed.query:
                    real_part += '?' + parsed.query

            # 域名过滤
            if home_host and candidate_host and candidate_host != home_host and candidate_host != f"www.{home_host}":
                continue

            # 正则匹配
            matched = False
            for stage, type_name, regex, pattern_len in self._compiled_patterns:
                if regex.match(real_part):
                    results.append({
                        'url': url,
                        'customer_journey_stage': stage,
                        'type_name': type_name
                    })
                    matched = True
                    break

        self.logger.info(f"✅ URL正则匹配完成，共过滤出{len(results)}/{len(valid_links)}个classified_urls")
        return results
    
    def _get_home_host(self, homepage_url: str) -> str:
        """获取主页对应的主域名"""
        parsed = urllib.parse.urlparse(homepage_url)
        host = parsed.netloc.lower()

        # 处理Wayback URL
        if 'web.archive.org' in host:
            m = re.search(r"/web/\d+/(https?://[^/]+)", homepage_url)
            if m:
                underlying = m.group(1)
                # 修正常见错误
                if underlying.startswith("http:/") and not underlying.startswith("http://"):
                    underlying = underlying.replace("http:/", "http://", 1)
                if underlying.startswith("https:/") and not underlying.startswith("https://"):
                    underlying = underlying.replace("https:/", "https://", 1)               
                host = urllib.parse.urlparse(underlying).netloc.lower()

        # 去掉端口号和www前缀
        if ':' in host:
            host = host.split(':')[0]
        if host.startswith('www.'):
            host = host[4:]
        return host
    
    def _select_core_urls_from_classification(self, year: str, classified_urls: List[Dict], crawl_num: int = 15) -> Dict:
        """调用LLM选择最具代表性的URLs"""
        classification_json = json.dumps(classified_urls, ensure_ascii=False, indent=2)

        prompt = (
            f"You are a highly precise e-commerce analysis engine. Based on the classified URL list below, select the most core and important {crawl_num} URLs.\n\n"
            f"<selection_rules>\n"
            # f"1.[IMPORTANT!!!] Final count **must be exactly {crawl_num}** (unless total classified URLs < {crawl_num}, then return all).\n"
            # f"1. Cover ALL six journey stages (Browse, Search, Decision-Making, Purchase, After-Sales, Customer Retention), and provide 2-3 URLs for EACH stage.\n"
            # f"2. Do NOT select more than two URLs having the SAME type_name.\n"
            f"1. Identify and prioritize URLs that are core, important, and valuable to the customer.\n"
            f"2. Cover ALL six journey stages (Awareness, Interest, Consideration, Decision, Fulfillment, Retention).\n"
            f"3. Ensure that type_name of the selected URLs are well-diversified and not concentrated.\n"
            f"4. Please choose English URLs only."
            # f"4. [IMPORTANT!!!] Final count **must be exactly {crawl_num}** (unless total classified URLs < {crawl_num}, then return all"
            f"</selection_rules>\n\n"
            f"<classified_urls total=\"{len(classified_urls)}\">\n```json\n{classification_json}\n```\n</classified_urls>\n\n"
            f"<output_format_instructions>Output ONLY the JSON object starting with '{{' and ending with '}}', using the schema: \n"
            f"{{\n  \"core_url_recommendations\": {{\n    \"recommended_url_list\": [\n      {{\n        \"url\": \"...\",\n        \"customer_journey_stage\": \"...\",\n        \"type_name\": \"...\",\n        \"selection_reason\": \"...\"\n      }}\n    ],\n    \"total_recommendations\": {crawl_num},\n    \"coverage_scenario_types\": [\"Awareness\", \"Interest\", \"Consideration\", \"Decision\", \"Fulfillment\", \"Retention\"]\n }}\n}}\n"
            f"</output_format_instructions>"
        )
        
        llm_resp = self._call_llm(prompt, model=self.medium_model, task_tag="选择核心URLs")
        parsed = self._parse_llm_response(llm_resp)
        return parsed
    
    def _optimize_crawl_strategy(self, llm_analysis: Dict, valid_content_urls: List[str], year: str, *, enforce_in_valid: Optional[bool] = None,) -> Dict:
        """Generate final crawl list.

        Args:
            enforce_in_valid: If provided, overrides self.enforce_recommended_in_valid_list for this call.
        """
        # 直接提取LLM推荐的核心URLs
        recommended_urls = []
        core_url_data = llm_analysis.get("core_url_recommendations", {})

        enforce = True if enforce_in_valid is None else enforce_in_valid
        
        if core_url_data and "recommended_url_list" in core_url_data:
            for url_info in core_url_data["recommended_url_list"]:
                url_str = url_info["url"] if isinstance(url_info, dict) else url_info
                
                if enforce:
                    if url_str in valid_content_urls:
                        recommended_urls.append(url_str)
                else:
                    recommended_urls.append(url_str)
        
        # 去重保持顺序
        recommended_urls = list(dict.fromkeys(recommended_urls))
        
        # 统计重叠数量
        overlap_count = sum(1 for u in recommended_urls if u in valid_content_urls)
        
        # 如果没有推荐URL，使用前10个有效URL
        if not recommended_urls:
            recommended_urls = valid_content_urls[:10]
            self.logger.warning(f"LLM推荐URLs不在有效列表中，使用前 {len(recommended_urls)} 个有效URLs")
        
        self.logger.info(f"✅ URL推荐完成: {len(recommended_urls)} 个推荐，{overlap_count} 个在有效页面内")

        # 构建分析结果
        analysis_result = {
            "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "using_real_llm": True,
            "llm_model": self.medium_model,
            "year": year,
            "discovered_links_count": len(valid_content_urls),
            "valid_content_urls_count": len(valid_content_urls),
            "recommended_crawl_pages": recommended_urls,
            "recommended_pages_count": len(recommended_urls),
            "recommended_in_valid_overlap": overlap_count,
            "enforce_recommended_in_valid_list": enforce,
            "core_url_details": core_url_data
        }
        
        return analysis_result
    
    def _call_llm(self, prompt: str, model: Optional[str] = None, *, task_tag: Optional[str] = None) -> str:
        """调用LLM API"""
        try:
            model_to_use = model if model else self.medium_model
            
            tag_txt = f" [{task_tag}]" if task_tag else ""
            self.logger.info(f"🤖 调用LLM模型{tag_txt}: {model_to_use}")
            
            response = self.client.chat.completions.create(
                model=model_to_use,
                messages=[
                    {"role": "system", "content": "You are a professional e-commerce website analysis expert, skilled in differentiated analysis for different years. Please respond in English and strictly follow the required JSON format."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=30000
            )
            
            response_content = response.choices[0].message.content
            self.logger.info(f"✅ LLM响应接收成功{tag_txt}")
            
            return response_content
            
        except Exception as e:
            self.logger.error(f"❌ LLM API调用失败: {e}")
            raise e
    
    def _parse_llm_response(self, response: str) -> Dict:
        """解析LLM响应"""
        try:
            # 提取JSON
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
            else:
                # 尝试定位对象或数组
                obj_start = response.find("{")
                arr_start = response.find("[")

                if obj_start == -1 and arr_start == -1:
                    raise ValueError("响应中未找到JSON")

                # 优先处理对象
                if obj_start != -1 and (arr_start == -1 or obj_start < arr_start):
                    json_start = obj_start
                    json_end = response.rfind("}") + 1
                    json_str = response[json_start:json_end]
                else:
                    json_start = arr_start
                    json_end = response.rfind("]") + 1
                    json_str = response[json_start:json_end]
            
            parsed = json.loads(json_str)
            return parsed
            
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.error(f"❌ LLM响应解析失败: {e}")
            raise Exception(f"LLM响应格式错误，无法解析分析结果: {e}")

    def load_llm_planning(self, company_url: str) -> Dict[str, Dict]:
        """加载已保存的LLM规划结果"""
        output_dir = os.path.join("outputs", company_url)
        planning_file = os.path.join(output_dir, f"{company_url}_llm_planning.json")
        
        if not os.path.exists(planning_file):
            self.logger.error(f"❌ 规划文件不存在: {planning_file}")
            return {}
        
        try:
            with open(planning_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            yearly_results = data.get("yearly_analysis_results", {})
            self.logger.info(f"✅ 成功加载 {len(yearly_results)} 年的规划数据")
            return yearly_results
            
        except Exception as e:
            self.logger.error(f"❌ 加载规划文件失败: {e}")
            return {}

    # ----------------- 新增工具方法 -----------------
    def _write_planning_file(self, output_file: str, company_url: str, yearly_analysis: Dict[str, Dict]):
        """将规划结果写入文件（用于增量保存）"""
        try:
            result_data = {
                "agent_version": "LLM_Planner_v1.0",
                "company_url": company_url,
                "export_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "yearly_analysis_results": yearly_analysis
            }
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)
            self.logger.debug(f"💾 已增量写入规划文件: {output_file}（共 {len(yearly_analysis)} 年）")
        except Exception as e:
            self.logger.warning(f"⚠️ 增量写入规划文件失败: {e}")


if __name__ == "__main__":
    # 测试代码
    api_key = "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"
    planner = LLMPlanner(api_key)
    print("LLM规划器初始化完成")
