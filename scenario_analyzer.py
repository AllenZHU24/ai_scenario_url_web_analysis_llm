#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
场景分析模块
负责分析网页内容并识别用户场景
"""

import json
import logging
import os
import re
import time
from typing import Dict, List, Set, Tuple, Optional
from datetime import datetime
import pathlib
from url_processing import URLProcessor


class ScenarioAnalyzer:
    """场景分析器"""
    
    def __init__(self):
        """初始化场景分析器"""
        self.url_processor = URLProcessor()
        self.logger = logging.getLogger(__name__)
        
        # 场景识别结果存储
        self.yearly_scenario_data = {}
        self.analysis_summary = {}
        
        # 微场景定义
        self.micro_scenarios = self._load_scenario_definitions()
        
        self.logger.info(f"🔍 场景分析器已初始化")
    
    def _load_scenario_definitions(self) -> Dict:
        """加载微场景定义"""
        try:
            base_dir = pathlib.Path(__file__).resolve().parent
            scenarios_file = base_dir / "inputs" / "1_scenario_mapping" / "micro_scenarios_definitions_v0.3.json"
            with open(scenarios_file, 'r', encoding='utf-8') as f:
                scenarios_data = json.load(f)
            
            self.logger.info(f"✅ 成功加载 {scenarios_data.get('total_scenarios', 0)} 个微场景")
            return scenarios_data["scenarios"]
            
        except Exception as e:
            self.logger.error(f"❌ 加载场景定义失败: {e}")
            return {}
    
    def analyze_scenarios_for_company(self, llm_planning_results: Dict[str, Dict], company_url: str) -> str:
        """
        基于LLM规划结果分析场景并保存
        
        Args:
            llm_planning_results: LLM规划结果，包含每年推荐的URLs
            company_url: 公司URL标识符
            
        Returns:
            输出文件路径
        """
        self.logger.info(f"🔍 开始分析场景: {company_url}")
        
        # 准备输出目录
        output_dir = os.path.join("outputs", company_url)
        os.makedirs(output_dir, exist_ok=True)
        websites_dir = os.path.join(output_dir, "websites")
        os.makedirs(websites_dir, exist_ok=True)
        
        # 输出文件路径
        output_file = os.path.join(output_dir, f"{company_url}_scenarios.json")
        
        # 检查是否已存在结果
        existing_results = {}
        if os.path.exists(output_file):
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                existing_results = data.get("yearly_detailed_results", {})
                self.logger.info(f"✅ 加载已存在的场景结果: {len(existing_results)} 年")
            except Exception as e:
                self.logger.warning(f"⚠️ 加载已存在场景结果失败: {e}")
        
        # 按年分析场景
        self.yearly_scenario_data = existing_results.copy()
        
        for year, planning_data in llm_planning_results.items():
            # 断点续跑
            if year in self.yearly_scenario_data:
                self.logger.info(f"⏩ {year} 年场景已存在，跳过")
                continue
            
            self.logger.info(f"🔍 分析 {year} 年的场景...")
            
            try:
                crawl_urls = planning_data.get("recommended_crawl_pages", [])
                if not crawl_urls:
                    self.logger.warning(f"❌ {year} 年没有推荐URL，跳过")
                    continue
                
                year_scenarios, successful_pages = self._analyze_scenarios_for_year(year, crawl_urls, websites_dir)
                
                self.yearly_scenario_data[year] = {
                    "identified_scenarios": list(year_scenarios),
                    "total_scenario_count": len(year_scenarios),
                    "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "llm_recommended_pages_count": len(crawl_urls),
                    "page_success_rate": f"{successful_pages}/{len(crawl_urls)}",
                    "stage_distribution": self._categorize_scenarios_by_stage(year_scenarios),
                }
                
                self.logger.info(f"✅ {year} 年场景分析完成: {len(year_scenarios)} 个场景")
                
                # 增量保存
                self._generate_analysis_summary(company_url)
                
            except Exception as e:
                self.logger.error(f"❌ {year} 年场景分析失败: {e}")
                self.yearly_scenario_data[year] = {
                    "identified_scenarios": [],
                    "total_scenario_count": 0,
                    "error": str(e)
                }
        
        # 生成并保存分析摘要
        output_file = self._generate_analysis_summary(company_url)
        
        return output_file
    
    def _analyze_scenarios_for_year(self, year: str, crawl_urls: List[str], websites_dir: str) -> Set[str]:
        """分析单年的场景"""
        year_scenarios: Set[str] = set()
        successful_pages = 0
        
        for i, url in enumerate(crawl_urls):
            self.logger.info(f"📄 [{year}] 分析页面 {i + 1}/{len(crawl_urls)}")
            try:
                page_scenarios = self._identify_scenarios_in_page(url, year, websites_dir)
                if page_scenarios:
                    year_scenarios.update(page_scenarios)
                successful_pages += 1
            except Exception as e:
                self.logger.warning(f"❌ 页面分析失败 {url}: {e}")
            
            time.sleep(1)  # 避免请求过于频繁
        
        return year_scenarios, successful_pages
    
    def _identify_scenarios_in_page(self, url: str, year: str, websites_dir: str) -> Set[str]:
        """识别单个页面中的微场景"""
        scenarios = set()
        
        try:
            # 获取页面内容
            content = self.url_processor.get_page_content(url, max_length=None)
            if not content:
                return scenarios
            
            content_lower = content.lower()
            
            # 保存内容到txt文件
            self._save_content_to_txt(url, content_lower, year, websites_dir)
            
            # 遍历所有微场景定义进行匹配
            for stage, stage_scenarios in self.micro_scenarios.items():
                for scenario_id, scenario_info in stage_scenarios.items():
                    scenario_name = scenario_info['name']
                    keywords = scenario_info['keywords']
                    
                    # 检查是否有关键词匹配
                    for keyword in keywords:
                        if keyword.lower() in content_lower:
                            scenarios.add(f"{scenario_id}_{scenario_name}")
                            break  # 找到匹配，移动到下一个场景
            
            return scenarios
            
        except Exception as e:
            self.logger.warning(f"❌ 场景识别失败 {url}: {e}")
            return scenarios
    
    def _save_content_to_txt(self, url: str, content_lower: str, year: str, websites_dir: str):
        """保存内容到txt文件"""
        try:
            # 生成时间戳
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 创建文件名
            filename = f"{year}_{timestamp}.txt"
            
            # 完整文件路径
            file_path = os.path.join(websites_dir, filename)
            
            # 写入内容到文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"来源URL: {url}\n")
                f.write("=" * 80 + "\n\n")
                f.write(content_lower)
            
            self.logger.info(f"💾 内容已保存到: {file_path}")
            
        except Exception as e:
            self.logger.warning(f"❌ 保存内容失败 {url}: {e}")
    
    def _categorize_scenarios_by_stage(self, scenarios: Set[str]) -> Dict[str, int]:
        """按阶段分类场景"""
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
    
    def _generate_analysis_summary(self, company_url: str = None) -> str:
        """生成分析摘要"""
        if not self.yearly_scenario_data:
            return ""
        
        total_scenarios = sum(data.get("total_scenario_count", 0) for data in self.yearly_scenario_data.values())
        
        self.analysis_summary = {
            "analysis_version": "Scenario_Analyzer_v1.0",
            "company_url": company_url,
            "generation_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "focus": "Core scenario identification functionality",
            
            "core_statistics": {
                "analyzed_years_count": len(self.yearly_scenario_data),
                "total_identified_scenarios": total_scenarios,
                "average_scenarios_per_year": round(total_scenarios / len(self.yearly_scenario_data), 1) if self.yearly_scenario_data else 0
            },
            
            "yearly_detailed_results": self.yearly_scenario_data
        }
        
        # 动态生成输出文件名
        if company_url:
            output_dir = os.path.join("outputs", company_url)
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{company_url}_scenarios.json")
        else:
            os.makedirs("outputs", exist_ok=True)
            output_file = os.path.join("outputs", "scenario_analysis_summary.json")
        
        # 导出分析摘要
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.analysis_summary, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"✅ 场景分析结果已导出到: {output_file}")
        return output_file
    
    def load_scenarios(self, company_url: str) -> Dict[str, Dict]:
        """加载已保存的场景分析结果"""
        output_dir = os.path.join("outputs", company_url)
        scenarios_file = os.path.join(output_dir, f"{company_url}_scenarios.json")
        
        if not os.path.exists(scenarios_file):
            self.logger.error(f"❌ 场景文件不存在: {scenarios_file}")
            return {}
        
        try:
            with open(scenarios_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            yearly_results = data.get("yearly_detailed_results", {})
            self.logger.info(f"✅ 成功加载 {len(yearly_results)} 年的场景数据")
            return yearly_results
            
        except Exception as e:
            self.logger.error(f"❌ 加载场景文件失败: {e}")
            return {}


def verify_scenario_definitions():
    """验证场景定义完整性"""
    print("🔍 验证微场景定义完整性...")
    
    try:
        base_dir = pathlib.Path(__file__).resolve().parent
        scenarios_file = base_dir / "inputs" / "1_scenario_mapping" / "micro_scenarios_definitions_v0.3.json"
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
        
        # 获取预期计数
        expected_count = scenarios_data.get("total_scenarios", 62)
        if total_count == expected_count:
            print("🎉 场景定义完整!")
            return True
        else:
            print(f"❌ 场景计数不匹配! 应该是 {expected_count}，实际是 {total_count}")
            return False
            
    except Exception as e:
        print(f"❌ 验证场景定义失败: {e}")
        return False


if __name__ == "__main__":
    # 测试代码
    analyzer = ScenarioAnalyzer()
    print("场景分析器初始化完成")
    verify_scenario_definitions() 