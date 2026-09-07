from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from app.schemas.bill import TransactionType
from app.services.settings_store import settings_store


@dataclass(frozen=True)
class BillCategoryMatch:
    category: str
    confidence: float
    source: str
    matched_keywords: tuple[str, ...] = ()


class BillCategoryClassifier:
    _default_category = "其他"
    _explicit_category_patterns = (
        re.compile(r"(?:分类|类别)\s*(?:是|为|成|：|:)?\s*([^，,。；;\n]{1,40})"),
        re.compile(r"(?:归类|记到|记为|算作|算到)\s*(?:是|为|成|到|：|:)?\s*([^，,。；;\n]{1,40})"),
    )
    _aliases = {
        "餐饮美食": "餐饮",
        "吃饭": "餐饮",
        "美食": "餐饮",
        "出行": "交通",
        "通勤": "交通",
        "买东西": "购物",
        "日用品": "日用",
        "生活用品": "日用",
        "医药": "医疗",
        "看病": "医疗",
        "教育": "学习",
        "书籍": "学习",
        "居住": "住房",
        "住宅": "住房",
        "房屋": "住房",
        "房租": "住房",
        "薪资": "工资",
        "工资收入": "工资",
        "薪水": "工资",
    }
    _fallbacks = {
        "通讯": ("日用", "其他"),
        "旅行": ("交通", "娱乐", "其他"),
        "人情": ("日用", "其他"),
        "订阅": ("娱乐", "其他"),
        "退款": ("其他",),
        "转账": ("其他",),
    }
    _category_rules: tuple[tuple[str, tuple[str, ...]], ...] = (
        (
            "医疗",
            (
                "买药",
                "药店",
                "医院",
                "门诊",
                "挂号",
                "医保",
                "体检",
                "复诊",
                "诊所",
                "牙科",
                "牙医",
                "眼科",
                "疫苗",
                "处方",
                "药",
            ),
        ),
        (
            "住房",
            (
                "房租",
                "租金",
                "房贷",
                "物业",
                "水电",
                "水费",
                "电费",
                "燃气",
                "天然气",
                "宽带",
                "网费",
                "保洁",
                "家政",
                "维修",
                "搬家",
                "公寓",
            ),
        ),
        (
            "交通",
            (
                "打车",
                "出租车",
                "网约车",
                "滴滴",
                "地铁",
                "公交",
                "巴士",
                "高铁",
                "火车",
                "火车票",
                "机票",
                "航班",
                "停车",
                "停车费",
                "过路费",
                "高速费",
                "加油",
                "油费",
                "充电桩",
                "共享单车",
                "单车",
                "骑行",
            ),
        ),
        (
            "餐饮",
            (
                "早餐",
                "午餐",
                "晚餐",
                "夜宵",
                "外卖",
                "咖啡",
                "奶茶",
                "饮料",
                "餐厅",
                "饭店",
                "食堂",
                "小吃",
                "烧烤",
                "火锅",
                "面包",
                "蛋糕",
                "甜品",
                "瑞幸",
                "星巴克",
                "麦当劳",
                "肯德基",
                "必胜客",
                "喜茶",
                "奈雪",
                "蜜雪冰城",
                "饿了么",
                "美团外卖",
                "餐",
            ),
        ),
        (
            "日用",
            (
                "超市",
                "便利店",
                "便利蜂",
                "全家",
                "罗森",
                "711",
                "7-11",
                "盒马",
                "沃尔玛",
                "山姆",
                "永辉",
                "买菜",
                "菜市场",
                "水果",
                "蔬菜",
                "纸巾",
                "洗发水",
                "牙膏",
                "洗衣液",
                "日用品",
                "生活用品",
                "叮咚买菜",
                "朴朴",
                "美团优选",
                "快递",
            ),
        ),
        (
            "购物",
            (
                "淘宝",
                "天猫",
                "京东",
                "拼多多",
                "唯品会",
                "抖音商城",
                "小红书",
                "网购",
                "下单",
                "购物",
                "购买",
                "买了",
                "衣服",
                "鞋",
                "包",
                "服饰",
                "数码",
                "手机",
                "电脑",
                "家电",
                "电器",
                "买",
            ),
        ),
        (
            "学习",
            (
                "课程",
                "网课",
                "培训",
                "学费",
                "考试",
                "报名费",
                "教材",
                "图书",
                "书籍",
                "学习",
                "得到",
                "知识星球",
                "论文",
                "托福",
                "雅思",
            ),
        ),
        (
            "娱乐",
            (
                "电影",
                "电影票",
                "影院",
                "演唱会",
                "剧院",
                "游戏",
                "steam",
                "switch",
                "ktv",
                "酒吧",
                "桌游",
                "展览",
                "门票",
                "爱奇艺",
                "腾讯视频",
                "优酷",
                "b站",
                "网易云",
            ),
        ),
        (
            "通讯",
            (
                "话费",
                "流量",
                "手机费",
                "电话费",
                "通信",
                "通讯",
                "中国移动",
                "中国联通",
                "中国电信",
            ),
        ),
        (
            "旅行",
            (
                "酒店",
                "民宿",
                "住宿",
                "旅行",
                "旅游",
                "景区",
                "携程",
                "飞猪",
                "去哪儿",
            ),
        ),
        (
            "人情",
            (
                "红包",
                "礼金",
                "份子钱",
                "随礼",
                "礼物",
                "请客",
            ),
        ),
        (
            "订阅",
            (
                "订阅",
                "会员",
                "月卡",
                "年费",
                "自动续费",
                "netflix",
                "spotify",
            ),
        ),
    )
    _salary_keywords = ("工资", "薪资", "薪水", "奖金", "年终奖", "绩效", "津贴")

    def classify(
        self,
        text: str,
        transaction_type: TransactionType | str | None = None,
    ) -> BillCategoryMatch:
        configured_categories = self._configured_categories()
        explicit = self._extract_explicit_category(text)
        if explicit is not None:
            return BillCategoryMatch(
                category=self.normalize_category(explicit, configured_categories),
                confidence=0.96,
                source="explicit",
                matched_keywords=(explicit,),
            )

        direct = self._category_from_direct_label(text, configured_categories)
        if direct is not None:
            return BillCategoryMatch(
                category=direct,
                confidence=0.9,
                source="category_label",
                matched_keywords=(direct,),
            )

        keyword_match = self._category_from_keywords(text, configured_categories)
        if keyword_match is not None:
            return keyword_match

        transaction_value = self._transaction_value(transaction_type)
        if transaction_value == TransactionType.income.value:
            confidence = 0.78 if self._contains_any(text, self._salary_keywords) else 0.62
            return BillCategoryMatch(
                category=self._preferred_category(("工资", "工资收入", "收入"), configured_categories),
                confidence=confidence,
                source="transaction_type",
            )
        if transaction_value == TransactionType.refund.value:
            return BillCategoryMatch(
                category=self._preferred_category(("退款", "其他"), configured_categories),
                confidence=0.58,
                source="transaction_type",
            )
        if transaction_value == TransactionType.transfer.value:
            return BillCategoryMatch(
                category=self._preferred_category(("转账", "其他"), configured_categories),
                confidence=0.58,
                source="transaction_type",
            )

        return BillCategoryMatch(
            category=self._preferred_category((self._default_category,), configured_categories),
            confidence=0.45,
            source="fallback",
        )

    def normalize_category(
        self,
        category: str | None,
        configured_categories: Iterable[str] | None = None,
    ) -> str:
        categories = list(configured_categories) if configured_categories is not None else self._configured_categories()
        return self._resolve_category(category, categories, allow_unknown=True) or self._default_category

    def _configured_categories(self) -> list[str]:
        try:
            configured = settings_store.get_category_settings().bill_categories
        except (AttributeError, ValueError, OSError):
            configured = []

        categories: list[str] = []
        for value in [*configured, self._default_category]:
            cleaned = self._clean_category(value)
            if cleaned and cleaned not in categories:
                categories.append(cleaned)
        return categories

    def _extract_explicit_category(self, text: str) -> str | None:
        for pattern in self._explicit_category_patterns:
            match = pattern.search(text)
            if match is None:
                continue
            category = self._clean_category(match.group(1))
            if category:
                return category
        return None

    def _category_from_direct_label(
        self,
        text: str,
        configured_categories: list[str],
    ) -> str | None:
        normalized_text = text.casefold()
        candidates = sorted(
            (category for category in configured_categories if category != self._default_category),
            key=len,
            reverse=True,
        )
        for category in candidates:
            if category.casefold() in normalized_text:
                return category
        return None

    def _category_from_keywords(
        self,
        text: str,
        configured_categories: list[str],
    ) -> BillCategoryMatch | None:
        normalized_text = text.casefold()
        best_category: str | None = None
        best_score = 0
        best_keywords: tuple[str, ...] = ()

        for category, keywords in self._category_rules:
            matched = tuple(
                keyword for keyword in keywords if keyword.casefold() in normalized_text
            )
            if not matched:
                continue
            score = sum(max(1, min(5, len(keyword))) for keyword in matched)
            if score > best_score:
                best_category = category
                best_score = score
                best_keywords = matched

        if best_category is None:
            return None

        return BillCategoryMatch(
            category=self._resolve_category(best_category, configured_categories, allow_unknown=True)
            or self._default_category,
            confidence=round(min(0.92, 0.64 + best_score * 0.04), 2),
            source="keywords",
            matched_keywords=best_keywords,
        )

    def _preferred_category(
        self,
        labels: tuple[str, ...],
        configured_categories: list[str],
    ) -> str:
        for label in labels:
            resolved = self._resolve_category(label, configured_categories, allow_unknown=False)
            if resolved is not None:
                return resolved
        return self._resolve_category(labels[0], configured_categories, allow_unknown=True) or self._default_category

    def _resolve_category(
        self,
        raw_category: str | None,
        configured_categories: list[str],
        *,
        allow_unknown: bool,
    ) -> str | None:
        category = self._clean_category(raw_category)
        if not category:
            return None

        candidates = [category]
        alias = self._aliases.get(category.casefold())
        if alias is not None:
            candidates.append(alias)
        for candidate in tuple(candidates):
            candidates.extend(self._fallbacks.get(candidate, ()))

        for candidate in candidates:
            for configured in configured_categories:
                if configured.casefold() == candidate.casefold():
                    return configured
        return candidates[-1] if candidates and allow_unknown else None

    def _clean_category(self, value: str | None) -> str | None:
        if value is None:
            return None
        category = str(value).strip(" \t\r\n，,。；;：:")
        category = re.split(r"[\s，,。；;]+", category, maxsplit=1)[0]
        category = re.sub(r"(?:就行|即可|就好|吧|了)$", "", category).strip(" \t\r\n，,。；;：:")
        return category[:40] or None

    def _contains_any(self, text: str, keywords: tuple[str, ...]) -> bool:
        normalized_text = text.casefold()
        return any(keyword.casefold() in normalized_text for keyword in keywords)

    def _transaction_value(self, transaction_type: TransactionType | str | None) -> str | None:
        if isinstance(transaction_type, TransactionType):
            return transaction_type.value
        if transaction_type is None:
            return None
        return str(transaction_type)


bill_category_classifier = BillCategoryClassifier()
