from datetime import datetime, timezone
from decimal import Decimal
from unittest import TestCase
from uuid import uuid4

from app.api.attachments import _find_existing_attachment_bill_candidate
from app.schemas.agent import BillCandidateData, ParseBillResponse
from app.schemas.attachment import AttachmentRead, AttachmentSource, RetentionPolicy
from app.schemas.bill import BillSource, TransactionType
from app.services.bill_candidate_store import bill_candidate_store


class AttachmentCandidateReuseTests(TestCase):
    def setUp(self) -> None:
        bill_candidate_store.clear()
        now = datetime.now(timezone.utc)
        self.attachment = AttachmentRead(
            id=uuid4(),
            filename="receipt.jpg",
            content_type="image/jpeg",
            file_size=1024,
            checksum="candidate-reuse-test",
            source=AttachmentSource.upload,
            retention_policy=RetentionPolicy.keep_until_user_delete,
            original_saved=True,
            created_at=now,
            updated_at=now,
        )

    def tearDown(self) -> None:
        bill_candidate_store.clear()

    def test_incomplete_duplicate_candidate_does_not_block_fresh_recognition(self) -> None:
        bill_candidate_store.save(self._candidate(amount=None))

        self.assertIsNone(_find_existing_attachment_bill_candidate(self.attachment))

    def test_confirmable_duplicate_candidate_is_reused(self) -> None:
        candidate = bill_candidate_store.save(self._candidate(amount=Decimal("18.50")))

        self.assertEqual(
            _find_existing_attachment_bill_candidate(self.attachment).candidate_id,
            candidate.candidate_id,
        )

    def _candidate(self, amount: Decimal | None) -> ParseBillResponse:
        return ParseBillResponse(
            candidate_id=uuid4(),
            source_attachment_id=self.attachment.id,
            confidence=0.9,
            data=BillCandidateData(
                amount=amount,
                category="餐饮",
                transaction_type=TransactionType.expense,
                source=BillSource.upload,
            ),
            field_confidence={"amount": 1.0 if amount is not None else 0.0},
            warnings=[] if amount is not None else ["amount_missing"],
        )
