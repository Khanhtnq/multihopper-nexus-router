import pytest
from src.multihopper.client import MultiHopperClient


def test_client_full_transfer_lifecycle():
    client = MultiHopperClient(integrator_wallet="6mghraUR9NV2fA187VXoLN2rVS3WLA91UhqLfjtvDdmf")

    # Step 1: Create Transfer
    created = client.create_transfer(
        token_mint="So11111111111111111111111111111111111111112",
        amount_tokens=5.0,
        source_owner="6mghraUR9NV2fA187VXoLN2rVS3WLA91UhqLfjtvDdmf",
        recipient_wallet="H4iZ7C2Z1rXgQ2Xy9J4K6M3P8T9W1V5L2B8N4M7K9L2P",
        custom_route=["hop_alpha", "hop_beta", "hop_gamma"]
    )
    transfer_id = created["id"]
    assert created["status"] == "quote"
    assert created["hopsCount"] == 3

    # Step 2: Prepare Transfer
    prep = client.prepare_transfer(transfer_id)
    assert prep["transferId"] == transfer_id
    assert len(prep["transactions"]) == 2

    # Step 3: Confirm Broadcast
    sigs = ["5xKSignatureStep1Success", "5xKSignatureStep2Success"]
    conf = client.confirm_broadcast(transfer_id, sigs)
    assert conf["status"] == "deployed"

    # Step 4: Get Transfer Status
    trf = client.get_transfer(transfer_id)
    assert trf["status"] == "deployed"
    assert trf["phase"] == "KEEPER_EXECUTION"

    # Step 5: Check Usage Aggregation
    usage = client.get_usage()
    assert usage["metrics"]["totalTransfers"] == 1
    assert usage["metrics"]["totalVolumeUsd"] > 0.0


def test_client_hop_library():
    client = MultiHopperClient()
    hops = client.get_hop_library()
    assert len(hops) >= 4
    for h in hops:
        assert "hopId" in h
        assert "wallet" in h
        assert "avgDelaySeconds" in h
