import pytest
from src.solana.tx_builder import (
    SolanaTransactionBuilder,
    Instruction,
    AccountMeta,
    encode_compact_u16,
    find_program_address
)
from src.multihopper.config import PROGRAM_IDS


def test_compact_u16_encoding():
    assert encode_compact_u16(0) == bytes([0])
    assert encode_compact_u16(1) == bytes([1])
    assert encode_compact_u16(127) == bytes([127])
    assert encode_compact_u16(128) == bytes([0x80, 0x01])
    assert encode_compact_u16(255) == bytes([0xFF, 0x01])


def test_pda_derivation():
    # Derive PDA for vault authority
    route_id_bytes = (12345678).to_bytes(8, byteorder='little')
    pda, nonce = find_program_address([b"route", route_id_bytes], PROGRAM_IDS["MULTI_HOPPER_CORE"])
    assert isinstance(pda, str)
    assert len(pda) >= 32
    assert 0 <= nonce <= 255


def test_solana_transaction_builder_message_structure():
    payer = "6mghraUR9NV2fA187VXoLN2rVS3WLA91UhqLfjtvDdmf"
    blockhash = "5eykt4UsFv8P8NJdTREpY1vzqKqZKvdpKuc147dw2N9d"

    ix1 = Instruction(
        program_id=PROGRAM_IDS["MULTI_HOPPER_CORE"],
        keys=[
            AccountMeta(pubkey=payer, is_signer=True, is_writable=True),
            AccountMeta(pubkey="H4iZ7C2Z1rXgQ2Xy9J4K6M3P8T9W1V5L2B8N4M7K9L2P", is_signer=False, is_writable=True),
        ],
        data=b"\x01\x00\x00\x00InitVaultInstruction"
    )

    tx = SolanaTransactionBuilder.build_transaction(
        fee_payer=payer,
        recent_blockhash=blockhash,
        instructions=[ix1]
    )

    assert tx["feePayer"] == payer
    assert tx["numSignatures"] >= 1
    assert len(tx["serializedBase64"]) > 0
    assert len(tx["serializedBase58"]) > 0
    assert tx["recentBlockhash"] == blockhash
