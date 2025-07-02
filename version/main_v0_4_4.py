#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main entry point for the Wayback Machine LLM analysis system.
This script orchestrates:
1. Scenario definition verification
2. LLM planning phase (RealLLMPlanningAgentV3)
3. Scenario identification phase (RealScenarioAnalyzerV3)

Usage:
    python main.py [--verify-only] [--input INPUT_FILE]

Flags:
    --verify-only   Only verify scenario definitions and exit.
    --input         Path to the historical URL list (default: ./inputs/apple.com.txt)
"""

import argparse
import logging
import os
from datetime import datetime
from typing import List, Tuple

# Local imports
from real_scenario_analyzer_v0_4_4 import (
    RealScenarioAnalyzerV3,
    extract_company_url_from_filepath,
    verify_scenario_definitions,
)

# ---------------------------
# Helper functions
# ---------------------------

def load_historical_urls_from_file(file_path: str) -> List[Tuple[str, str]]:
    """Load historical URL data from file and extract year from each Wayback URL"""
    historical_urls: List[Tuple[str, str]] = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        import re

        for line in lines:
            line = line.strip()
            if line and line.startswith("https://web.archive.org/"):
                match = re.search(r"/web/(\d{4})\d{10}/", line)
                if match:
                    year = match.group(1)
                    historical_urls.append((year, line))

        logging.info("✅ Successfully read %d historical URLs from %s", len(historical_urls), file_path)
    except FileNotFoundError:
        logging.error("❌ File not found: %s", file_path)
    except Exception as e:
        logging.error("❌ Error reading file %s: %s", file_path, e)

    return historical_urls

# ---------------------------
# Main workflow
# ---------------------------

def main():
    parser = argparse.ArgumentParser(description="Run Wayback Machine LLM analysis workflow")
    parser.add_argument("--verify-only", action="store_true", help="Only verify scenario definitions and exit")
    parser.add_argument("--input", type=str, default="./inputs/apple.com.txt", help="Path to historical URL list")
    args = parser.parse_args()

    # Initial logging setup with console output; file handler will be added after company_url is known
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )
    logging.info("📋 Logging started (console). File logging will initialize after company URL is determined.")

    # Step 0: Verify scenario definitions
    if not verify_scenario_definitions():
        logging.error("Scenario definition verification failed. Exiting.")
        return

    if args.verify_only:
        logging.info("✅ Verification-only mode, exiting.")
        return

    # Step 1: Load historical URLs
    input_file_path = args.input
    historical_urls = load_historical_urls_from_file(input_file_path)
    if not historical_urls:
        logging.error("No historical URLs loaded. Exiting.")
        return

    # Extract company URL for output naming
    company_url = extract_company_url_from_filepath(input_file_path)
    logging.info("📋 Company URL extracted: %s", company_url)

    # Prepare company-specific output directory and logging after company_url is known
    output_dir = os.path.join("./outputs", company_url)
    os.makedirs(output_dir, exist_ok=True)

    # Ensure logs subdirectory exists
    logs_dir = os.path.join(output_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    # Reconfigure logging file handler to company/logs folder
    for handler in logging.root.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            logging.root.removeHandler(handler)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = os.path.join(logs_dir, f"log_v0.4_{timestamp}.txt")
    file_handler = logging.FileHandler(log_filename, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logging.getLogger().addHandler(file_handler)

    # Step 2: Initialize analyzer
    API_KEY = "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"
    analyzer = RealScenarioAnalyzerV3(api_key=API_KEY)

    # Step 3: Run complete analysis
    logging.info("🚀 Starting complete analysis workflow...")
    analyzer.run_complete_analysis(historical_urls, company_url=company_url)

    logging.info("💡 Analysis completed! Output files:")
    logging.info("   - %s", os.path.join(output_dir, f"{company_url}_llm_planning_v0.4_result.json"))
    logging.info("   - %s", os.path.join(output_dir, f"{company_url}_scenario_v0.4_result.json"))

    # Step 4: Visualize scenario results
    try:
        import importlib.util
        import pathlib
        vis_file = pathlib.Path(__file__).resolve().parent / "visualize_results.py"
        spec = importlib.util.spec_from_file_location("visualize_results", str(vis_file))
        vis_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(vis_mod)
        vis_mod.visualize_scenario_results(output_dir, company_url)
    except Exception as e:
        logging.error("❌ Visualization failed: %s", e)


if __name__ == "__main__":
    main() 