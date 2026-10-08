import base64
import json
import os
import sys

import httpx


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python run_review.py statement.pdf")
    with open(sys.argv[1], "rb") as source:
        document_base64 = base64.b64encode(source.read()).decode("ascii")

    response = httpx.request(
        method="POST",
        url=os.environ.get("PAYMENT_REVIEW_URL", "http://127.0.0.1:8000/scan"),
        json={
            "document_base64": document_base64,
            "filename": os.path.basename(sys.argv[1]),
            "account_id": "acct-demo-17",
            "lang": "eng",
            "quality": "accurate",
        },
        timeout=60.0,
    )
    response.raise_for_status()
    print(json.dumps(response.json(), indent=2))


if __name__ == "__main__":
    main()
