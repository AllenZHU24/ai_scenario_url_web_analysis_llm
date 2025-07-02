#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Visualization of scenario analysis results.
Generates line and bar charts showing total scenarios per year and distribution per stage.
Requires pandas and matplotlib.
"""

import json
import os
import pandas as pd
import matplotlib.pyplot as plt

def visualize_scenario_results(output_dir, company_url):
    """
    Reads scenario analysis JSON and generates visualization:
    1. Line chart of total scenarios per year.
    2. Bar chart of scenario distribution per stage per year.
    Saves figure to outputs directory.
    """
    json_path = os.path.join(output_dir, f"{company_url}_scenario_v0.4.4_result.json")
    if not os.path.exists(json_path):
        print(f"Result JSON file not found: {json_path}")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    yearly_results = data.get("yearly_detailed_results", {})
    if not yearly_results:
        print("No yearly results found in JSON.")
        return

    # Sort years
    years = sorted(yearly_results.keys())

    # Total scenarios per year
    totals = [yearly_results[year]["total_scenario_count"] for year in years]

    # Build DataFrame for total scenarios
    df_total = pd.DataFrame({
        "Year": years,
        "Total Scenarios": totals
    })

    # Stage distribution DataFrame
    first_year = years[0]
    stage_names = list(yearly_results[first_year]["stage_distribution"].keys())
    stage_data = {
        stage: [yearly_results[year]["stage_distribution"].get(stage, 0) for year in years]
        for stage in stage_names
    }
    df_stages = pd.DataFrame(stage_data, index=years)

    # Plotting
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

    # Line Chart: Total scenarios per year
    ax1.plot(df_total["Year"], df_total["Total Scenarios"], marker='o', linestyle='-')
    ax1.set_title("Total Scenarios Identified per Year")
    ax1.set_xlabel("Year")
    ax1.set_ylabel("Total Scenarios")
    ax1.grid(True)

    # Bar Chart: Stage distribution per year
    df_stages.plot(kind='bar', stacked=True, ax=ax2)
    ax2.set_title("Scenario Distribution per Stage per Year")
    ax2.set_xlabel("Year")
    ax2.set_ylabel("Scenario Count")
    ax2.legend(title="Stage", bbox_to_anchor=(1.05, 1), loc='upper left')

    plt.tight_layout()
    output_file = os.path.join(output_dir, f"{company_url}_scenario_visualization.png")
    plt.savefig(output_file)
    print(f"Visualization saved to: {output_file}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Visualize scenario analysis results")
    parser.add_argument("--output-dir", type=str, default="./outputs", help="Directory containing JSON result file")
    parser.add_argument("--company-url", type=str, required=True, help="Company URL identifier")
    args = parser.parse_args()
    visualize_scenario_results(args.output_dir, args.company_url) 