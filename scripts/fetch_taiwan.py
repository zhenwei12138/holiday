"""
台湾节假日采集
数据来源：
  - 中华民国人事行政总处（DGPA）/ data.gov.tw dataset 14718
    政府行政機關辦公日曆表 CSV
    https://data.gov.tw/dataset/14718
  - CSV 直链由 data.gov.tw 数据集页面动态解析获得
    格式：西元日期, 星期, 是否放假(0=上班/1=補班/2=放假), 備註

民国年对照：
  2025 年 = 民国 114 年
  2026 年 = 民国 115 年
"""
from __future__ import annotations
import re
import csv
import io
import time
import argparse
import requests
from bs4 import BeautifulSoup
from models import HolidayCalendarDay, AdjustInfo, save_json

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; HolidayBot/1.0)',
    'Accept': 'application/json, text/csv, */*',
}

# data.gov.tw 数据集页面（从此动态解析 CSV 下载链接）
DATA_GOV_TW_PAGE = 'https://data.gov.tw/dataset/14718'

# 已知 CSV 直链（从 data.gov.tw 页面解析，需定期更新）
# 格式：民国年编号 → CSV 下载 URL
# 民国年 = 西元年 - 1911
KNOWN_CSV_URLS: dict[int, str] = {
    # 113 年 (2024)
    113: 'https://www.dgpa.gov.tw/FileConversion?filename=dgpa/files/202407/777152e9-fdd1-4a61-876c-2733e7692538.csv',
    # 114 年 (2025)
    114: 'https://www.dgpa.gov.tw/FileConversion?filename=dgpa/files/202407/22f9fcbc-fbb2-4387-8bcf-73b2279666c2.csv',
    # 115 年 (2026)
    115: 'https://www.dgpa.gov.tw/FileConversion?filename=dgpa/files/202506/a52331bd-a189-466b-b0f0-cae3062bbf74.csv',
}

# 静态备用数据（采集失败时回退）
FALLBACK_TW: dict[int, list[dict]] = {
    2025: [
        {"date": "2025-01-01", "name": "開國紀念日", "isHoliday": True},
        {"date": "2025-01-27", "name": "農曆除夕", "isHoliday": True},
        {"date": "2025-01-28", "name": "春節", "isHoliday": True},
        {"date": "2025-01-29", "name": "春節", "isHoliday": True},
        {"date": "2025-01-30", "name": "春節", "isHoliday": True},
        {"date": "2025-01-31", "name": "春節補假", "isHoliday": True},
        {"date": "2025-02-28", "name": "和平紀念日", "isHoliday": True},
        {"date": "2025-04-04", "name": "兒童節", "isHoliday": True},
        {"date": "2025-04-05", "name": "清明節", "isHoliday": True},
        {"date": "2025-05-01", "name": "勞動節", "isHoliday": True},
        {"date": "2025-05-31", "name": "端午節", "isHoliday": True},
        {"date": "2025-10-06", "name": "中秋節", "isHoliday": True},
        {"date": "2025-10-10", "name": "國慶日", "isHoliday": True},
    ],
    2026: [
        {"date": "2026-01-01", "name": "開國紀念日", "isHoliday": True},
        {"date": "2026-02-14", "name": "農曆除夕", "isHoliday": True},
        {"date": "2026-02-15", "name": "春節", "isHoliday": True},
        {"date": "2026-02-16", "name": "春節", "isHoliday": True},
        {"date": "2026-02-17", "name": "春節", "isHoliday": True},
        {"date": "2026-02-18", "name": "春節補假", "isHoliday": True},
        {"date": "2026-02-28", "name": "和平紀念日", "isHoliday": True},
        {"date": "2026-04-03", "name": "兒童節", "isHoliday": True},
        {"date": "2026-04-05", "name": "清明節", "isHoliday": True},
        {"date": "2026-05-01", "name": "勞動節", "isHoliday": True},
        {"date": "2026-06-19", "name": "端午節", "isHoliday": True},
        {"date": "2026-09-25", "name": "中秋節", "isHoliday": True},
        {"date": "2026-10-10", "name": "國慶日", "isHoliday": True},
    ],
}


def discover_csv_url(year: int) -> str | None:
    """
    动态从 data.gov.tw 数据集页面解析目标年份的 CSV 下载链接。
    民国年 = year - 1911，CSV 文件名含有民国年数字。
    """
    roc_year = year - 1911
    try:
        resp = requests.get(DATA_GOV_TW_PAGE, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'lxml')
        for a in soup.find_all('a', href=True):
            href = a['href']
            name_text = a.get_text('', strip=True)
            # 匹配含有民国年的 CSV 链接，排除 Google 版本
            if (str(roc_year) in name_text or str(roc_year) in href) \
               and 'csv' in href.lower() \
               and 'Google' not in name_text \
               and 'google' not in href.lower():
                print(f'[data.gov.tw 动态发现] {href[:100]}')
                return href
    except Exception as e:
        print(f'[警告] 动态发现 CSV 链接失败: {e}')
    return None


