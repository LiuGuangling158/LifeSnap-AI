import re
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from app.schemas.agent import BillCandidateData, ParseBillRequest, ParseBillResponse
from app.schemas.bill import TransactionType
from app.services.bill_category_classifier import bill_category_classifier
from app.services.external_ai_parser import external_ai_parser


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
    def parse_bill(self, payload: ParseBillRequest) -> ParseBillResponse:
        text = payload.text.strip()
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        amount = self._extract_amount(text)
        merchant = self._extract_merchant(lines)
        payment_method = self._extract_payment_method(text)
        transaction_type = self._extract_transaction_type(text)
        category_match = self._extract_category(text, transaction_type)
        category = category_match.category
        warnings = self._build_warnings(amount, merchant, payment_method, category)
        field_confidence = self._field_confidence(
            amount,
            merchant,
            payment_method,
            category,
            category_match.confidence,
        )

        data = BillCandidateData(
            amount=amount,
            merchant=merchant,
            category=category,
            payment_method=payment_method,
            transaction_type=transaction_type,
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
                amount = Decimal(match.group(1))
                return amount if amount > 0 else None
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

    def _extract_transaction_type(self, text: str) -> TransactionType:
        for keywords, transaction_type in (
            (("退款", "退回"), TransactionType.refund),
            (("工资", "收入", "奖金"), TransactionType.income),
            (("充值", "储值"), TransactionType.top_up),
            (("转账",), TransactionType.transfer),
        ):
            if any(keyword in text for keyword in keywords):
                return transaction_type
        return TransactionType.expense

    def _extract_payment_method(self, text: str) -> str | None:
        normalized_text = text.casefold()
        for keyword, payment_method in self._payment_keywords.items():
            if keyword.casefold() in normalized_text:
                return payment_method
        return None

    def _extract_category(self, text: str, transaction_type: TransactionType | None = None):
        return bill_category_classifier.classify(text, transaction_type)

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
        return warnings

    def _field_confidence(
        self,
        amount: Decimal | None,
        merchant: str | None,
        payment_method: str | None,
        category: str,
        category_confidence: float,
    ) -> dict[str, float]:
        return {
            "amount": 0.95 if amount is not None else 0.0,
            "merchant": 0.7 if merchant is not None else 0.0,
            "category": category_confidence,
            "payment_method": 0.8 if payment_method is not None else 0.0,
            "paid_at": 0.0,
            "transaction_type": 0.9,
        }

    def _overall_confidence(self, field_confidence: dict[str, float]) -> float:
        important_fields = ["amount", "transaction_type"]
        score = sum(field_confidence[field] for field in important_fields) / len(important_fields)
        return round(score, 2)


class ConfigurableBillParser:
    def __init__(self) -> None:
        self._rule_based_parser = RuleBasedBillParser()

    def parse_bill(self, payload: ParseBillRequest) -> ParseBillResponse:
        external_candidate, fallback_warnings = external_ai_parser.parse_bill(payload)
        if external_candidate is not None:
            return external_candidate

        candidate = self._rule_based_parser.parse_bill(payload)
        candidate.warnings = self._dedupe(candidate.warnings + fallback_warnings)
        return candidate

    def _dedupe(self, warnings: list[str]) -> list[str]:
        deduped: list[str] = []
        for warning in warnings:
            if warning not in deduped:
                deduped.append(warning)
        return deduped


bill_parser = ConfigurableBillParser()
