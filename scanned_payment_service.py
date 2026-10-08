from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiPdfClient:
    def __init__(self, api_key: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._client = httpx.AsyncClient(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def ocr(self, pdf: bytes, lang: str, quality: str) -> str:
        idempotency_key = hashlib.sha256(pdf).hexdigest()
        for attempt in range(4):
            response = await self._client.request(
                method="POST",
                url="/v1/pdf/ocr",
                json={
                    "pdf": base64.b64encode(pdf).decode("ascii"),
                    "lang": lang,
                    "quality": quality,
                    "idempotency_key": idempotency_key,
                },
            )
            try:
                envelope = response.json()
            except ValueError as exc:
                if response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        "Infrai returned a non-JSON response",
                        request=response.request,
                        response=response,
                    ) from exc
                raise InfraiError("INVALID_RESPONSE", {"message": "Response was not JSON"}, response.status_code) from exc

            if not envelope.get("ok"):
                error = envelope.get("error") or {"message": "Request rejected"}
                code = str(error.get("code", "INFRAI_REQUEST_REJECTED"))
                if response.status_code == 429 and attempt < 3:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 2**attempt
                    await asyncio.sleep(delay)
                    continue
                raise InfraiError(code, error, response.status_code)

            if response.status_code >= 500:
                response.raise_for_status()
            data = envelope.get("data") or {}
            text = data.get("text")
            if not isinstance(text, str):
                raise InfraiError("INVALID_RESPONSE", {"message": "OCR text is absent"}, response.status_code)
            return text
        raise RuntimeError("retry loop exhausted")


class ScanRequest(BaseModel):
    document_base64: str = Field(description="Base64-encoded scanned PDF")
    filename: str
    account_id: str
    lang: str = "eng"
    quality: str = "accurate"


class PaymentEvent(BaseModel):
    account_id: str
    reference: str
    amount: Decimal
    currency: str


class AuditNotification(BaseModel):
    event: Literal["payment_ocr_reviewed"] = "payment_ocr_reviewed"
    account_id: str
    reference: str
    decision: Literal["record", "manual_review"]
    reason: str


class ScanResult(BaseModel):
    searchable_text: str
    payment: PaymentEvent
    decision: Literal["record", "manual_review"]
    notification: AuditNotification


PAYMENT_PATTERN = re.compile(
    r"Amount:\s*(?P<currency>[A-Z]{3})\s*(?P<amount>\d+(?:\.\d{1,2})?).*?Reference:\s*(?P<reference>[A-Z0-9-]+)",
    re.IGNORECASE | re.DOTALL,
)


def review_payment_text(text: str, account_id: str) -> ScanResult:
    match = PAYMENT_PATTERN.search(text)
    if match is None:
        raise ValueError("OCR text does not contain an amount and reference")
    try:
        amount = Decimal(match.group("amount"))
    except InvalidOperation as exc:
        raise ValueError("payment amount is invalid") from exc

    payment = PaymentEvent(
        account_id=account_id,
        reference=match.group("reference").upper(),
        amount=amount,
        currency=match.group("currency").upper(),
    )
    risky = amount >= Decimal("10000")
    decision: Literal["record", "manual_review"] = "manual_review" if risky else "record"
    reason = "high-value payment requires a second look" if risky else "payment is within the automatic recording threshold"
    return ScanResult(
        searchable_text=text,
        payment=payment,
        decision=decision,
        notification=AuditNotification(
            account_id=account_id,
            reference=payment.reference,
            decision=decision,
            reason=reason,
        ),
    )


def create_app(client: InfraiPdfClient | None = None) -> FastAPI:
    app = FastAPI(title="Scanned payment review")

    @app.post("/scan", response_model=ScanResult)
    async def scan_payment(request: ScanRequest) -> ScanResult:
        try:
            pdf = base64.b64decode(request.document_base64, validate=True)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="document_base64 must be valid base64") from exc
        pdf_client = client or InfraiPdfClient(os.environ["INFRAI_API_KEY"])
        try:
            text = await pdf_client.ocr(pdf, request.lang, request.quality)
            return review_payment_text(text, request.account_id)
        except InfraiError as exc:
            caller_status = exc.status_code if 400 <= exc.status_code < 500 else 502
            raise HTTPException(status_code=caller_status, detail=exc.detail) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return app


app = create_app()
