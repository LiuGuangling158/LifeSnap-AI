import re
from datetime import datetime, time, timedelta
from uuid import uuid4

from app.schemas.agent import ParseTaskRequest, ParseTaskResponse, TaskCandidateData
from app.schemas.task import TaskPriority, TaskType
from app.services.external_ai_parser import external_ai_parser


class RuleBasedTaskParser:
    _clock_pattern = re.compile(
        r"(?:(上午|中午|下午|晚上|今晚|早上|凌晨)\s*)?([0-2]?\d)\s*(?:[:：点时])\s*([0-5]?\d)?"
    )
    _month_day_pattern = re.compile(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]?")
    _date_tokens = (
        "今天",
        "今晚",
        "明天",
        "后天",
        "下周",
        "下星期",
        "这周",
        "本周",
    )
    _reminder_keywords = ("提醒", "闹钟", "到点", "别忘", "记得")
    _todo_keywords = ("待办", "任务", "安排", "todo")
    _high_priority_keywords = ("紧急", "重要", "马上", "尽快", "高优先级", "必须")
    _low_priority_keywords = ("不急", "有空", "空了", "低优先级")
    _category_keywords = {
        "医疗": ("医院", "复诊", "体检", "医保", "医生", "药", "牙"),
        "居住": ("房租", "水电", "物业", "宽带", "燃气", "维修"),
        "工作": ("会议", "面试", "汇报", "项目", "合同", "客户"),
        "学习": ("考试", "课程", "作业", "论文", "学习", "报名"),
        "财务": ("还款", "报销", "发票", "转账", "账单", "预算"),
        "生活": ("快递", "取件", "购物", "买菜", "洗衣", "预约"),
    }

    def parse_task(self, payload: ParseTaskRequest) -> ParseTaskResponse:
        text = payload.text.strip()
        task_type = self._extract_task_type(text)
        target_at, date_found, clock_found = self._extract_target_at(text)
        due_at = self._build_due_at(task_type, target_at, date_found, clock_found)
        remind_at = target_at if task_type == TaskType.reminder and clock_found else None

        data = TaskCandidateData(
            title=self._extract_title(text),
            description=text[:500],
            category=self._extract_category(text),
            task_type=task_type,
            due_at=due_at,
            remind_at=remind_at,
            priority=self._extract_priority(text),
            source=payload.source,
        )
        field_confidence = self.field_confidence_for_data(data)

        return ParseTaskResponse(
            candidate_id=uuid4(),
            confidence=self.overall_confidence(field_confidence, data.task_type),
            data=data,
            field_confidence=field_confidence,
            warnings=self.warnings_for_data(data),
            need_user_confirmation=True,
        )

    def warnings_for_data(self, data: TaskCandidateData) -> list[str]:
        warnings: list[str] = []
        if data.title is None:
            warnings.append("title_missing")
        if data.category == "生活":
            warnings.append("category_low_confidence")
        if data.task_type == TaskType.reminder and data.remind_at is None:
            warnings.append("remind_time_missing")
        return warnings

    def field_confidence_for_data(self, data: TaskCandidateData) -> dict[str, float]:
        return {
            "title": 0.85 if data.title is not None else 0.0,
            "category": 0.8 if data.category != "生活" else 0.45,
            "task_type": 0.85 if data.task_type == TaskType.reminder else 0.65,
            "due_at": 0.75 if data.due_at is not None else 0.0,
            "remind_at": 0.85 if data.remind_at is not None else 0.0,
            "priority": 0.8 if data.priority != TaskPriority.medium else 0.55,
        }

    def overall_confidence(
        self,
        field_confidence: dict[str, float],
        task_type: TaskType,
    ) -> float:
        important_fields = ["title", "category", "task_type", "priority"]
        if task_type == TaskType.reminder:
            important_fields.append("remind_at")
        score = sum(field_confidence[field] for field in important_fields) / len(
            important_fields
        )
        return round(score, 2)

    def _extract_task_type(self, text: str) -> TaskType:
        if any(keyword in text for keyword in self._reminder_keywords):
            return TaskType.reminder
        if any(keyword.casefold() in text.casefold() for keyword in self._todo_keywords):
            return TaskType.todo
        if self._clock_pattern.search(text) is not None:
            return TaskType.reminder
        return TaskType.todo

    def _extract_title(self, text: str) -> str | None:
        cleaned = self._clock_pattern.sub("", text)
        cleaned = self._month_day_pattern.sub("", cleaned)
        for token in self._date_tokens:
            cleaned = cleaned.replace(token, "")

        cleaned = re.sub(
            r"^(请|麻烦|帮我|帮忙|给我)?(提醒我|提醒一下我|记得|别忘|新增|创建|安排|加一个|把|将)",
            "",
            cleaned,
        )
        cleaned = re.sub(r"^(我需要|我要|需要|要)", "", cleaned)
        cleaned = re.sub(r"(加入|加到|放到)?待办$", "", cleaned)
        cleaned = re.sub(r"(设为|设置为)?提醒$", "", cleaned)
        cleaned = cleaned.strip(" ，,。.;；:：")

        title = re.split(r"[，,。.;；\n]", cleaned, maxsplit=1)[0].strip()
        if not title:
            return None
        return title[:120]

    def _extract_category(self, text: str) -> str:
        for category, keywords in self._category_keywords.items():
            if any(keyword in text for keyword in keywords):
                return category
        return "生活"

    def _extract_priority(self, text: str) -> TaskPriority:
        if any(keyword in text for keyword in self._high_priority_keywords):
            return TaskPriority.high
        if any(keyword in text for keyword in self._low_priority_keywords):
            return TaskPriority.low
        return TaskPriority.medium

    def _extract_target_at(self, text: str) -> tuple[datetime | None, bool, bool]:
        now = datetime.now().astimezone()
        target_date = self._extract_target_date(text, now)
        clock = self._extract_clock(text)
        if target_date is None and clock is None:
            return None, False, False

        if target_date is None:
            target_date = now.date()
        if clock is None:
            return (
                datetime.combine(target_date, time(23, 59), tzinfo=now.tzinfo),
                True,
                False,
            )

        target_at = datetime.combine(target_date, clock, tzinfo=now.tzinfo)
        if target_at < now and target_date == now.date():
            target_at += timedelta(days=1)
        return target_at, True, True

    def _extract_target_date(self, text: str, now: datetime):
        month_day_match = self._month_day_pattern.search(text)
        if month_day_match is not None:
            month = int(month_day_match.group(1))
            day = int(month_day_match.group(2))
            try:
                target_date = now.replace(month=month, day=day).date()
            except ValueError:
                return None
            if target_date < now.date():
                try:
                    target_date = now.replace(year=now.year + 1, month=month, day=day).date()
                except ValueError:
                    return None
            return target_date

        if "后天" in text:
            return (now + timedelta(days=2)).date()
        if "明天" in text:
            return (now + timedelta(days=1)).date()
        if "今天" in text or "今晚" in text:
            return now.date()
        if "下周" in text or "下星期" in text:
            return (now + timedelta(days=7)).date()
        return None

    def _extract_clock(self, text: str) -> time | None:
        match = self._clock_pattern.search(text)
        if match is None:
            return None

        period = match.group(1) or ""
        hour = int(match.group(2))
        minute = int(match.group(3) or 0)
        if hour > 23 or minute > 59:
            return None
        if period in {"下午", "晚上", "今晚"} and hour < 12:
            hour += 12
        if period == "中午" and hour < 11:
            hour += 12
        if period == "凌晨" and hour == 12:
            hour = 0
        return time(hour, minute)

    def _build_due_at(
        self,
        task_type: TaskType,
        target_at: datetime | None,
        date_found: bool,
        clock_found: bool,
    ) -> datetime | None:
        if task_type != TaskType.todo or target_at is None:
            return None
        if date_found or clock_found:
            return target_at
        return None


class ConfigurableTaskParser:
    def __init__(self) -> None:
        self._rule_based_parser = RuleBasedTaskParser()

    def parse_task(self, payload: ParseTaskRequest) -> ParseTaskResponse:
        external_candidate, fallback_warnings = external_ai_parser.parse_task(payload)
        if external_candidate is not None:
            return external_candidate

        candidate = self._rule_based_parser.parse_task(payload)
        candidate.warnings = self._dedupe(candidate.warnings + fallback_warnings)
        return candidate

    def warnings_for_data(self, data: TaskCandidateData) -> list[str]:
        return self._rule_based_parser.warnings_for_data(data)

    def field_confidence_for_data(self, data: TaskCandidateData) -> dict[str, float]:
        return self._rule_based_parser.field_confidence_for_data(data)

    def overall_confidence(
        self,
        field_confidence: dict[str, float],
        task_type: TaskType,
    ) -> float:
        return self._rule_based_parser.overall_confidence(field_confidence, task_type)

    def _dedupe(self, warnings: list[str]) -> list[str]:
        deduped: list[str] = []
        for warning in warnings:
            if warning not in deduped:
                deduped.append(warning)
        return deduped


task_parser = ConfigurableTaskParser()
