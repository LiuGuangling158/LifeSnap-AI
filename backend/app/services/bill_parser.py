import re
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from app.schemas.agent import BillCandidateData, ParseBillRequest, ParseBillResponse
from app.schemas.bill import TransactionType


class RuleBasedBillParser:
    _amount_patterns = [
        re.compile(r"(?:¥|￥|人民币|金额|实付|支付|付款)\s*([0-9]+(?:\.[0-9]{1,2})?)"),
        re.compile(r"([0-9]+(?:\.[0-9]{1,2})?)\s*元"),
    ]
    _payment_keywords = {
        "微信": "微信支付",
        "wechat": "微信支付",
        "支付宝": "支付宝",
        "alipay": "支付宝",
        "银行卡": "银行卡",
        "云闪付": "云闪付",
    }
    _category_keywords = {
        "咖啡": "餐饮",
        "早餐": "餐饮",
        "午餐": "餐饮",
        "晚餐": "餐饮",
        "外卖": "餐饮",
        "餐": "餐饮",
        "打车": "交通",
        "地铁": "交通",
        "公交": "交通",
        "医院": "医疗",
        "药": "医疗",
        "会员": "订阅",
        "话费": "通讯",
        "房租": "居住",
        "水电": "居住",
    }

    def parse_bill(self, payload: ParseBillRequest) -> ParseBillResponse:
        text = payload.text.strip()
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        amount = self._extract_amount(text)
        merchant = self._extract_merchant(lines)
        payment_method = self._extract_payment_method(text)
        category = self._extract_category(text)
        warnings = self._build_warnings(amount, merchant, payment_method, category)
        field_confidence = self._field_confidence(amount, merchant, payment_method, category)

        data = BillCandidateData(
            amount=amount,
            merchant=merchant,
            category=category,
            payment_method=payment_method,
            transaction_type=TransactionType.expense,
            note="规则解析生成的候选账单",
            source=payload.source,
        )

        return ParseBillResponse(
            candidate_id=uuid4(),
            confidence=self._overall_confidence(field_confidence),
            data=data,
            field_confidence=field_confidence,
            warnings=warnings,
            need_user_confirmation=True,
        )

    def _extract_amount(self, text: str) -> Decimal | None:
        for pattern in self._amount_patterns:
            match = pattern.search(text)
            if match is None:
                continue
            try:
                return Decimal(match.group(1))
            except InvalidOperation:
                return None
        return None

    def _extract_merchant(self, lines: list[str]) -> str | None:
        ignored_keywords = ["支付", "付款", "金额", "成功", "订单", "交易", "时间"]
        for line in lines:
            if len(line) > 120:
                continue
            if any(keyword in line for keyword in ignored_keywords):
                continue
            if re.search(r"[0-9]+(?:\.[0-9]{1,2})?\s*元", line):
                continue
            return line
        return None

    def _extract_payment_method(self, text: str) -> str | None:
        normalized_text = text.casefold()
        for keyword, payment_method in self._payment_keywords.items():
            if keyword.casefold() in normalized_text:
                return payment_method
        return None

    def _extract_category(self, text: str) -> str:
        for keyword, category in self._category_keywords.items():
            if keyword in text:
                return category
        return "其他"

    def _build_warnings(
        self,
        amount: Decimal | None,
        merchant: str | None,
        payment_method: str | None,
        category: str,
    ) -> list[str]:
        warnings: list[str] = []
        if amount is None:
            warnings.append("amount_missing")
        if merchant is None:
            warnings.append("merchant_missing")
        if payment_method is None:
            warnings.append("payment_method_missing")
        if category == "其他":
            warnings.append("category_low_confidence")
        return warnings

    def _field_confidence(
        self,
        amount: Decimal | None,
        merchant: str | None,
        payment_method: str | None,
        category: str,
    ) -> dict[str, float]:
        return {
            "amount": 0.95 if amount is not None else 0.0,
            "merchant": 0.7 if merchant is not None else 0.0,
            "category": 0.75 if category != "其他" else 0.45,
            "payment_method": 0.8 if payment_method is not None else 0.0,
            "paid_at": 0.0,
        }

    def _overall_confidence(self, field_confidence: dict[str, float]) -> float:
        important_fields = ["amount", "merchant", "category", "payment_method"]
        score = sum(field_confidence[field] for field in important_fields) / len(important_fields)
        return round(score, 2)


bill_parser = RuleBasedBillParser()

