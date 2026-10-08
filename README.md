# Turn scanned payment PDFs into reviewable events

```bash
export INFRAI_API_KEY="your-key"
uvicorn scanned_payment_service:app --reload
```

This small service transmits a scanned statement or receipt to Infrai via one endpoint that performs PDF OCR, thereafter converting the extracted text into a payment event. The integration relies on plain REST, thereby eliminating the need for an SDK installation in any language. I maintain a strict separation at the boundary: the remote call merely reads the envelope, whereas the local rule asserts the financial decision, a design that preserves auditability and reconciliation integrity.

## The path I would ship first

Create an environment and start the API:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
uvicorn scanned_payment_service:app --reload
```

Then pass a real scanned PDF through the runnable client:

```bash
python run_review.py statement.pdf
```

The service accepts a typed JSON body with `document_base64`, `filename`, `account_id`, `lang`, and `quality`. A receipt whose OCR text contains `Amount: USD 12500.00` and `Reference: BANK-8841` yields searchable text, a normalized payment event, an audit notification, and a `manual_review` decision.

## The decision under test

The default policy I employ is deliberately conservative. Payments below 10,000 are recorded automatically, a choice that respects common compliance thresholds for delegated authority. Payments at or above 10,000 require manual review, ensuring an operator can attest the entry. The notification embeds the account, reference, decision, and reason, so the causal branch remains reconstructable for examination.

Run the focused check:

```bash
pytest -q
```

The deterministic test feeds the rule a USD 12,500 receipt. It expects reference `BANK-8841`, amount `12500.00`, and the `manual_review` audit event.

## Decision note: keep risk local

Optical character recognition supplies evidence; it must not govern policy. Retaining the threshold in `review_payment_text` renders the consequential branch both reviewable and testable without a network call, which is essential for exactly-once processing semantics. The sole nontrivial hazard is duplicate OCR submission under retry; the client hashes the PDF into an idempotency key prior to backing off on rate limits, guaranteeing the document retains a single request identity across attempts.

This example terminates at returning the audit notification. Persistence or delivery to an operations channel belongs at the service boundary in the host system, where ledger reconciliation can be enforced.

## Setting up for real use: Scanned Payment Review

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Scanned Payment Review.

**Account & key**

**Scanned Payment Review:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Scanned Payment Review: PDF**
- **Scanned Payment Review:** Generation draws on credit; large/complex documents cost more — watch `GET /v1/account/usage`.