# 大中华区法定节假日数据库

自动采集并整理大陆、台湾、香港三地官方法定节假日数据，每年自动更新，输出统一格式的 JSON 数据。

## 数据来源

| 地区 | 来源 | 说明 |
|------|------|------|
| 🇨🇳 中国大陆 | 中国政府网 / 国务院政策文件库 | 国务院办公厅关于部分节假日安排的通知 |
| 🇹🇼 台湾 | data.gov.tw / 新北市开放资料 | 政府行政機關辦公日曆表 |
| 🇭🇰 香港 | data.gov.hk / 1823 | Hong Kong Public Holidays Data |

## 数据结构

```typescript
type HolidayDateType =
  | 'HOLIDAY'           // 法定节假日
  | 'MAKEUP_REST_DAY'   // 调班休息日
  | 'MAKEUP_WORKDAY';   // 调班工作日

type AdjustType =
  | 'REST_FROM_WORK'    // 这天休息，来源于某天补班
  | 'WORK_FOR_REST';    // 这天上班，是为了换某天休息

interface HolidayCalendarDay {
  region: 'CN_MAINLAND' | 'CN_TAIWAN' | 'CN_HONGKONG';
  date: string;         // YYYY-MM-DD
  year: number;

  type: HolidayDateType;
  name: string;

  isHoliday: boolean;
  isWorkday: boolean;

  adjust?: {
    type: AdjustType;
    relatedDate: string;
    relatedType: HolidayDateType;
    description: string;
  };

  remark?: string;
}
```

## 输出文件

```
data/
  holidays-{YEAR}.json      # 当年全部三地节假日
  cn-mainland-{YEAR}.json   # 中国大陆
  cn-taiwan-{YEAR}.json     # 台湾
  cn-hongkong-{YEAR}.json   # 香港
  latest.json               # 最新一年完整数据（同 holidays-{YEAR}.json）
```

## 自动更新策略

### 高频探测模式（解决国务院通知发布时间不确定的问题）

国务院发布次年节假日通知的时间**不固定**（历史上在 10 月下旬 ~ 12 月初之间），因此采用**高频探测 + 智能更新**策略：

| 阶段 | 时间 | 频率 | 说明 |
|------|------|------|------|
| 🔍 **探测期** | 11月1日 ~ 12月15日 | **每3天一次** | 持续搜索国务院是否已发布通知，首次抓到官方正文即替换回退数据 |
| ✅ **最终确认** | 12月15日 | 1次 | 确保次年数据在元旦假期前到位 |
| 🎯 **手动** | 任意时间 | 按需 | `workflow_dispatch` 可指定年份、地区、强制提交 |

### 数据来源降级链路

```
中国大陆:
  ① KNOWN_NOTICE_URLS 直连 → ② 政府网搜索 → ③ 内置静态回退数据
台湾:    ① DGPA CSV 直连 → ② 动态发现 data.gov.tw CSV → ③ 内置静态
香港:    ① 1823.gov.hk JSON API → ② 英文 JSON 备用 → ③ 内置静态
```

每次运行都会自动判断数据来源质量：
- ✅ 大陆数据含 `adjust` 调班信息 = 来自官方正文解析
- ⚠️ 无 adjust 字段 = 当前为回退数据，后续定时任务会持续探测

## 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 运行全部采集
python scripts/fetch_all.py --year 2026

# 仅运行某一地区
python scripts/fetch_mainland.py --year 2026
python scripts/fetch_taiwan.py --year 2026
python scripts/fetch_hongkong.py --year 2026
```

## License

MIT
