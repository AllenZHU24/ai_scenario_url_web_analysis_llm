#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将所有公司的scenarios.json文件整合成面板数据格式的Excel文件
输出文件：tools/outputs/company_scenarios_panel.xlsx
"""

import os
import json
import pandas as pd
from pathlib import Path
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def find_scenarios_files(base_path):
    """
    扫描outputs目录下所有的*_scenarios.json文件
    
    Args:
        base_path (str): outputs目录的路径
        
    Returns:
        list: 包含所有scenarios.json文件路径的列表
    """
    scenarios_files = []
    base_path = Path(base_path)
    
    if not base_path.exists():
        logger.error(f"路径不存在: {base_path}")
        return scenarios_files
    
    # 遍历所有子目录
    for company_dir in base_path.iterdir():
        if company_dir.is_dir():
            # 查找该目录下的scenarios.json文件
            for file in company_dir.iterdir():
                if file.is_file() and file.name.endswith('_scenarios.json'):
                    scenarios_files.append(file)
                    logger.info(f"找到文件: {file}")
    
    return scenarios_files

def parse_scenarios_json(file_path):
    """
    解析单个scenarios.json文件
    
    Args:
        file_path (Path): JSON文件路径
        
    Returns:
        list: 包含面板数据行的列表，每行是一个字典
    """
    panel_data = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        company_url = data.get('company_url', '')
        yearly_results = data.get('yearly_detailed_results', {})
        
        # 遍历每年的数据
        for year, year_data in yearly_results.items():
            # 跳过数据不完整的年份
            if not year_data or 'total_scenario_count' not in year_data:
                logger.warning(f"跳过 {company_url} 年份 {year}，数据不完整")
                continue
            
            # 提取stage_distribution数据
            stage_dist = year_data.get('stage_distribution', {})
            
            # 构建一行面板数据
            row = {
                'url_id': company_url,
                'year': int(year),
                'total_scenario_count': year_data.get('total_scenario_count', 0),
                'awareness_stage': stage_dist.get('Awareness Stage', 0),
                'interest_stage': stage_dist.get('Interest Stage', 0),
                'consideration_stage': stage_dist.get('Consideration Stage', 0),
                'decision_stage': stage_dist.get('Decision Stage', 0),
                'fulfillment_stage': stage_dist.get('Fulfillment Stage', 0),
                'retention_stage': stage_dist.get('Retention Stage', 0),
                'page_success_rate': year_data.get('page_success_rate', '')
            }
            
            panel_data.append(row)
            logger.debug(f"处理 {company_url} 年份 {year}，场景数: {row['total_scenario_count']}")
    
    except Exception as e:
        logger.error(f"解析文件 {file_path} 时出错: {e}")
    
    return panel_data

def create_panel_dataframe(all_panel_data):
    """
    创建面板数据DataFrame
    
    Args:
        all_panel_data (list): 所有面板数据行的列表
        
    Returns:
        pd.DataFrame: 面板数据DataFrame
    """
    if not all_panel_data:
        logger.warning("没有有效的数据")
        return pd.DataFrame()
    
    df = pd.DataFrame(all_panel_data)
    
    # 按公司和年份排序
    df = df.sort_values(['url_id', 'year']).reset_index(drop=True)
    
    # 数据类型优化
    df['year'] = df['year'].astype(int)
    df['total_scenario_count'] = df['total_scenario_count'].astype(int)
    df['awareness_stage'] = df['awareness_stage'].astype(int)
    df['interest_stage'] = df['interest_stage'].astype(int)
    df['consideration_stage'] = df['consideration_stage'].astype(int)
    df['decision_stage'] = df['decision_stage'].astype(int)
    df['fulfillment_stage'] = df['fulfillment_stage'].astype(int)
    df['retention_stage'] = df['retention_stage'].astype(int)
    
    return df

def export_to_excel(df, output_path):
    """
    将DataFrame导出到Excel文件
    
    Args:
        df (pd.DataFrame): 面板数据DataFrame
        output_path (str): 输出文件路径
    """
    try:
        # 确保输出目录存在
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 导出到Excel
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Panel_Data', index=False)
            
            # 获取工作表对象以进行格式化
            worksheet = writer.sheets['Panel_Data']
            
            # 自动调整列宽
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        logger.info(f"成功导出到: {output_path}")
        logger.info(f"总计 {len(df)} 行数据")
        logger.info(f"涵盖 {df['url_id'].nunique()} 家公司")
        logger.info(f"年份范围: {df['year'].min()} - {df['year'].max()}")
        
    except Exception as e:
        logger.error(f"导出Excel文件时出错: {e}")

def main():
    """
    主函数
    """
    logger.info("开始处理scenarios.json文件...")
    
    # 设置路径
    current_dir = Path(__file__).parent
    outputs_dir = current_dir.parent / 'outputs'
    output_file = current_dir / 'outputs' / 'company_scenarios_panel.xlsx'
    
    logger.info(f"扫描目录: {outputs_dir}")
    logger.info(f"输出文件: {output_file}")
    
    # 1. 查找所有scenarios.json文件
    scenarios_files = find_scenarios_files(outputs_dir)
    
    if not scenarios_files:
        logger.warning("未找到任何scenarios.json文件")
        return
    
    logger.info(f"找到 {len(scenarios_files)} 个scenarios.json文件")
    
    # 2. 解析所有JSON文件
    all_panel_data = []
    for file_path in scenarios_files:
        logger.info(f"处理文件: {file_path}")
        panel_data = parse_scenarios_json(file_path)
        all_panel_data.extend(panel_data)
    
    if not all_panel_data:
        logger.warning("没有有效的面板数据")
        return
    
    logger.info(f"总计处理了 {len(all_panel_data)} 行面板数据")
    
    # 3. 创建DataFrame
    df = create_panel_dataframe(all_panel_data)
    
    if df.empty:
        logger.warning("DataFrame为空")
        return
    
    # 4. 导出到Excel
    export_to_excel(df, output_file)
    
    logger.info("处理完成！")

if __name__ == "__main__":
    main()
