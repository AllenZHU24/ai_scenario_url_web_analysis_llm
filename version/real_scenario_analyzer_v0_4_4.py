#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Real LLM-Driven Scenario Analyzer v0.4
按"先规划→立刻识别"逐年流式执行，支持断点续跑。
"""

import json
from typing import Dict, List, Set, Tuple, Optional
import logging
from datetime import datetime
import re
import time

import importlib.util
import sys
import pathlib, os

# Dynamically import modules with dots in name
spec = importlib.util.spec_from_file_location("real_llm_planning_agent_v0_4_4", str(pathlib.Path(__file__).resolve().parent / "real_llm_planning_agent_v0_4_4.py"))
real_llm_planning_agent_v0_4_4 = importlib.util.module_from_spec(spec)
sys.modules["real_llm_planning_agent_v0_4_4"] = real_llm_planning_agent_v0_4_4
spec.loader.exec_module(real_llm_planning_agent_v0_4_4)

RealLLMPlanningAgentV3 = real_llm_planning_agent_v0_4_4.RealLLMPlanningAgentV3
from url_discovery import URLDiscovery

class RealScenarioAnalyzerV3:
    """Real LLM-Driven Scenario Analyzer (English Version) - Focused on core scenario identification"""
    
    # ------------------------------------------------------------------
    # 🔥 Preparation
    # ------------------------------------------------------------------
    
    def __init__(self, api_key: str):
        """Initialize scenario analyzer"""
        self.planning_agent = RealLLMPlanningAgentV3(api_key=api_key)
        self.url_discovery = URLDiscovery()
        
        # Logger first
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)

        # Analysis results storage
        self.yearly_scenario_data = {}
        self.analysis_summary = {}
        
        # Micro-scenario definitions
        self.micro_scenarios = self._load_scenario_definitions()
        
        # 已加载过的输出文件路径占位
        self.planning_output_path: Optional[str] = None
        self.scenario_output_path: Optional[str] = None

        # Company-specific output directory (set in run_complete_analysis)
        self.output_dir: Optional[str] = None

        # Consolidated links cache {year: [links]}
        self._links_cache: Dict[str, List[str]] = {}
        self._links_cache_path: Optional[str] = None
    
    def _load_scenario_definitions(self) -> Dict:
        """Load micro-scenario definitions from external JSON file"""
        try:
            base_dir = pathlib.Path(__file__).resolve().parent
            scenarios_file = base_dir / "inputs" / "micro_scenarios_definitions_v0.3.json"
            with open(scenarios_file, 'r', encoding='utf-8') as f:
                scenarios_data = json.load(f)
            
            self.logger.info(f"✅ Successfully loaded {scenarios_data.get('total_scenarios', 0)} micro-scenarios from {scenarios_file}")
            return scenarios_data["scenarios"]
            
        except FileNotFoundError:
            self.logger.error(f"❌ Scenario definitions file not found: {scenarios_file}")
            self.logger.error("Please ensure inputs/micro_scenarios_definitions_v0.3.json exists")
            return {}
        except json.JSONDecodeError as e:
            self.logger.error(f"❌ Error parsing scenario definitions JSON: {e}")
            return {}
        except KeyError as e:
            self.logger.error(f"❌ Missing required key in scenario definitions: {e}")
            return {}

    def run_complete_analysis(self, historical_urls: List[Tuple[str, str]], company_url: str = None):
        """Run analysis in an incremental, year-by-year manner with breakpoint resume."""

        if not company_url:
            company_url = "company"

        # Prepare company-specific output directory
        self.output_dir = os.path.join("outputs", company_url)
        os.makedirs(self.output_dir, exist_ok=True)

        # 输出目录已确定，让 _load_existing_outputs 负责加载所有缓存文件

        self.logger.info("🚀 Starting incremental LLM scenario analysis workflow... Output dir: %s", self.output_dir)

        # 0. 预加载已有输出，实现断点续跑
        self._load_existing_outputs()

        # ------------------------------------------------------------
        # 🔥 v0.4.4 Unified Planning Workflow (website-level → yearly)
        # ------------------------------------------------------------
        self.logger.info("🔄 Starting new unified planning workflow (v0.4.4)...")

        # Step A: Discover and cache filtered links (with resume support)
        year_links_map: Dict[str, List[str]] = {}
        for year, url in historical_urls:
            if year not in year_links_map:
                year_links_map[year] = self._get_filtered_links_for_year(year, url)

        # Step B: Identify unified core page types using high-performance model
        if not self.planning_agent.core_page_types:
            self.logger.info("🧠 [Step B] Identifying core page types via LLM…")
            self.planning_agent.identify_core_page_types(year_links_map)
            # -- 导出 core_page_types --
            self.planning_agent.export_core_page_types(company_url=company_url)
        else:
            self.logger.info("⏩ [Step B] Core page types already available, skipping LLM call")

        # Step C: Year-specific core URL recommendation
        for year, url in historical_urls:
            if year in self.planning_agent.yearly_analysis:
                continue  # already done via resume
            valid_links = year_links_map.get(year, [])
            self.logger.info("🤖 [Step C] Recommending core URLs for %s", year)
            try:
                self.planning_agent.recommend_core_urls_for_year(year, url, valid_links)
                # Export after each year
                self.planning_output_path = self.planning_agent.export_analysis_results(company_url=company_url)
            except Exception as e:
                self.logger.error("❌ Core URL recommendation failed for %s: %s", year, e)

        # Step D: Scenario identification – same as before but using new planning results
        for year, _ in historical_urls:
            if year in self.yearly_scenario_data:
                continue
            planning_data = self.planning_agent.yearly_analysis.get(year)
            if planning_data:
                try:
                    self._identify_and_export_scenarios_for_year(year, planning_data, company_url)
                except Exception as e:
                    self.logger.error("❌ Scenario identification failed for %s: %s", year, e)

        # Final summary and exit
        self._generate_analysis_summary(company_url)
        self.logger.info("✅ Unified analysis workflow completed!")
        return

    def _load_existing_outputs(self):
        """Load existing JSON outputs to support breakpoint resume."""

        if not self.output_dir:
            return

        company_name = os.path.basename(self.output_dir)
        planning_file = os.path.join(self.output_dir, f"{company_name}_llm_planning_v0.4.4_result.json")

        scenario_file = os.path.join(self.output_dir, f"{company_name}_scenario_v0.4.4_result.json")

        if planning_file:
            self.planning_agent.load_existing_results(planning_file)

        # 加载场景识别结果
        if os.path.exists(scenario_file):
            try:
                with open(scenario_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                historical_scenarios = data.get("yearly_detailed_results", {})
                if isinstance(historical_scenarios, dict):
                    self.yearly_scenario_data.update(historical_scenarios)
                    self.logger.info("✅ Loaded existing scenario results for %d years", len(historical_scenarios))
            except Exception as e:
                self.logger.warning("⚠️ Failed to load existing scenario results: %s", e)

        # Links cache consolidated
        self._links_cache_path = os.path.join(self.output_dir, f"{company_name}_filtered_links_v0.4.4_result.json")

        if os.path.exists(self._links_cache_path):
            try:
                with open(self._links_cache_path, "r", encoding="utf-8") as f:
                    self._links_cache = json.load(f)
                self.logger.info("🔄 Loaded links cache (%d years)", len(self._links_cache))
            except Exception as e:
                self.logger.warning("⚠️ Failed to load links cache: %s", e)

        # Core page types cache
        core_types_file = os.path.join(self.output_dir, f"{company_name}_core_page_types_v0.4.4_result.json")
        if os.path.exists(core_types_file) and not self.planning_agent.core_page_types:
            try:
                with open(core_types_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    nested = data.get("core_page_types", {})
                    flat = []
                    for stage, items in nested.items():
                        for it in items:
                            item_cp = it.copy()
                            item_cp["related_journey_stage"] = stage
                            flat.append(item_cp)
                    self.planning_agent.core_page_types_nested = nested
                    self.planning_agent.core_page_types = flat
                    self.logger.info("🔄 Loaded cached core page types (%d) from disk", len(flat))
            except Exception as e:
                self.logger.warning("⚠️ Failed to load core page types cache: %s", e)

    def _identify_and_export_scenarios_for_year(self, year: str, planning_data: Dict, company_url: str):
        """Identify scenarios for a single year and immediately export incremental results."""

        self.logger.info("🔍 Identifying scenarios for year %s ...", year)

        crawl_urls = planning_data["recommended_crawl_pages"]
        year_scenarios: Set[str] = set()
        successful_pages = 0

        for i, url in enumerate(crawl_urls):
            self.logger.info("📄 [%s] Analyzing page %d/%d", year, i + 1, len(crawl_urls))
            try:
                page_scenarios = self._identify_scenarios_in_page(url)
                if page_scenarios:
                    year_scenarios.update(page_scenarios)
                successful_pages += 1
            except Exception as e:
                self.logger.warning("❌ Page analysis failed %s: %s", url, e)
            time.sleep(1)

        self.yearly_scenario_data[year] = {
            "identified_scenarios": list(year_scenarios),
            "total_scenario_count": len(year_scenarios),
            "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "llm_recommended_pages_count": len(crawl_urls),
            "successful_analysis_pages_count": successful_pages,
            "page_success_rate": f"{successful_pages}/{len(crawl_urls)}",
            "stage_distribution": self._categorize_scenarios_by_stage(year_scenarios),
            "using_llm_recommendations": planning_data.get("using_real_llm", False),
        }

        self.logger.info("✅ Year %s scenario identification completed: %d scenarios", year, len(year_scenarios))

        # 每年完成后立即导出
        self._generate_analysis_summary(company_url)

    def _identify_scenarios_in_page(self, url: str) -> Set[str]:
        """Identify micro-scenarios in single page"""
        
        scenarios = set()
        
        try:
            # Get page content
            content = self.url_discovery.get_page_content_for_analysis(url, max_length=None) 
            if not content:
                return scenarios
            
            content_lower = content.lower()
            
            # Extract year from URL and create filename
            self._save_content_to_txt(url, content_lower)
            
            # Traverse all micro-scenario definitions for matching
            for stage, stage_scenarios in self.micro_scenarios.items():
                for scenario_id, scenario_info in stage_scenarios.items():
                    scenario_name = scenario_info['name']
                    keywords = scenario_info['keywords']
                    
                    # Check if any keyword matches
                    for keyword in keywords:
                        if keyword.lower() in content_lower:
                            scenarios.add(f"{scenario_id}_{scenario_name}")
                            break  # Found match, move to next scenario
            
            return scenarios
            
        except Exception as e:
            self.logger.warning(f"Scenario identification failed {url}: {e}")
            return scenarios
    
    def _save_content_to_txt(self, url: str, content_lower: str):
        """Save content_lower to txt file with specified naming format"""
        try:
            # Extract year from URL (format: https://web.archive.org/web/YYYYMMDDHHMMSS/...)
            year_match = re.search(r'/web/(\d{4})\d{10}/', url)
            if year_match:
                year = year_match.group(1)
            else:
                # Fallback: use 0000 if can't extract from URL
                year = '0000'
            
            # Generate timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Create filename
            filename = f"{year}_{timestamp}.txt"
            
            # Ensure output directory exists (company-specific)
            base_dir = pathlib.Path(self.output_dir if self.output_dir else pathlib.Path(__file__).resolve().parent / "outputs")
            output_dir = base_dir / "websites"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Full file path
            file_path = output_dir / filename
            
            # Write content to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"来源URL: {url}\n")
                f.write("=" * 80 + "\n\n")
                f.write(content_lower)
            
            self.logger.info(f"💾 Content saved to: {file_path}")
            
        except Exception as e:
            self.logger.warning(f"Failed to save content to txt file for {url}: {e}")
    
    def _categorize_scenarios_by_stage(self, scenarios: Set[str]) -> Dict[str, int]:
        """Categorize scenarios by stage"""
        stage_count = {
            "Awareness Stage": 0,
            "Interest Stage": 0, 
            "Consideration Stage": 0,
            "Decision Stage": 0,
            "Fulfillment Stage": 0,
            "Retention Stage": 0
        }
        
        for scenario in scenarios:
            scenario_id = scenario.split('_')[0]
            if scenario_id.startswith('1.'):
                stage_count["Awareness Stage"] += 1
            elif scenario_id.startswith('2.'):
                stage_count["Interest Stage"] += 1
            elif scenario_id.startswith('3.'):
                stage_count["Consideration Stage"] += 1
            elif scenario_id.startswith('4.'):
                stage_count["Decision Stage"] += 1
            elif scenario_id.startswith('5.'):
                stage_count["Fulfillment Stage"] += 1
            elif scenario_id.startswith('6.'):
                stage_count["Retention Stage"] += 1
                
        return stage_count 

    def _generate_analysis_summary(self, company_url: str = None):
        """Generate analysis summary"""
        
        if not self.yearly_scenario_data:
            return
        
        total_scenarios = sum(data["total_scenario_count"] for data in self.yearly_scenario_data.values())
        
        self.analysis_summary = {
            "analysis_version": "Real_Scenario_Analyzer_v0.4",
            "company_url": company_url,
            "generation_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "focus": "Core scenario identification functionality",
            
            "core_statistics": {
                "analyzed_years_count": len(self.yearly_scenario_data),
                "total_identified_scenarios": total_scenarios,
                "average_scenarios_per_year": round(total_scenarios / len(self.yearly_scenario_data), 1)
            },
            
            "yearly_detailed_results": self.yearly_scenario_data
        }
        
        # 动态生成输出文件名 (company-specific dir)
        if company_url:
            output_dir = os.path.join("outputs", company_url)
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{company_url}_scenario_v0.4.4_result.json")
        else:
            os.makedirs("outputs", exist_ok=True)
            output_file = os.path.join("outputs", "real_scenario_analysis_v0.4_summary.json")
        
        # Export analysis summary
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.analysis_summary, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"Scenario analysis results exported to: {output_file}")
        return output_file

    def _get_filtered_links_for_year(self, year: str, homepage_url: str) -> List[str]:
        """Discover links for a year, using consolidated JSON cache for resume."""

        # Return from in-memory cache if exists
        if year in self._links_cache:
            self.logger.info("🔄 [Links] Using cached links for %s (%d links)", year, len(self._links_cache[year]))
            return self._links_cache[year]

        # Perform discovery
        self.logger.info("🌐 [Links] Discovering internal links for %s", year)
        links_list = self.planning_agent.discover_filtered_links(homepage_url, max_links=10000)

        # Update cache and persist
        self._links_cache[year] = links_list
        try:
            with open(self._links_cache_path, "w", encoding="utf-8") as f:
                json.dump(self._links_cache, f, ensure_ascii=False, indent=2)
            self.logger.info("💾 [Links] Consolidated cache updated (%s)", self._links_cache_path)
        except Exception as e:
            self.logger.warning("⚠️ [Links] Failed to save consolidated cache: %s", e)

        return links_list


def extract_company_url_from_filepath(file_path: str) -> str:
    """从文件路径中提取公司URL"""
    import os
    # 获取文件名（去除路径和扩展名）
    filename = os.path.basename(file_path)
    # 去除扩展名
    company_url = os.path.splitext(filename)[0]
    return company_url


def verify_scenario_definitions():
    """Verify scenario definition completeness"""
    print("🔍 Verifying micro-scenario definition completeness...")
    
    try:
        base_dir = pathlib.Path(__file__).resolve().parent
        scenarios_file = base_dir / "inputs" / "micro_scenarios_definitions_v0.3.json"
        with open(scenarios_file, 'r', encoding='utf-8') as f:
            scenarios_data = json.load(f)
        
        scenarios = scenarios_data["scenarios"]
        total_count = 0
        
        for stage, stage_scenarios in scenarios.items():
            count = len(stage_scenarios)
            print(f"  {stage}: {count} scenarios")
            total_count += count
        
        print(f"\n✅ Total: {total_count} micro-scenarios")
        print(f"📄 Loaded from: {scenarios_file}")
        
        # Get expected count from JSON metadata
        expected_count = scenarios_data.get("total_scenarios", 62)
        if total_count == expected_count:
            print("🎉 Scenario definitions complete!")
            return True
        else:
            print(f"❌ Scenario count mismatch! Should be {expected_count}, actual is {total_count}")
            return False
            
    except Exception as e:
        print(f"❌ Failed to verify scenario definitions: {e}")
        return False