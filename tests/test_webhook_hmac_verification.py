import pytest
import json
from src.multihopper.webhook import WebhookManager


def test_webhook_hmac_generation_and_validation():
    secret = "test_superteam_secret_key_123"
    mgr = WebhookManager(secret)

    payload = json.dumps({"event": "transfer.settled", "transferId": "trf_12345"}).encode('utf-8')
    sig_header = mgr.sign_payload(payload)

    # Valid signature check
    assert mgr.verify_signature(payload, sig_header) is True

    # Tampered payload check
    tampered_payload = json.dumps({"event": "transfer.settled", "transferId": "trf_TAMPERED"}).encode('utf-8')
    assert mgr.verify_signature(tampered_payload, sig_header) is False

    # Corrupted signature header check
    assert mgr.verify_signature(payload, "sha256=invalidhexdigest12345") is False
    assert mgr.verify_signature(payload, "malformed_header_no_sha_prefix") is False


def test_webhook_event_dispatch():
    secret = "test_dispatch_secret"
    mgr = WebhookManager(secret)

    received_events = []
    def on_settled(ev):
        received_events.append(ev)

    mgr.register_handler("transfer.settled", on_settled)

    mock_event = WebhookManager.create_mock_event(
        event_type="transfer.settled",
        transfer_id="trf_abc999",
        route_id="route_xyz111",
        token_mint="So11111111111111111111111111111111111111112",
        amount_tokens="10.0",
        recipient_wallet="RecipWallet999"
    )
    raw_bytes = json.dumps(mock_event).encode('utf-8')
    sig = mgr.sign_payload(raw_bytes)

    dispatched = mgr.process_event(raw_bytes, sig)
    assert dispatched["event"] == "transfer.settled"
    assert len(received_events) == 1
    assert received_events[0]["data"]["transferId"] == "trf_abc999"
