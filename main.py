#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主模块
协调整个Wayback Machine分析流程
"""

import argparse
import logging
import os
from datetime import datetime
from typing import List, Tuple, Set

# 导入重构后的模块
from url_processing import URLProcessor, extract_company_url_from_filepath
from llm_planning import LLMPlanner
from scenario_analyzer import ScenarioAnalyzer, verify_scenario_definitions


def load_historical_urls_from_file(file_path: str) -> List[Tuple[str, str]]:
    """从文件加载历史URL数据并提取年份、并按年份排序"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        import re

        # 收集 (year, url) 列表
        historical_urls_raw: List[Tuple[str, str]] = []

        for line in lines:
            line = line.strip()
            if not line or not line.startswith("https://web.archive.org/"):
                continue
            m = re.search(r"/web/(\d{4})\d{10}/", line)
            if not m:
                continue
            year = m.group(1)
            historical_urls_raw.append((year, line))

        # 按年份升序排序；稳定排序可保持同年内原始顺序
        historical_urls_raw.sort(key=lambda x: x[0])

        # 去重保持顺序
        seen: Set[str] = set()
        historical_urls = []
        for year, url in historical_urls_raw:
            if url in seen:
                continue
            seen.add(url)
            historical_urls.append((year, url))

        logging.info("✅ 成功读取 %d 个历史URLs from %s", len(historical_urls), file_path)
    except FileNotFoundError:
        logging.error("❌ 文件未找到: %s", file_path)
    except Exception as e:
        logging.error("❌ 读取文件错误 %s: %s", file_path, e)

    return historical_urls


def setup_logging(company_url: str):
    """设置日志系统"""
    # 准备输出目录
    output_dir = os.path.join("outputs", company_url)
    logs_dir = os.path.join(output_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    # 配置日志
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = os.path.join(logs_dir, f"log_main_{timestamp}.txt")
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_filename, encoding="utf-8")
        ]
    )
    
    logging.info(f"📋 日志系统已初始化: {log_filename}")


def main():
    """主流程"""
    parser = argparse.ArgumentParser(description="运行Wayback Machine分析流程")
    parser.add_argument("--verify-only", action="store_true", help="仅验证场景定义并退出")
    parser.add_argument("--input", type=str, default="./inputs/apple.com.txt", help="历史URL列表路径")
    parser.add_argument("--api-key", type=str, default="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", help="OpenAI API密钥")
    args = parser.parse_args()

    # 步骤0: 验证场景定义
    if not verify_scenario_definitions():
        print("❌ 场景定义验证失败，退出")
        return

    if args.verify_only:
        print("✅ 仅验证模式，退出")
        return

    # 提取公司URL用于输出命名
    company_url = extract_company_url_from_filepath(args.input)
    
    # 设置日志
    setup_logging(company_url)
    
    logging.info("🚀 开始Wayback Machine分析流程...")
    logging.info(f"📊 公司: {company_url}")
    
    # 步骤1: 加载历史URLs
    historical_urls = load_historical_urls_from_file(args.input)
    if not historical_urls:
        logging.error("❌ 未加载到历史URLs，退出")
        return

    try:
        # 步骤2: URL处理
        logging.info("🌐 开始URL处理...")
        url_processor = URLProcessor()
        links_file = url_processor.process_urls_for_company(historical_urls, company_url)
        year_links_map = url_processor.load_filtered_links(company_url)
        
        if not year_links_map:
            logging.error("❌ URL处理失败，退出")
            return
        
        logging.info(f"✅ URL处理完成，共处理 {len(year_links_map)} 年的数据")
        
        # 步骤3: LLM规划
        logging.info("🧠 开始LLM规划...")
        llm_planner = LLMPlanner(api_key=args.api_key)
        
        # 生成核心页面类型
        core_types_file = llm_planner.generate_core_page_types(year_links_map, company_url)
        logging.info(f"✅ 核心页面类型已生成: {core_types_file}")
        
        # 生成LLM规划
        planning_file = llm_planner.generate_llm_planning(year_links_map, company_url)
        llm_planning_results = llm_planner.load_llm_planning(company_url)
        
        if not llm_planning_results:
            logging.error("❌ LLM规划失败，退出")
            return
        
        logging.info(f"✅ LLM规划完成: {planning_file}")
        
        # 步骤4: 场景分析
        logging.info("🔍 开始场景分析...")
        scenario_analyzer = ScenarioAnalyzer()
        scenarios_file = scenario_analyzer.analyze_scenarios_for_company(llm_planning_results, company_url)
        
        logging.info(f"✅ 场景分析完成: {scenarios_file}")
        
        # # 步骤5: 可视化
        # logging.info("📊 开始生成可视化...")
        # try:
        #     import importlib.util
        #     import pathlib
        #     vis_file = pathlib.Path(__file__).resolve().parent / "visualize_results.py"
        #     spec = importlib.util.spec_from_file_location("visualize_results", str(vis_file))
        #     vis_mod = importlib.util.module_from_spec(spec)
        #     spec.loader.exec_module(vis_mod)
            
        #     output_dir = os.path.join("outputs", company_url)
        #     vis_mod.visualize_scenario_results(output_dir, company_url)
        #     logging.info("✅ 可视化完成")
        # except Exception as e:
        #     logging.error(f"❌ 可视化失败: {e}")
        
        # 最终总结
        logging.info("🎉 分析流程完成!")
        logging.info("📁 输出文件:")
        logging.info(f"   - 过滤链接: {links_file}")
        logging.info(f"   - 核心页面类型: {core_types_file}")
        logging.info(f"   - LLM规划: {planning_file}")
        logging.info(f"   - 场景分析: {scenarios_file}")
        
    except Exception as e:
        logging.error(f"❌ 流程执行失败: {e}")
        raise


if __name__ == "__main__":
    main() 