#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Real LLM-Driven AI Planning Agent v0.4
English Version: Resolving unified strategy and invalid webpage filtering issues
"""

import json
import logging
import os
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from openai import OpenAI
from url_discovery import URLDiscovery
import pathlib
import re
import urllib.parse
import random

class RealLLMPlanningAgentV3:
    """Enhanced Real LLM Smart Planning Agent (English Version)"""
    
    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1"):
        """Initialize Enhanced LLM Planning Agent"""
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        
        self.url_discovery = URLDiscovery()
        self.yearly_analysis = {}
        self.adaptive_strategies = {}  # Store adaptive strategies for each year
        
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)
        
        # --- 模型配置 ---
        self.high_model = "google/gemini-2.5-pro"          # 高性能模型（Step 1）
        self.medium_model = "openai/gpt-4o-mini"   # 中等性能模型（Step 2）

        # 默认使用中等性能模型
        self.model = self.medium_model

        # 跨年份统一的核心页面类型列表（由Step 1产生）
        self.core_page_types: List[Dict] = []
        self.core_page_types_nested: Dict[str, List[Dict]] = {}
        
        self.logger.info(f"🚀 LLM Planning Agent v0.4 (English) initialized")
        self.logger.info(f"⚙️ Model configuration: {self.model}")
        
        # Load scenario reference from external file
        self.scenario_reference = self._load_scenario_reference()

    # ------------------------------------------------------------------
    # 🔥 Preparation
    # ------------------------------------------------------------------

    def _load_scenario_reference(self) -> str:
        """Load scenario reference from external JSON file and format as text"""
        try:
            base_dir = pathlib.Path(__file__).resolve().parent
            scenarios_file = base_dir / "inputs" / "micro_scenarios_definitions_v0.3.json"
            with open(scenarios_file, 'r', encoding='utf-8') as f:
                scenarios_data = json.load(f)
            
            # Format scenarios into text for LLM prompt
            total_scenarios = scenarios_data.get('total_scenarios', 0)
            reference_text = f"E-commerce User Journey Micro-Scenario Categories ({total_scenarios} scenarios total):\n"
            
            for stage_name, stage_scenarios in scenarios_data["scenarios"].items():
                scenario_names = []
                stage_ids = list(stage_scenarios.keys())
                for scenario_id, scenario_info in stage_scenarios.items():
                    scenario_names.append(scenario_info["name"])
                
                if stage_ids:
                    first_id = stage_ids[0].split('.')[0]
                    last_id = stage_ids[-1]
                    reference_text += f"{stage_name} ({first_id}.1-{last_id}): {', '.join(scenario_names)}\n"
            
            self.logger.info(f"✅ Successfully loaded scenario reference with {total_scenarios} scenarios")
            self.logger.info(f"📝 Scenario reference: {reference_text}")
            return reference_text
            
        except Exception as e:
            self.logger.error(f"❌ Failed to load scenario reference: {e}")
            # Fallback to a simplified reference
            return """E-commerce User Journey Micro-Scenario Categories:
            1. Browse Stage: Product browsing and discovery
            2. Search Stage: Search and filtering
            3. Decision-Making Stage: Product evaluation and comparison  
            4. Purchase Stage: Cart and checkout process
            5. After-Sales Stage: Order management and support
            6. Customer Retention Stage: Loyalty and engagement
            """

    # ------------------------------------------------------------------
    # 🔥 New unified planning workflow methods (v0.4.4)
    # ------------------------------------------------------------------
    def discover_filtered_links(self, homepage_url: str, max_links: int = 10000) -> List[str]:
        """Discover internal links and apply structural filtering only."""
        discovered = self.url_discovery.discover_internal_links(homepage_url, max_links=max_links)
        return self._filter_valid_links(discovered)

    #TODO:this function should be included by url_discovery.py (not here)
    def _filter_valid_links(self, links: List[str]) -> List[str]:
        """Pre-filtering: only filter technical files, no content checking (avoid duplicate requests)"""
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
            "URL filtering completed: %d/%d links passed (structure + reachability)",
            len(valid_links), len(links)
        )
        return valid_links

    def _is_meaningful_url(self, url: str) -> bool:
        """Judge whether URL is meaningful based on URL structure (filter technical files)"""
        # Filter out obvious technical files and static resources
        excluded_extensions = ['.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', 
                             '.pdf', '.xml', '.json', '.txt', '.zip', '.woff', '.ttf']
        excluded_paths = ['/static/', '/assets/', '/css/', '/js/', '/images/', '/img/', 
                         '/fonts/', '/media/', '/resources/', '/ajax/', '/api/']
        
        url_lower = url.lower()
        
        # Exclude technical file extensions
        if any(url_lower.endswith(ext) for ext in excluded_extensions):
            return False
        
        # Exclude technical paths
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

    def identify_core_page_types(self, all_year_links: Dict[str, List[str]], expected_types: int = 50) -> List[Dict]:
        """Step B: 利用高性能模型统一识别核心页面类型。"""

        if self.core_page_types:
            self.logger.info("🔄 Core page types already identified, skip recalculation")
            return self.core_page_types

        # 合并并抽样 URL 以控制 prompt 长度
        merged: List[str] = []
        for links in all_year_links.values():
            merged.extend(links)
        unique_links = list(dict.fromkeys(merged))  # 保序去重
        sample_links = unique_links[:]  # 抽样 300 条
        random.shuffle(sample_links)  # 随机打乱顺序，减轻 LLM 对 URL 顺序偏好

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

        llm_resp = self._call_real_llm(prompt, model=self.high_model, task_tag="Step B CoreType")
        parsed = self._parse_llm_response(llm_resp, year="ALL")

        # 兼容两种返回结构：
        # 1) {"core_page_types": [...]}  (老格式)
        # 2) {"Browse Stage": [...], ...} (新嵌套格式)

        if "core_page_types" in parsed:
            # old flat list; build nested mapping by stage key if provided
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

        self.logger.info("✅ Identified %d core page types", len(self.core_page_types))
        return self.core_page_types

    def recommend_core_urls_for_year(
        self,
        year: str,
        homepage_url: str,
        valid_links: List[str],
        crawl_num: int = 15,
    ) -> Dict:
        """Step C: 根据统一核心页面类型，使用中性能模型为指定年份推荐核心 URL。"""

        if not self.core_page_types:
            raise RuntimeError("Core page types have not been identified. Run identify_core_page_types() first.")

        # ----------------------------
        # Step C.1: URL classification
        # ----------------------------
        classified_urls = self._classify_candidate_urls(year, valid_links, homepage_url)
        self.logger.info(f"🔄 Classified {len(classified_urls)} URLs for year {year}")

        # ----------------------------
        # Step C.2: Core URL selection
        # ----------------------------
        llm_analysis = self._select_core_urls_from_classification(year, classified_urls, crawl_num=crawl_num)

        # Post-process & fuzzy-match optimisation
        final = self._optimize_crawl_strategy(llm_analysis, valid_links, year, enforce_in_valid=False)

        # Also cache intermediate classification for transparency
        final["all_classified_urls_count"] = len(classified_urls) 
        final["all_classified_urls"] = classified_urls

        self.yearly_analysis[year] = final
        return final

    # ----------------------------
    # Step C.1: URL classification
    # ----------------------------
    def _classify_candidate_urls(self, year: str, valid_links: List[str], homepage_url: str = "") -> List[Dict]:
        """[Step C.1] Deterministically classify candidate URLs using regex patterns, without LLM.

        Returns a list[dict]: {"url", "customer_journey_stage", "type_name"}
        """

        import re, urllib.parse

        self._compile_core_type_patterns()

        results: List[Dict] = []

        # determine primary domain root from homepage_url for filtering external links
        home_host = self._get_home_host(homepage_url)

        for url in valid_links:
            # Step 1. Extract the *real* site path, stripping Wayback prefix if present.
            real_part = url
            candidate_host = ""
            if "web.archive.org" in url:
                # Capture underlying URL after timestamp
                m = re.search(r"/web/\d+/(https?://.*)", url)
                if m:
                    underlying = m.group(1)
                    # Fix common Wayback URL malformations  
                    if underlying.startswith("http:/") and not underlying.startswith("http://"):
                        underlying = underlying.replace("http:/", "http://", 1)
                    if underlying.startswith("https:/") and not underlying.startswith("https://"):
                        underlying = underlying.replace("https:/", "https://", 1)
                    parsed_under = urllib.parse.urlparse(underlying)
                    candidate_host = parsed_under.netloc.lower()
                    
                    # 去掉端口号
                    if ":" in candidate_host:
                        candidate_host = candidate_host.split(":")[0]
                    # 去掉 leading 'www.'
                    if candidate_host.startswith("www."):
                        candidate_host = candidate_host[4:]

                    # 为regex匹配做准备
                    real_part = parsed_under.path
                    if real_part == "":
                        real_part = "/"
                    if parsed_under.query:
                        real_part += '?' + parsed_under.query
                else:
                    # Fall back to stripping manually
                    real_part = re.sub(r"^https://web\.archive\.org/web/\d+/", "", url)
            else:
                parsed = urllib.parse.urlparse(url)
                candidate_host = parsed.netloc.lower()
                real_part = parsed.path
                if real_part == "":
                    real_part = "/"
                if parsed.query:
                    real_part += '?' + parsed.query

            # Step 2. Apply domain filter
            if candidate_host and not candidate_host.endswith(home_host):
                continue

            # Step 2.5. Filter out non-main subdomains (keep only exact match and www.)
            if candidate_host and candidate_host != home_host and candidate_host != f"www.{home_host}":
                continue

            # Step 3. Match against compiled regex patterns
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
            
        return results
    
    def _compile_core_type_patterns(self):
        """[Step C.1] Compile regex objects from typical_url_patterns for fast, deterministic matching.

        This method is idempotent; it only compiles once per agent instance.
        A helper to be called before any regex-based classification logic.
        """

        if getattr(self, "_compiled_patterns", None):  # Already compiled
            return

        import re

        # Ensure we have a nested mapping of stage -> List[page_type]
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
                    # Special-case root pattern to avoid matching every URL containing '/'
                    if raw_pat.strip() == "/":
                        pat_regex = r"^/$"  # strict root only
                    else:
                        # Convert simple wildcard patterns ( * ) to regex and escape everything else.
                        pat_regex = re.escape(raw_pat).replace(r"\\*", ".*")
                    # Compile as case-insensitive.
                    try:
                        regex = re.compile(pat_regex, re.IGNORECASE)
                    except re.error:
                        self.logger.debug("⚠️ Invalid regex generated from pattern %s; skipped", raw_pat)
                        continue
                    compiled.append((stage, type_name, regex, len(raw_pat)))

        # Ensure more specific (longer) patterns are evaluated first.
        compiled.sort(key=lambda x: -x[3])

        self._compiled_patterns = compiled

    def _get_home_host(self, homepage_url: str) -> str:
        """[Step C.1] Return the primary domain (without 'www.') for the website under analysis.

        Works for both normal URLs and Wayback Machine snapshot URLs.
        """
        parsed = urllib.parse.urlparse(homepage_url)
        host = parsed.netloc.lower()

        # Handle Wayback Machine snapshot URLs by extracting the underlying site host.
        if 'web.archive.org' in host:
            # attempt to extract underlying URL
            m = re.search(r"/web/\d+/(https?://[^/]+)", homepage_url)
            if m:
                underlying = m.group(1)
                # 修正常见的 http:/、https:/ 错误
                if underlying.startswith("http:/") and not underlying.startswith("http://"):
                    underlying = underlying.replace("http:/", "http://", 1)
                if underlying.startswith("https:/") and not underlying.startswith("https://"):
                    underlying = underlying.replace("https:/", "https://", 1)               
                host = urllib.parse.urlparse(underlying).netloc.lower()

        # Remove explicit port number (e.g., ':80', ':443') if present.
        if ':' in host:
            host = host.split(':')[0]
        # Strip leading 'www.' for canonical domain.
        if host.startswith('www.'):
            host = host[4:]
        return host
    
    # ----------------------------
    # Step C.2: Core URL selection
    # ----------------------------
    def _select_core_urls_from_classification(self, year: str, classified_urls: List[Dict], crawl_num: int = 15) -> Dict:
        """[Step C.2] Call LLM again to pick the most representative URLs following strict rules.

        Returns a dict expected by _optimize_crawl_strategy (has core_url_recommendations key).
        """

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
        llm_resp = self._call_real_llm(prompt, model=self.medium_model, task_tag="Step C.2 Select")
        parsed = self._parse_llm_response(llm_resp, year)
        return parsed

    # ------------------------------------------------------------------
    # 🔥 Supporting functions
    # ------------------------------------------------------------------
    def export_core_page_types(self, company_url: str, output_file: str = None):
        """Export unified core page types to a JSON file."""

        if not self.core_page_types:
            self.logger.warning("Core page types not generated yet; nothing to export")
            return None

        if company_url and not output_file:
            output_dir = os.path.join("outputs", company_url)
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{company_url}_core_page_types_v0.4.4_result.json")
        elif not output_file:
            os.makedirs("outputs", exist_ok=True)
            output_file = "outputs/core_page_types_v0.4.4_result.json"

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump({
                    "generation_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "core_page_types": self.core_page_types_nested or self.core_page_types
                }, f, ensure_ascii=False, indent=2)
            self.logger.info("💾 Core page types exported to %s", output_file)
            return output_file
        except Exception as e:
            self.logger.warning("⚠️ Failed to export core page types JSON: %s", e)
            return None


    def _call_real_llm(self, prompt: str, model: Optional[str] = None, *, task_tag: Optional[str] = None) -> str:
        """Call real LLM API with optional model override"""
        try:
            # 1. Determine model to use
            model_to_use = model if model else self.model

            # 2. Log current LLM model information with optional task tag
            tag_txt = f" [{task_tag}]" if task_tag else ""
            self.logger.info(f"🤖 Calling LLM model{tag_txt}: {model_to_use}")
            self.logger.debug(f"📝 Prompt length: {len(prompt)} characters")
            
            response = self.client.chat.completions.create(
                model=model_to_use,
                messages=[
                    {"role": "system", "content": "You are a professional e-commerce website analysis expert, skilled in differentiated analysis for different years. Please respond in English and strictly follow the required JSON format."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=30000
            )
            
            # 3. Log LLM response information
            response_content = response.choices[0].message.content
            self.logger.info(f"✅ LLM response received successfully{tag_txt}")
            self.logger.info(f"📊 Response length: {len(response_content)} characters")
            
            # # Log API usage statistics
            # if hasattr(response, 'usage'):
            #     usage = response.usage
            #     self.logger.info(f"📈 Token usage statistics: input={usage.prompt_tokens}, output={usage.completion_tokens}, total={usage.total_tokens}")
            
            return response_content
            
        except Exception as e:
            self.logger.error(f"❌ LLM API call failed: {e}")
            self.logger.error(f"🚨 Using model: {model_to_use}")
            raise e
    

    def _parse_llm_response(self, response: str, year: str) -> Dict:
        """Parse LLM response"""
        try:
            # Extract JSON (object or array) from LLM response
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
            else:
                # Try to locate either object '{' ... '}' or array '[' ... ']'
                obj_start = response.find("{")
                arr_start = response.find("[")

                if obj_start == -1 and arr_start == -1:
                    raise ValueError("No JSON found in response")

                # Prioritise object detection if both exist before array
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
            self.logger.error(f"LLM response parsing failed: {e}")
            raise Exception(f"LLM response format error, unable to parse analysis results: {e}")


    def _optimize_crawl_strategy(
        self,
        llm_analysis: Dict,
        valid_content_urls: List[str],
        year: str,
        *,
        enforce_in_valid: Optional[bool] = None,
    ) -> Dict:
        """Generate final crawl list.

        Args:
            enforce_in_valid: If provided, overrides self.enforce_recommended_in_valid_list for this call.
        """
        
        # Directly extract LLM recommended core URLs
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

        # 统计推荐 URL 与 valid_content_urls 的交集数量
        overlap_count = sum(1 for u in recommended_urls if u in valid_content_urls)

        
        # If LLM doesn't provide recommendations or recommended URLs are not in valid list, use first 10 valid content URLs
        if not recommended_urls:
            recommended_urls = valid_content_urls[:10]
            self.logger.warning(f"LLM recommended URLs not in valid content list, using first {len(recommended_urls)} valid content URLs")
        
        self.logger.info(
            "✅ URL recommendation finished: %d recommended, %d within valid pages (enforce=%s)",
            len(recommended_urls),
            overlap_count,
            enforce
        )

        # Build simplified analysis results - focus on core information only
        analysis_result = {
            "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "using_real_llm": True,
            "llm_model": self.model,
            "year": year,
            "discovered_links_count": len(valid_content_urls),
            "valid_content_urls_count": len(valid_content_urls),
            
            # Directly use LLM recommended URL list
            "recommended_crawl_pages": recommended_urls,
            "recommended_pages_count": len(recommended_urls),
            "recommended_in_valid_overlap": overlap_count,
            "enforce_recommended_in_valid_list": enforce,
            "core_url_details": core_url_data
        }
        
        return analysis_result

    def export_analysis_results(self, output_file: str = None, company_url: str = None):
        """Export yearly planning results (core URLs)"""
        if not self.yearly_analysis:
            self.logger.warning("No analysis results to export")
            return
        
        # 如果提供了company_url，自动生成文件名并放置在专属目录下
        if company_url and not output_file:
            output_dir = os.path.join("outputs", company_url)
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{company_url}_llm_planning_v0.4.4_result.json")
        elif not output_file:
            output_file = "outputs/real_llm_planning_v0.4.4_results.json"
        
        results = {
            "agent_version": "Real_LLM_Planning_Agent_v0.4",
            "company_url": company_url,
            "export_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "yearly_analysis_results": self.yearly_analysis
        }
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"Analysis results exported to: {output_file}")
        return output_file

    def load_existing_results(self, file_path: str):
        """Load previously exported planning results to enable breakpoint resume.

        Args:
            file_path: Path to an existing *_llm_planning_result.json file
        """
        try:
            if not os.path.exists(file_path):
                self.logger.info(f"🔍 No existing planning file found at {file_path}, starting fresh")
                return

            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 兼容性处理：不同版本可能字段名不同
            historical_results = (
                data.get("yearly_analysis_results")
                or data.get("yearly_analysis")
                or {}
            )
            if isinstance(historical_results, dict):
                already_years = list(historical_results.keys())
                self.yearly_analysis.update(historical_results)
                self.logger.info(
                    f"✅ Loaded existing planning results for {len(already_years)} years: {already_years}"
                )
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to load existing planning results: {e}")