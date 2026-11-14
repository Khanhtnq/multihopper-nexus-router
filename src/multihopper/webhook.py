"""
MultiHopper Webhook Signature Verification and Event Dispatcher.
MultiHopper webhooks deliver signed real-time lifecycle events via HMAC-SHA256 headers:
`x-multihopper-signature: sha256=<hex_digest>`
"""

import hmac
import hashlib
import json
import time
from typing import Dict, Any, Optional, Callable, List


class WebhookManager:
    """
    Manages webhook signature generation, verification, and handler routing.
    """
    def __init__(self, webhook_secret: str):
        self.webhook_secret = webhook_secret.encode('utf-8')
        self.handlers: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}

    def sign_payload(self, payload_bytes: bytes) -> str:
        """Computes HMAC-SHA256 signature over raw request body."""
        sig = hmac.new(self.webhook_secret, payload_bytes, hashlib.sha256).hexdigest()
        return f"sha256={sig}"

    def verify_signature(self, payload_bytes: bytes, signature_header: str) -> bool:
        """
        Constant-time comparison against header signature.
        """
        if not signature_header or not signature_header.startswith("sha256="):
            return False

        expected_sig = signature_header.split("sha256=")[-1].strip()
        computed_sig = hmac.new(self.webhook_secret, payload_bytes, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_sig, computed_sig)

    def register_handler(self, event_type: str, handler: Callable[[Dict[str, Any]], None]):
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)

    def process_event(self, payload_bytes: bytes, signature_header: str) -> Dict[str, Any]:
        """
        Verifies signature, parses event, and dispatches to registered handlers.
        """
        if not self.verify_signature(payload_bytes, signature_header):
            raise ValueError("Invalid webhook HMAC signature.")

        event = json.loads(payload_bytes.decode('utf-8'))
        event_type = event.get("event") or event.get("type")

        if event_type in self.handlers:
            for h in self.handlers[event_type]:
                h(event)

        return event

    @staticmethod
    def create_mock_event(
        event_type: str,
        transfer_id: str,
        route_id: str,
        token_mint: str,
        amount_tokens: str,
        recipient_wallet: str,
        current_hop: int = 1,
        total_hops: int = 3
    ) -> Dict[str, Any]:
        """Generates realistic MultiHopper webhook event payload."""
        now = int(time.time())
        return {
            "id": f"evt_{now}_{transfer_id[:8]}",
            "event": event_type,
            "createdAt": now,
            "data": {
                "transferId": transfer_id,
                "routeId": route_id,
                "tokenMint": token_mint,
                "amountTokens": amount_tokens,
                "recipientWallet": recipient_wallet,
                "currentHop": current_hop,
                "totalHops": total_hops,
                "status": "settled" if event_type == "transfer.settled" else "in_progress",
                "txSignature": f"5xK{now}MockSolanaTxSignature{transfer_id[:6]}Hash",
                "integratorRewardsLamports": 2500000,
            }
        }
