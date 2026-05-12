"""
香港节假日采集
数据来源：
  - data.gov.hk / 1823 官方 JSON
    https://www.1823.gov.hk/common/ical/en.json  （英文）
    https://www.1823.gov.hk/common/ical/tc.json  （繁体中文）
  - data.gov.hk 备用 API
    https://data.gov.hk/en-data/dataset/hk-1823-holidays-hk
"""
from __future__ import annotations
import re
import json
import time
import argparse
import requests
from models import HolidayCalendarDay, save_json

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (compatible; HolidayBot/1.0; '
        '+https://github.com/your-repo/holiday-calendar)'
    ),
    'Accept': 'application/json, */*',
}

# 1823 官方 JSON 端点
HK_ICAL_JSON_EN = 'https://www.1823.gov.hk/common/ical/en.json'
HK_ICAL_JSON_TC = 'https://www.1823.gov.hk/common/ical/tc.json'

# data.gov.hk 备用
DATA_GOV_HK_API = (
    'https://data.gov.hk/en/api/3/action/datastore_search'
    '?resource_id=5b3a0d69-13a4-4e27-8c5d-c1d6da0e82e7'
    '&limit=50&filters={{"year":{year}}}'
)

# 中英文节日名称对照
EN_TO_ZH: dict[str, str] = {
    "New Year's Day": '元旦',
    "Lunar New Year's Day": '農曆年初一',
    "The second day of Lunar New Year": '農曆年初二',
    "The third day of Lunar New Year": '農曆年初三',
    "The fourth day of Lunar New Year": '農曆年初四',
    "Ching Ming Festival": '清明節',
    "Good Friday": '耶穌受難節',
    "The day following Good Friday": '耶穌受難節翌日',
    "Holy Saturday": '復活節前夕',
    "Easter Monday": '復活節星期一',
    "Labour Day": '勞動節',
    "The Buddha's Birthday": '佛誕',
    "Tuen Ng Festival": '端午節',
    "Hong Kong Special Administrative Region Establishment Day": '香港特別行政區成立紀念日',
    "The day following the Chinese Mid-Autumn Festival": '中秋節翌日',
    "Chinese Mid-Autumn Festival": '中秋節',
    "National Day": '國慶日',
    "Chung Yeung Festival": '重陽節',
    "Christmas Day": '聖誕節',
    "The first weekday after Christmas Day": '聖誕節後第一個周日',
    "The second weekday after Christmas Day": '聖誕節後第二個周日',
}

# 静态备用数据
FALLBACK_HK: dict[int, list[dict]] = {
    2025: [
        {"date": "2025-01-01", "name": "元旦"},
        {"date": "2025-01-29", "name": "農曆年初一"},
        {"date": "2025-01-30", "name": "農曆年初二"},
        {"date": "2025-01-31", "name": "農曆年初三"},
        {"date": "2025-04-04", "name": "清明節"},
        {"date": "2025-04-18", "name": "耶穌受難節"},
        {"date": "2025-04-19", "name": "耶穌受難節翌日"},
        {"date": "2025-04-20", "name": "復活節前夕"},
        {"date": "2025-04-21", "name": "復活節星期一"},
        {"date": "2025-05-01", "name": "勞動節"},
        {"date": "2025-05-05", "name": "佛誕"},
        {"date": "2025-06-02", "name": "端午節"},
        {"date": "2025-07-01", "name": "香港特別行政區成立紀念日"},
        {"date": "2025-10-01", "name": "國慶日"},
        {"date": "2025-10-07", "name": "中秋節翌日"},
        {"date": "2025-10-02", "name": "重陽節"},  # 以實際公告為准
        {"date": "2025-12-25", "name": "聖誕節"},
        {"date": "2025-12-26", "name": "聖誕節後第一個周日"},
    ],
    2026: [
        {"date": "2026-01-01", "name": "元旦"},
        {"date": "2026-02-17", "name": "農曆年初一"},
        {"date": "2026-02-18", "name": "農曆年初二"},
        {"date": "2026-02-19", "name": "農曆年初三"},
        {"date": "2026-04-05", "name": "清明節"},
        {"date": "2026-04-03", "name": "耶穌受難節"},
        {"date": "2026-04-04", "name": "耶穌受難節翌日"},
        {"date": "2026-04-05", "name": "復活節前夕"},
        {"date": "2026-04-06", "name": "復活節星期一"},
        {"date": "2026-05-01", "name": "勞動節"},
        {"date": "2026-05-24", "name": "佛誕"},
        {"date": "2026-06-20", "name": "端午節"},
        {"date": "2026-07-01", "name": "香港特別行政區成立紀念日"},
        {"date": "2026-10-01", "name": "國慶日"},
        {"date": "2026-09-26", "name": "中秋節翌日"},
        {"date": "2026-10-16", "name": "重陽節"},
        {"date": "2026-12-25", "name": "聖誕節"},
        {"date": "2026-12-26", "name": "聖誕節後第一個周日"},
    ],
}


