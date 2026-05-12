"""
共享工具函数与数据结构
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Literal, Optional
import json
import os
from datetime import datetime


Region = Literal['CN_MAINLAND', 'CN_TAIWAN', 'CN_HONGKONG']
HolidayDateType = Literal['HOLIDAY', 'MAKEUP_REST_DAY', 'MAKEUP_WORKDAY']
AdjustType = Literal['REST_FROM_WORK', 'WORK_FOR_REST']


@dataclass
class AdjustInfo:
    type: AdjustType
    relatedDate: str           # YYYY-MM-DD
    relatedType: HolidayDateType
    description: str


@dataclass
class HolidayCalendarDay:
    region: Region
    date: str                  # YYYY-MM-DD
    year: int
    type: HolidayDateType
    name: str
    isHoliday: bool
    isWorkday: bool
    adjust: Optional[AdjustInfo] = None
    remark: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        # 移除 None 字段
        return {k: v for k, v in d.items() if v is not None}


def save_json(data: list[dict], filepath: str) -> None:
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'[✓] 已保存 {len(data)} 条记录 → {filepath}')


def load_json(filepath: str) -> list[dict]:
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_calendar_output(days: list[HolidayCalendarDay], year: int, regions: list[Region]) -> dict:
    return {
        'generatedAt': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'year': year,
        'regions': regions,
        'days': [d.to_dict() for d in days],
    }
