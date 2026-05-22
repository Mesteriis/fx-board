from dataclasses import dataclass
from typing import Literal

DealAnswer = Literal["yes", "no"]


@dataclass(frozen=True)
class DealCallback:
    contact_attempt_id: int
    answer: DealAnswer


def encode_deal_callback(*, contact_attempt_id: int, answer: DealAnswer) -> str:
    if contact_attempt_id < 1:
        raise ValueError("invalid deal callback")
    if answer not in {"yes", "no"}:
        raise ValueError("invalid deal callback")
    return f"deal:{contact_attempt_id}:{answer}"


def decode_deal_callback(value: str) -> DealCallback:
    parts = value.split(":")
    if len(parts) != 3:
        raise ValueError("invalid deal callback")

    prefix, raw_id, answer = parts
    if prefix != "deal" or answer not in {"yes", "no"}:
        raise ValueError("invalid deal callback")

    try:
        contact_attempt_id = int(raw_id)
    except ValueError as exc:
        raise ValueError("invalid deal callback") from exc

    if contact_attempt_id < 1:
        raise ValueError("invalid deal callback")
    return DealCallback(contact_attempt_id=contact_attempt_id, answer=answer)
