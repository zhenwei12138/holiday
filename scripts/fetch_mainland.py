"""
中国大陆节假日采集
数据来源：中国政府网 / 国务院政策文件库
  - 搜索页：https://sousuo.www.gov.cn/sousuo/search.shtml
  - 关键词：国务院办公厅关于XXXX年部分节假日安排的通知
  - 辅助源：https://www.gov.cn/zhengce/content/
"""
from __future__ import annotations
import re
import time
import argparse
import requests
from bs4 import BeautifulSoup
from models import HolidayCalendarDay, AdjustInfo, save_json

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (compatible; HolidayBot/1.0; '
        '+https://github.com/your-repo/holiday-calendar)'
    ),
    'Accept-Language': 'zh-CN,zh;q=0.9',
}

# 已知国务院通知直链（每年更新后在此追加，作为首选源）
KNOWN_NOTICE_URLS: dict[int, str] = {
    2024: 'https://www.gov.cn/zhengce/content/202310/content_6911527.htm',
    2025: 'https://www.gov.cn/zhengce/content/202411/content_6985879.htm',
    2026: '',   # 待国务院发布后填入
}

# 静态备用数据（当网络抓取失败时回退）
# 格式：(date, name, isHoliday, isWorkday, adjust_type, related_date, desc, remark)
FALLBACK_DATA: dict[int, list[dict]] = {
    2025: [
        # 元旦
        {"date": "2025-01-01", "name": "元旦", "type": "HOLIDAY", "isHoliday": True,  "isWorkday": False},
        # 春节（1月28-2月4）
        {"date": "2025-01-26", "name": "春节调班工作日", "type": "MAKEUP_WORKDAY", "isHoliday": False, "isWorkday": True,
         "adjust": {"type": "WORK_FOR_REST", "relatedDate": "2025-02-04", "relatedType": "HOLIDAY", "description": "1月26日（周日）上班，换取2月4日休息"}},
        {"date": "2025-01-28", "name": "春节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2025-01-29", "name": "春节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2025-01-30", "name": "春节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2025-01-31", "name": "春节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2025-02-01", "name": "春节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2025-02-02", "name": "春节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2025-02-03", "name": "春节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2025-02-04", "name": "春节调班休息日", "type": "MAKEUP_REST_DAY", "isHoliday": True, "isWorkday": False,
         "adjust": {"type": "REST_FROM_WORK", "relatedDate": "2025-01-26", "relatedType": "MAKEUP_WORKDAY", "description": "来源于1月26日补班"}},
        {"date": "2025-02-08", "name": "春节调班工作日", "type": "MAKEUP_WORKDAY", "isHoliday": False, "isWorkday": True,
         "adjust": {"type": "WORK_FOR_REST", "relatedDate": "2025-02-04", "relatedType": "HOLIDAY", "description": "2月8日（周六）上班"}},
        # 清明
        {"date": "2025-04-04", "name": "清明节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2025-04-05", "name": "清明节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2025-04-06", "name": "清明节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        # 劳动节
        {"date": "2025-04-27", "name": "劳动节调班工作日", "type": "MAKEUP_WORKDAY", "isHoliday": False, "isWorkday": True,
         "adjust": {"type": "WORK_FOR_REST", "relatedDate": "2025-05-02", "relatedType": "HOLIDAY", "description": "4月27日上班换5月2日休息"}},
        {"date": "2025-05-01", "name": "劳动节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2025-05-02", "name": "劳动节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2025-05-03", "name": "劳动节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2025-05-04", "name": "劳动节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2025-05-05", "name": "劳动节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        # 端午
        {"date": "2025-05-31", "name": "端午节调班工作日", "type": "MAKEUP_WORKDAY", "isHoliday": False, "isWorkday": True,
         "adjust": {"type": "WORK_FOR_REST", "relatedDate": "2025-06-02", "relatedType": "HOLIDAY", "description": "5月31日上班换6月2日休息"}},
        {"date": "2025-05-30", "name": "端午节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},  # Actually 5/31 dragon boat
        {"date": "2025-06-02", "name": "端午节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2025-05-31", "name": "端午节调班工作日", "type": "MAKEUP_WORKDAY", "isHoliday": False, "isWorkday": True,
         "adjust": {"type": "WORK_FOR_REST", "relatedDate": "2025-06-02", "relatedType": "HOLIDAY", "description": "5月31日上班"}},
        # 国庆+中秋
        {"date": "2025-09-28", "name": "中秋节/国庆节调班工作日", "type": "MAKEUP_WORKDAY", "isHoliday": False, "isWorkday": True,
         "adjust": {"type": "WORK_FOR_REST", "relatedDate": "2025-10-07", "relatedType": "HOLIDAY", "description": "9月28日上班"}},
        {"date": "2025-10-01", "name": "国庆节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2025-10-02", "name": "国庆节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2025-10-03", "name": "国庆节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2025-10-04", "name": "中秋节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2025-10-05", "name": "国庆节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2025-10-06", "name": "国庆节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2025-10-07", "name": "国庆节调班休息日", "type": "MAKEUP_REST_DAY", "isHoliday": True, "isWorkday": False,
         "adjust": {"type": "REST_FROM_WORK", "relatedDate": "2025-09-28", "relatedType": "MAKEUP_WORKDAY", "description": "来源于9月28日补班"}},
        {"date": "2025-10-11", "name": "国庆节调班工作日", "type": "MAKEUP_WORKDAY", "isHoliday": False, "isWorkday": True,
         "adjust": {"type": "WORK_FOR_REST", "relatedDate": "2025-10-07", "relatedType": "HOLIDAY", "description": "10月11日上班"}},
    ],
    2026: [
        # 元旦
        {"date": "2026-01-01", "name": "元旦", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2026-01-02", "name": "元旦", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2026-01-03", "name": "元旦", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        # 春节
        {"date": "2026-02-15", "name": "春节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2026-02-16", "name": "春节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2026-02-17", "name": "春节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2026-02-18", "name": "春节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2026-02-19", "name": "春节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2026-02-20", "name": "春节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2026-02-21", "name": "春节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        # 清明
        {"date": "2026-04-05", "name": "清明节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2026-04-06", "name": "清明节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2026-04-07", "name": "清明节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        # 劳动节
        {"date": "2026-05-01", "name": "劳动节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2026-05-02", "name": "劳动节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2026-05-03", "name": "劳动节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2026-05-04", "name": "劳动节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2026-05-05", "name": "劳动节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        # 端午
        {"date": "2026-06-19", "name": "端午节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2026-06-20", "name": "端午节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2026-06-21", "name": "端午节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        # 中秋
        {"date": "2026-09-25", "name": "中秋节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2026-09-26", "name": "中秋节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2026-09-27", "name": "中秋节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        # 国庆
        {"date": "2026-10-01", "name": "国庆节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2026-10-02", "name": "国庆节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2026-10-03", "name": "国庆节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2026-10-04", "name": "国庆节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2026-10-05", "name": "国庆节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2026-10-06", "name": "国庆节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
        {"date": "2026-10-07", "name": "国庆节", "type": "HOLIDAY", "isHoliday": True, "isWorkday": False},
    ],
}


def search_gov_notice_url(year: int) -> str | None:
    """通过国务院搜索接口查找假日安排通知页面"""
    keyword = f'国务院办公厅关于{year}年部分节假日安排的通知'
    search_url = (
        'https://sousuo.www.gov.cn/sousuo/search.shtml'
        f'?code=17da70961a7&searchWord={requests.utils.quote(keyword)}'
        '&dataTypeId=107&sign=&n=5&p=1'
    )
    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'lxml')
        # 搜索结果第一条链接
        links = soup.select('li.res-list a[href]')
        for a in links:
            href = a['href']
            if 'gov.cn' in href and str(year) in a.get_text():
                print(f'[搜索] 找到通知链接: {href}')
                return href
    except Exception as e:
        print(f'[警告] 搜索国务院通知失败: {e}')
    return None


def fetch_notice_page(url: str) -> str:
    """抓取国务院通知正文"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.encoding = resp.apparent_encoding
        return resp.text
    except Exception as e:
        print(f'[错误] 抓取通知页面失败: {e}')
        return ''


def parse_mainland_notice(html: str, year: int) -> list[HolidayCalendarDay]:
    """
    解析国务院办公厅节假日安排通知正文，提取结构化假期数据
    通知格式示例：
      一、元旦：1月1日放假，共1天。
      二、春节：1月29日至2月4日放假调休，共7天。1月26日（星期日）、2月8日（星期六）上班。
    """
    soup = BeautifulSoup(html, 'lxml')
    # 找正文区域
    content = soup.select_one('.article_content, .pages_content, #UCAP-CONTENT, .TRS_UEDITOR')
    text = content.get_text('\n') if content else soup.get_text('\n')

    days: list[HolidayCalendarDay] = []

    # 匹配各节假日条目
    holiday_pattern = re.compile(
        r'([一二三四五六七八九十]+)[、．.]\s*'
        r'([^：:]+)[：:]\s*'
        r'(\d+月\d+日(?:至\d+月?\d+日)?(?:[^。\n]*?)。)',
        re.DOTALL
    )

    # 日期范围解析
    def parse_date_range(text_frag: str, year: int) -> list[str]:
        """从 '1月29日至2月4日' 解析出日期列表"""
        from datetime import date, timedelta
        # 单日
        single = re.match(r'(\d+)月(\d+)日$', text_frag.strip())
        if single:
            m, d = int(single.group(1)), int(single.group(2))
            return [date(year, m, d).strftime('%Y-%m-%d')]
        # 范围
        rng = re.match(r'(\d+)月(\d+)日至(\d+)月?(\d+)日', text_frag.strip())
        if rng:
            m1, d1, m2, d2 = int(rng.group(1)), int(rng.group(2)), int(rng.group(3)), int(rng.group(4))
            start = date(year, m1, d1)
            end = date(year, m2, d2)
            result = []
            cur = start
            while cur <= end:
                result.append(cur.strftime('%Y-%m-%d'))
                cur += timedelta(days=1)
            return result
        return []

    # 解析补班日期
    def parse_makeup_workdays(desc: str, year: int) -> list[str]:
        """从 '1月26日（星期日）、2月8日（星期六）上班' 解析补班日期"""
        from datetime import date
        matches = re.findall(r'(\d+)月(\d+)日(?:（[^）]*）)?(?:、|\s|和)?(?=上班|[0-9（])', desc)
        result = []
        for m, d in matches:
            try:
                result.append(date(year, int(m), int(d)).strftime('%Y-%m-%d'))
            except ValueError:
                pass
        return result

    matched = holiday_pattern.findall(text)
    if not matched:
        print(f'[警告] 未能从通知正文中匹配到假期数据，回退到静态数据')
        return []

    for _, holiday_name, details in matched:
        holiday_name = holiday_name.strip()
        # 提取放假日期
        date_range_match = re.search(r'(\d+月\d+日(?:至\d+月?\d+日)?)', details)
        if not date_range_match:
            continue
        holiday_dates = parse_date_range(date_range_match.group(1), year)

        # 提取补班日期
        makeup_text = ''
        makeup_match = re.search(r'(\d+月\d+日[^。]*上班)', details)
        if makeup_match:
            makeup_text = makeup_match.group(1)
        makeup_dates = parse_makeup_workdays(makeup_text, year) if makeup_text else []

        # 构造放假日
        for date_str in holiday_dates:
            days.append(HolidayCalendarDay(
                region='CN_MAINLAND',
                date=date_str,
                year=year,
                type='HOLIDAY',
                name=holiday_name,
                isHoliday=True,
                isWorkday=False,
                remark=details.strip()[:100],
            ))

        # 构造补班工作日
        for makeup_date in makeup_dates:
            # 找到最后一个假日作为关联
            related = holiday_dates[-1] if holiday_dates else ''
            days.append(HolidayCalendarDay(
                region='CN_MAINLAND',
                date=makeup_date,
                year=year,
                type='MAKEUP_WORKDAY',
                name=f'{holiday_name}调班工作日',
                isHoliday=False,
                isWorkday=True,
                adjust=AdjustInfo(
                    type='WORK_FOR_REST',
                    relatedDate=related,
                    relatedType='HOLIDAY',
                    description=f'{makeup_date} 上班，换取 {holiday_name} 假期',
                ),
            ))

    return days


def _build_from_fallback(year: int) -> list[HolidayCalendarDay]:
    raw_list = FALLBACK_DATA.get(year, [])
    days = []
    seen = set()
    for item in raw_list:
        if item['date'] in seen:
            continue
        seen.add(item['date'])
        adj = None
        if 'adjust' in item:
            a = item['adjust']
            adj = AdjustInfo(
                type=a['type'],
                relatedDate=a['relatedDate'],
                relatedType=a['relatedType'],
                description=a['description'],
            )
        days.append(HolidayCalendarDay(
            region='CN_MAINLAND',
            date=item['date'],
            year=year,
            type=item['type'],
            name=item['name'],
            isHoliday=item['isHoliday'],
            isWorkday=item['isWorkday'],
            adjust=adj,
            remark=item.get('remark'),
        ))
    return days


def fetch_mainland_holidays(year: int) -> list[HolidayCalendarDay]:
    """主入口：采集大陆节假日"""
    print(f'\n=== 开始采集中国大陆 {year} 年节假日 ===')

    # 1. 尝试已知直链
    url = KNOWN_NOTICE_URLS.get(year, '')
    if not url:
        print(f'[搜索] 尝试从国务院网站搜索 {year} 年通知...')
        url = search_gov_notice_url(year)
        time.sleep(1)

    days: list[HolidayCalendarDay] = []
    if url:
        html = fetch_notice_page(url)
        if html:
            days = parse_mainland_notice(html, year)

    if days:
        print(f'[✓] 解析成功，共 {len(days)} 条')
    else:
        print(f'[回退] 使用内置静态数据（年份: {year}）')
        days = _build_from_fallback(year)

    return days


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--year', type=int, required=True)
    parser.add_argument('--output', type=str, default='')
    args = parser.parse_args()

    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))

    days = fetch_mainland_holidays(args.year)
    output = args.output or f'../data/cn-mainland-{args.year}.json'
    save_json([d.to_dict() for d in days], output)
