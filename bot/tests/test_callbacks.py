import pytest

from fx_board_bot.callbacks import decode_deal_callback, encode_deal_callback


def test_deal_callback_round_trip() -> None:
    encoded = encode_deal_callback(contact_attempt_id=55, answer="yes")

    decoded = decode_deal_callback(encoded)

    assert encoded == "deal:55:yes"
    assert decoded.contact_attempt_id == 55
    assert decoded.answer == "yes"


@pytest.mark.parametrize("value", ["deal:55:maybe", "other:55:yes", "deal:not-int:yes", "deal:"])
def test_deal_callback_rejects_invalid_payloads(value: str) -> None:
    with pytest.raises(ValueError, match="invalid deal callback"):
        decode_deal_callback(value)
