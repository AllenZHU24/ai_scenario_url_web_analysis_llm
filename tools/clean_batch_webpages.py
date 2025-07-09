#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量删除 outputs 目录下各 <url_id> 子目录中的 websites/（或 website/）文件夹。

用法示例：
    python clean_batch_webpages.py                 # 使用默认路径 <当前脚本>/../outputs
    python clean_batch_webpages.py -o /tmp/outputs # 指定自定义 outputs 目录
    python clean_batch_webpages.py -n              # 仅打印将要删除的目录（dry run）

如果希望脚本更安静，可使用 -q/--quiet 关闭 INFO 级别日志。
"""

import argparse
import logging
import shutil
from pathlib import Path
from typing import List

# --------------------------- 日志配置 --------------------------- #
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# --------------------------- 核心逻辑 --------------------------- #

def find_target_folders(outputs_dir: Path, keywords: List[str]) -> List[Path]:
    """扫描 outputs_dir 下的每个 <url_id> 目录，寻找待删除的目标文件夹。

    Args:
        outputs_dir (Path): outputs 目录路径。
        keywords (List[str]): 目标文件夹名称关键字列表，例如 ["websites", "website"].

    Returns:
        List[Path]: 待删除文件夹的完整路径列表。
    """
    targets: List[Path] = []

    if not outputs_dir.exists():
        logger.error("指定的 outputs 目录不存在: %s", outputs_dir)
        return targets

    for url_dir in outputs_dir.iterdir():
        if not url_dir.is_dir():
            continue  # 跳过文件

        for keyword in keywords:
            candidate = url_dir / keyword
            if candidate.exists() and candidate.is_dir():
                targets.append(candidate)
                logger.debug("发现目标文件夹: %s", candidate)

    return targets


def remove_folders(folders: List[Path], dry_run: bool = False):
    """删除给定的文件夹列表。

    Args:
        folders (List[Path]): 待删除文件夹路径列表。
        dry_run (bool): 如果为 True，则仅打印将要删除的文件夹，不实际删除。
    """
    for folder in folders:
        if dry_run:
            logger.info("[DRY-RUN] 将删除: %s", folder)
            continue

        try:
            shutil.rmtree(folder)
            logger.info("已删除: %s", folder)
        except Exception as e:
            logger.error("删除 %s 失败: %s", folder, e)

# --------------------------- 命令行接口 --------------------------- #

def parse_args():
    parser = argparse.ArgumentParser(
        description="批量删除 outputs/<url_id>/websites* 目录", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-o",
        "--outputs-dir",
        type=str,
        default=str((Path(__file__).parent.parent / "outputs").resolve()),
        help="outputs 目录路径"
    )
    parser.add_argument(
        "-k",
        "--keywords",
        nargs="+",
        default=["websites", "website"],
        help="需要删除的文件夹名称，可一次指定多个"
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="只打印将要删除的目录而不实际删除"
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="安静模式，仅输出 WARNING 及以上日志"
    )
    return parser.parse_args()

# --------------------------- main --------------------------- #

def main():
    args = parse_args()

    if args.quiet:
        logger.setLevel(logging.WARNING)

    outputs_dir = Path(args.outputs_dir).expanduser().resolve()
    logger.info("扫描 outputs 目录: %s", outputs_dir)

    targets = find_target_folders(outputs_dir, args.keywords)

    if not targets:
        logger.info("未找到任何待删除的 websites 文件夹")
        return

    logger.info("共找到 %d 个待删除的文件夹", len(targets))

    remove_folders(targets, dry_run=args.dry_run)

    if args.dry_run:
        logger.info("干跑(dry-run)完成，未实际删除任何文件夹")
    else:
        logger.info("清理完成！")


if __name__ == "__main__":
    main()
