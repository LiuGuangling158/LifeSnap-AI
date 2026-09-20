from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from app.schemas.agent import BillCandidateData, ParseBillRequest, ParseBillResponse
from app.schemas.bill import BillSource, TransactionType
from app.services.bill_parser import ConfigurableBillParser, RuleBasedBillParser


class PaymentScreenshotParserTests(TestCase):
    _payment_screenshot = """
    全部订单
    -25.00
    当前状态 支付成功
    支付时间 2026年9月6日 19:48:38
    收款方 小程序商户
    支付方式 零钱
    """

    def test_rule_parser_reads_standalone_negative_payment_amount(self) -> None:
        candidate = RuleBasedBillParser().parse_bill(
            ParseBillRequest(text=self._payment_screenshot, source=BillSource.upload)
        )

        self.assertEqual(candidate.data.amount, Decimal("25.00"))
        self.assertEqual(candidate.data.transaction_type, TransactionType.expense)
        self.assertEqual(candidate.data.merchant, "小程序商户")
        self.assertEqual(candidate.data.payment_method, "微信支付")

    def test_missing_external_amount_falls_back_to_deterministic_payment_parser(self) -> None:
        incomplete = ParseBillResponse(
            candidate_id=uuid4(),
            confidence=0.4,
            data=BillCandidateData(
                amount=None,
                category="其他",
                transaction_type=TransactionType.expense,
                source=BillSource.upload,
            ),
            field_confidence={"amount": 0.0},
            warnings=["amount_missing"],
        )
        with patch(
            "app.services.bill_parser.external_ai_parser.parse_bill",
            return_value=(incomplete, []),
        ):
            candidate = ConfigurableBillParser().parse_bill(
                ParseBillRequest(text=self._payment_screenshot, source=BillSource.upload)
            )

        self.assertEqual(candidate.data.amount, Decimal("25.00"))
        self.assertIn("external_ai_parser_amount_missing_fallback", candidate.warnings)
