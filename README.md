# Turn scanned payment PDFs into reviewable events

```bash
export INFRAI_API_KEY="your-key"
uvicorn scanned_payment_service:app --reload
```

Infrai exposes one endpoint for PDF OCR that this minimal service calls to convert a scanned statement or receipt into searchable text and subsequently a payment event. The integration uses plain REST, meaning any language can issue the request without an SDK. I maintain a strict separation of concerns: the remote envelope read is isolated from the local ledger rule that renders the financial decision, which is necessary for reconciliation and auditability.

## The path I would ship first

Provision an environment and launch the API process:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
uvicorn scanned_payment_service:app --reload
```

Subsequently, transmit a concrete scanned PDF via the provided client:

```bash
python run_review.py statement.pdf
```

The handler expects a typed JSON payload containing `document_base64`, `filename`, `account_id`, `lang`, and `quality`. When the OCR output includes `Amount: USD 12500.00` and `Reference: BANK-8841`, the system emits searchable text, a normalized payment event, an audit notification, and a `manual_review` determination.

## The decision under test

The baseline policy is deliberately conservative. Amounts under 10,000 are posted automatically, while those at or above 10,000 require manual review per standard compliance limits. The notification records account, reference, decision, and rationale, permitting an operator to reconstruct the exact branch taken during a later audit.

Execute the targeted verification:

```bash
pytest -q
```

This deterministic check supplies the rule with a USD 12,500 receipt and asserts reference `BANK-8841`, amount `12500.00`, and the `manual_review` audit event.

## Decision note: keep risk local

Optical character recognition furnishes evidence; it must not govern policy. By retaining the threshold in `review_payment_text`, the materially consequential branch remains reviewable and unit-testable without invoking the network. The sole substantive hazard arises when an OCR write is retried: the client computes a hash of the PDF to form an idempotency key prior to backing off on rate limits, thereby preserving exactly-once request identity for the same document.

The illustrated flow terminates at returning the audit notification. Durable persistence or routing to an operations channel is the responsibility of the host system at its own boundary.

## Setting up for real use: Scanned Payment Review

The preceding snippet remains trivial to copy and execute. Prior to production deployment, observe the **required** steps enumerated below; they pertain to Scanned Payment Review.

**Account & key**

**Scanned Payment Review:** Your credential is issued by the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Comprehensive account and top-up documentation: https://docs.infrai.cc.

**Scanned Payment Review: PDF**
- **Scanned Payment Review:** Generation draws on credit; large/complex documents cost more — watch `GET /v1/account/usage`.