def fetch_1823_json(url: str) -> dict | None:
    """从 1823.gov.hk 获取 JSON 格式假期数据"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f'[警告] 1823 API 失败 ({url}): {e}')
        return None


def parse_1823_json(data: dict, year: int, lang: str = 'tc') -> list[dict]:
    """
    解析 1823 格式的 JSON
    结构示例（实际 API 返回）:
    {
      "vcalendar": [{
        "vevent": [
          {
            "dtstart": ["20250101", {"value": "DATE"}],
            "summary": "一月一日",
            ...
          },
          ...
        ]
      }]
    }
    注意：dtstart 是列表，summary 是字符串。
    """
    results = []
    try:
        vevents = data.get('vcalendar', [{}])[0].get('vevent', [])
        for ev in vevents:
            # dtstart 是 list，第一个元素是日期字符串
            dtstart_raw = ev.get('dtstart', [''])
            dtstart = dtstart_raw[0] if isinstance(dtstart_raw, list) else dtstart_raw
            # 格式: 20250101 或 20250101T000000Z
            date_raw = str(dtstart)[:8]
            if not re.match(r'^\d{8}$', date_raw):
                continue
            date_str = f'{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:]}'
            if not date_str.startswith(str(year)):
                continue

            # summary 可能是字符串，也可能是列表
            summary_raw_field = ev.get('summary', '')
            if isinstance(summary_raw_field, list):
                summary_raw = summary_raw_field[0] if summary_raw_field else ''
            else:
                summary_raw = str(summary_raw_field)

            # 香港繁中摘要中元旦显示为"一月一日"，需要标准化
            HK_NAME_NORMALIZE = {
                '一月一日': '元旦',
            }
            summary_raw = HK_NAME_NORMALIZE.get(summary_raw, summary_raw)

            # 英文 JSON 直接用对照表翻译，繁中 JSON 直接用
            if lang == 'en':
                name = EN_TO_ZH.get(summary_raw, summary_raw)
            else:
                name = summary_raw

            results.append({'date': date_str, 'name': name})
    except Exception as e:
        print(f'[警告] 解析1823 JSON失败: {e}')
    return results


def fetch_hongkong_holidays(year: int) -> list[HolidayCalendarDay]:
    print(f'\n=== 开始采集香港 {year} 年节假日 ===')

    records: list[dict] = []

    # 优先繁中
    data_tc = fetch_1823_json(HK_ICAL_JSON_TC)
    if data_tc:
        records = parse_1823_json(data_tc, year, lang='tc')

    # 繁中失败则用英文
    if not records:
        time.sleep(1)
        data_en = fetch_1823_json(HK_ICAL_JSON_EN)
        if data_en:
            records = parse_1823_json(data_en, year, lang='en')

    if not records:
        print(f'[回退] 使用内置静态数据（年份: {year}）')
        records = FALLBACK_HK.get(year, [])

    # 去重（清明和复活节可能重叠）
    seen = set()
    days: list[HolidayCalendarDay] = []
    for rec in records:
        key = rec['date']
        if key in seen:
            continue
        seen.add(key)
        days.append(HolidayCalendarDay(
            region='CN_HONGKONG',
            date=rec['date'],
            year=year,
            type='HOLIDAY',
            name=rec['name'],
            isHoliday=True,
            isWorkday=False,
        ))

    # 香港不存在大陆式"调班工作日"概念，MAKEUP_WORKDAY 暂不适用
    print(f'[✓] 香港 {year} 年假日共 {len(days)} 天')
    return days


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--year', type=int, required=True)
    parser.add_argument('--output', type=str, default='')
    args = parser.parse_args()

    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))

    days = fetch_hongkong_holidays(args.year)
    output = args.output or f'../data/cn-hongkong-{args.year}.json'
    save_json([d.to_dict() for d in days], output)