def fetch_dgpa_csv(year: int) -> list[dict] | None:
    """下载并解析人事行政总处 CSV 数据"""
    roc_year = year - 1911

    # 优先使用已知直链
    url = KNOWN_CSV_URLS.get(roc_year)
    if not url:
        print(f'[data.gov.tw] 尝试动态发现 {year}（民国{roc_year}年）CSV 链接...')
        url = discover_csv_url(year)

    if not url:
        print(f'[警告] 找不到 {year} 年 CSV 链接')
        return None

    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        # UTF-8 with BOM
        content = resp.content.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(content))

        records = []
        for row in reader:
            # 列名：西元日期, 星期, 是否放假, 備註
            date_raw = row.get('西元日期', '').strip()
            is_holiday_code = row.get('是否放假', '0').strip()
            remark = row.get('備註', '').strip()

            if not date_raw or not re.match(r'^\d{8}$', date_raw):
                continue

            date_str = f'{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:]}'
            if not date_str.startswith(str(year)):
                continue

            records.append({
                'date': date_str,
                'isHolidayCode': is_holiday_code,  # 0=上班, 1=補班, 2=放假
                'name': remark,
            })

        if records:
            print(f'[DGPA CSV] 获取 {len(records)} 条（{year}年全年）')
        return records
    except Exception as e:
        print(f'[警告] DGPA CSV 下载/解析失败: {e}')
        return None


def build_tw_days_from_dgpa(records: list[dict], year: int) -> list[HolidayCalendarDay]:
    """
    从人事行政总处完整日历构建节假日列表。
    is_holiday_code:
      0 = 正常上班
      1 = 補班日（调班工作日）
      2 = 放假（含法定节假日、补假、弹性放假、周末）
    只保留有实际 remark 的假日（即有意义的法定节假日或调班），
    跳过普通周末（code=2 但 remark 为空）。
    """
    days = []
    seen = set()

    for rec in records:
        date_str = rec['date']
        code = rec['isHolidayCode']
        name = rec['name']

        if date_str in seen:
            continue

        if code == '2' and name:
            # 有名称的放假日 → 法定节假日或补假
            dtype: str
            adj = None
            if '補假' in name or '彈性放假' in name:
                dtype = 'MAKEUP_REST_DAY'
                adj = AdjustInfo(
                    type='REST_FROM_WORK',
                    relatedDate='',
                    relatedType='MAKEUP_WORKDAY',
                    description=name,
                )
            else:
                dtype = 'HOLIDAY'

            seen.add(date_str)
            days.append(HolidayCalendarDay(
                region='CN_TAIWAN',
                date=date_str,
                year=year,
                type=dtype,
                name=name,
                isHoliday=True,
                isWorkday=False,
                adjust=adj,
            ))

        elif code == '1':
            # 補班日 → 调班工作日
            seen.add(date_str)
            days.append(HolidayCalendarDay(
                region='CN_TAIWAN',
                date=date_str,
                year=year,
                type='MAKEUP_WORKDAY',
                name=name if name else '補班日',
                isHoliday=False,
                isWorkday=True,
                adjust=AdjustInfo(
                    type='WORK_FOR_REST',
                    relatedDate='',
                    relatedType='HOLIDAY',
                    description=name if name else '補班',
                ),
            ))

    return days


def fetch_taiwan_holidays(year: int) -> list[HolidayCalendarDay]:
    print(f'\n=== 开始采集台湾 {year} 年节假日 ===')

    records = fetch_dgpa_csv(year)
    if records:
        days = build_tw_days_from_dgpa(records, year)
        if days:
            print(f'[✓] 解析成功，共 {len(days)} 条（仅含法定假日与补班日）')
            return days

    print(f'[回退] 使用内置静态数据（年份: {year}）')
    fallback = FALLBACK_TW.get(year, [])
    result = []
    for item in fallback:
        result.append(HolidayCalendarDay(
            region='CN_TAIWAN',
            date=item['date'],
            year=year,
            type='HOLIDAY',
            name=item['name'],
            isHoliday=True,
            isWorkday=False,
        ))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--year', type=int, required=True)
    parser.add_argument('--output', type=str, default='')
    args = parser.parse_args()

    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))

    days = fetch_taiwan_holidays(args.year)
    output = args.output or f'../data/cn-taiwan-{args.year}.json'
    save_json([d.to_dict() for d in days], output)
