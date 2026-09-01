import base64
from typing import Dict, Any, Optional
import httpx
from app.core.config import settings
from app.core.logger import logger


class MonnifyClient:
    """Monnify Payments Integration."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        contract_code: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or settings.MONNIFY_API_KEY
        self.secret_key = secret_key or settings.MONNIFY_SECRET_KEY
        self.contract_code = contract_code or settings.MONNIFY_CONTRACT_CODE
        self.base_url = (base_url or settings.MONNIFY_BASE_URL).rstrip("/")
        self._access_token: Optional[str] = None

    async def _get_auth_token(self) -> str:
        if not self.api_key or not self.secret_key:
            raise ValueError("MONNIFY_API_KEY or MONNIFY_SECRET_KEY is not configured.")

        auth_str = f"{self.api_key}:{self.secret_key}"
        encoded_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")

        url = f"{self.base_url}/api/v1/auth/login"
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, headers={"Authorization": f"Basic {encoded_auth}"})
            data = res.json()
            if res.status_code == 200 and data.get("requestSuccessful"):
                return data["responseBody"]["accessToken"]
            else:
                raise RuntimeError(f"Monnify auth failed: {data.get('responseMessage')}")

    async def initialize_payment(
        self,
        amount: float,
        currency: str,
        customer_name: str,
        customer_email: str,
        reference: str,
        redirect_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Initializes a dynamic invoice on Monnify."""
        if not self.contract_code:
            raise ValueError("MONNIFY_CONTRACT_CODE is not configured.")

        token = await self._get_auth_token()
        url = f"{self.base_url}/api/v1/merchant/transactions/init-transaction"

        payload = {
            "amount": amount,
            "customerName": customer_name or "Customer",
            "customerEmail": customer_email,
            "paymentReference": reference,
            "paymentDescription": f"Payment for Order {reference}",
            "currencyCode": currency.upper(),
            "contractCode": self.contract_code,
            "redirectUrl": redirect_url or settings.PAYSTACK_CALLBACK_URL,
            "paymentMethods": ["CARD", "ACCOUNT_TRANSFER"],
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json=payload, headers={"Authorization": f"Bearer {token}"})
            data = res.json()
            if res.status_code == 200 and data.get("requestSuccessful"):
                body = data["responseBody"]
                return {
                    "checkout_url": body.get("checkoutUrl"),
                    "transaction_reference": body.get("transactionReference"),
                    "reference": reference,
                }
            else:
                logger.error(f"Monnify init failed: {res.text}")
                raise RuntimeError(data.get("responseMessage", "Monnify initialization failed"))

    async def verify_payment(self, transaction_reference: str) -> Dict[str, Any]:
        """Verifies payment on Monnify."""
        token = await self._get_auth_token()
        url = f"{self.base_url}/api/v1/merchant/transactions/query?transactionReference={transaction_reference}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(url, headers={"Authorization": f"Bearer {token}"})
            data = res.json()
            if res.status_code == 200 and data.get("requestSuccessful"):
                body = data["responseBody"]
                return {
                    "status": "success" if body.get("paymentStatus") == "PAID" else body.get("paymentStatus"),
                    "amount": body.get("amountPaid"),
                    "reference": body.get("paymentReference"),
                    "raw": body,
                }
            else:
                raise RuntimeError(data.get("responseMessage", "Monnify query failed"))
