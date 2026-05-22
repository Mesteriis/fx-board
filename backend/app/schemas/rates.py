from pydantic import BaseModel


class RateItem(BaseModel):
    pair: str
    rate: str


class RatesResponse(BaseModel):
    date: str
    source: str
    is_stale: bool
    updated_at: str
    rates: list[RateItem]
