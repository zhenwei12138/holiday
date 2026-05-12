"""
主入口：汇总三地节假日数据
用法：python scripts/fetch_all.py --year 2026
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from datetime import datetime

# 确保 scripts 目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import HolidayCalendarDay, save_json, build_calendar_output
from fetch_mainland import fetch_mainland_holidays
from fetch_taiwan import fetch_taiwan_holidays
from fetch_hongkong import fetch_hongkong_holidays


def deduplicate(days: list[HolidayCalendarDay]) -> list[HolidayCalendarDay]:
    """按 (region, date) 去重，保留第一条"""
    seen: set[tuple] = set()
    result = []
    for d in days:
        key = (d.region, d.date)
        if key not in seen:
            seen.add(key)
            result.append(d)
    return result


def run(year: int, output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)

    # 采集三地
    mainland = fetch_mainland_holidays(year)
    taiwan = fetch_taiwan_holidays(year)
    hongkong = fetch_hongkong_holidays(year)

    all_days = deduplicate(mainland + taiwan + hongkong)
    all_days.sort(key=lambda d: (d.date, d.region))

    # 保存单地区文件
    save_json(
        [d.to_dict() for d in mainland],
        os.path.join(output_dir, f'cn-mainland-{year}.json'),
    )
    save_json(
        [d.to_dict() for d in taiwan],
        os.path.join(output_dir, f'cn-taiwan-{year}.json'),
    )
    save_json(
        [d.to_dict() for d in hongkong],
        os.path.join(output_dir, f'cn-hongkong-{year}.json'),
    )

    # 保存合并文件
    merged_output = build_calendar_output(
        all_days,
        year,
        ['CN_MAINLAND', 'CN_TAIWAN', 'CN_HONGKONG'],
    )
    merged_path = os.path.join(output_dir, f'holidays-{year}.json')
    with open(merged_path, 'w', encoding='utf-8') as f:
        json.dump(merged_output, f, ensure_ascii=False, indent=2)
    print(f'\n[✓] 合并文件 → {merged_path}  ({len(all_days)} 条)')

    # 更新 latest.json 软链接
    latest_path = os.path.join(output_dir, 'latest.json')
    with open(latest_path, 'w', encoding='utf-8') as f:
        json.dump(merged_output, f, ensure_ascii=False, indent=2)
    print(f'[✓] latest.json 已更新')

    # 统计报告
    print('\n========== 采集统计 ==========')
    print(f'  中国大陆: {len(mainland):>3} 条')
    print(f'  台    湾: {len(taiwan):>3} 条')
    print(f'  香    港: {len(hongkong):>3} 条')
    print(f'  合    计: {len(all_days):>3} 条（已去重）')
    print('================================\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='采集大中华区法定节假日')
    parser.add_argument('--year', type=int, default=datetime.now().year,
                        help='目标年份（默认当前年）')
    parser.add_argument('--output-dir', type=str,
                        default=os.path.join(os.path.dirname(__file__), '..', 'data'),
                        help='输出目录（默认 ./data）')
    args = parser.parse_args()

    run(args.year, os.path.abspath(args.output_dir))
