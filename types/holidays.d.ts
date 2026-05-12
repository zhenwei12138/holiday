/**
 * 大中华区法定节假日统一类型定义
 * Greater China Holiday Calendar Type Definitions
 */

/** 地区 */
export type Region = 'CN_MAINLAND' | 'CN_TAIWAN' | 'CN_HONGKONG';

/**
 * 日期类型
 * - HOLIDAY: 法定节假日（当天为假日）
 * - MAKEUP_REST_DAY: 调班休息日（工作日调至假日，用于补其他假）
 * - MAKEUP_WORKDAY: 调班工作日（休息日调为工作日，换取其他日期假期）
 */
export type HolidayDateType =
  | 'HOLIDAY'
  | 'MAKEUP_REST_DAY'
  | 'MAKEUP_WORKDAY';

/**
 * 调班类型
 * - REST_FROM_WORK: 今天休息，来源于某个工作日的补班
 * - WORK_FOR_REST: 今天上班，是为了换取某个假日
 */
export type AdjustType =
  | 'REST_FROM_WORK'
  | 'WORK_FOR_REST';

/** 调班关联信息 */
export interface AdjustInfo {
  /** 调班类型 */
  type: AdjustType;
  /** 关联日期（YYYY-MM-DD） */
  relatedDate: string;
  /** 关联日期的类型 */
  relatedType: HolidayDateType;
  /** 描述说明 */
  description: string;
}

/** 单日节假日记录 */
export interface HolidayCalendarDay {
  /** 地区标识 */
  region: Region;
  /** 日期（YYYY-MM-DD） */
  date: string;
  /** 年份 */
  year: number;
  /** 日期类型 */
  type: HolidayDateType;
  /** 假日名称（如：元旦、春节、清明节…） */
  name: string;
  /** 是否为假日（放假） */
  isHoliday: boolean;
  /** 是否为工作日（上班，含调班工作日） */
  isWorkday: boolean;
  /** 调班信息（仅 MAKEUP_REST_DAY / MAKEUP_WORKDAY 有值） */
  adjust?: AdjustInfo;
  /** 备注 */
  remark?: string;
}

/** 单年度节假日数据集合 */
export interface HolidayCalendar {
  /** 数据版本（ISO 8601 生成时间） */
  generatedAt: string;
  /** 覆盖年份 */
  year: number;
  /** 包含地区 */
  regions: Region[];
  /** 节假日列表 */
  days: HolidayCalendarDay[];
}
