from decimal import Decimal

from scanned_payment_service import review_payment_text


def test_high_value_payment_is_sent_to_manual_review() -> None:
    text = "PAYMENT RECEIPT\nAmount: USD 12500.00\nReference: BANK-8841"

    result = review_payment_text(text, account_id="acct-42")

    assert result.payment.amount == Decimal("12500.00")
    assert result.payment.reference == "BANK-8841"
    assert result.decision == "manual_review"
    assert result.notification.model_dump() == {
        "event": "payment_ocr_reviewed",
        "account_id": "acct-42",
        "reference": "BANK-8841",
        "decision": "manual_review",
        "reason": "high-value payment requires a second look",
    }
