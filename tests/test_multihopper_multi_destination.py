import pytest
from src.multihopper.client import MultiHopperClient


def test_multi_destination_limit_and_distribution():
    client = MultiHopperClient()

    # Up to 20 destinations supported
    destinations = [
        {"wallet": f"wallet_{i+1:02d}", "share": 1.0}
        for i in range(15)
    ]

    created = client.create_transfer(
        token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        amount_tokens=1500.0,
        source_owner="6mghraUR9NV2fA187VXoLN2rVS3WLA91UhqLfjtvDdmf",
        destinations=destinations
    )
    assert created["status"] == "quote"
    assert len(created["destinations"]) == 15

    # Exceeding 20 destinations must raise error
    with pytest.raises(ValueError):
        too_many = [{"wallet": f"w_{i}", "share": 1.0} for i in range(21)]
        client.estimate_transfer(
            token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            amount_tokens=2100.0,
            source_owner="6mghraUR9NV2fA187VXoLN2rVS3WLA91UhqLfjtvDdmf",
            destinations=too_many
        )


def test_mutual_exclusivity_destination_vs_recipient():
    client = MultiHopperClient()
    # Providing BOTH recipientWallet and destinations must fail
    with pytest.raises(ValueError):
        client.create_transfer(
            token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            amount_tokens=100.0,
            source_owner="6mghraUR9NV2fA187VXoLN2rVS3WLA91UhqLfjtvDdmf",
            recipient_wallet="recip_wallet_1",
            destinations=[{"wallet": "dest_1", "share": 1.0}]
        )
