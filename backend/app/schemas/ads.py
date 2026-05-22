from datetime import datetime
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Currency = Literal["USD", "EUR", "RUB", "USDT", "USDC"]
AdSide = Literal["BUY", "SELL"]
AdStatus = Literal["ACTIVE", "REVOKED", "HIDDEN", "EXPIRED", "COMPLETED"]

DecimalAmount = Decimal


class AuthorResponse(BaseModel):
    id: int
    username: str | None


class AdCreateRequest(BaseModel):
    side: AdSide
    base_currency: Currency
    quote_currency: Currency
    amount: DecimalAmount = Field(gt=0, max_digits=18, decimal_places=8)
    min_amount: DecimalAmount | None = Field(default=None, gt=0, max_digits=18, decimal_places=8)
    max_amount: DecimalAmount | None = Field(default=None, gt=0, max_digits=18, decimal_places=8)
    rate: DecimalAmount = Field(gt=0, max_digits=18, decimal_places=8)
    payment_method: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=120)
    comment: str | None = Field(default=None, max_length=500)
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def validate_expires_at_is_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("expires_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_create_limits(self) -> Self:
        _validate_currency_pair(self.base_currency, self.quote_currency)
        _validate_amount_limits(
            amount=self.amount,
            min_amount=self.min_amount,
            max_amount=self.max_amount,
        )
        return self


class AdUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: DecimalAmount | None = Field(default=None, gt=0, max_digits=18, decimal_places=8)
    min_amount: DecimalAmount | None = Field(default=None, gt=0, max_digits=18, decimal_places=8)
    max_amount: DecimalAmount | None = Field(default=None, gt=0, max_digits=18, decimal_places=8)
    rate: DecimalAmount | None = Field(default=None, gt=0, max_digits=18, decimal_places=8)
    payment_method: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=120)
    comment: str | None = Field(default=None, max_length=500)
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def validate_expires_at_is_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("expires_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_non_nullable_fields(self) -> Self:
        for field_name in ("amount", "rate", "expires_at"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self


class AdListItemResponse(BaseModel):
    id: int
    side: AdSide
    base_currency: Currency
    quote_currency: Currency
    amount: Decimal
    min_amount: Decimal | None
    max_amount: Decimal | None
    rate: Decimal
    payment_method: str | None
    location: str | None
    comment: str | None
    status: AdStatus
    expires_at: datetime
    created_at: datetime
    updated_at: datetime


class AdDetailResponse(AdListItemResponse):
    author: AuthorResponse
    revoked_at: datetime | None
    hidden_at: datetime | None
    completed_at: datetime | None


class PaginationResponse(BaseModel):
    limit: int
    offset: int
    total: int


class AdsBySideResponse(BaseModel):
    sell: list[AdListItemResponse]
    buy: list[AdListItemResponse]
    pagination: PaginationResponse


class MyAdsResponse(BaseModel):
    items: list[AdDetailResponse]
    pagination: PaginationResponse


class ContactAttemptResponse(BaseModel):
    contact_attempt_id: int
    telegram_url: str


def _validate_currency_pair(base_currency: str, quote_currency: str) -> None:
    if base_currency == quote_currency:
        raise ValueError("base_currency and quote_currency must differ")


def _validate_amount_limits(
    *,
    amount: Decimal,
    min_amount: Decimal | None,
    max_amount: Decimal | None,
) -> None:
    if min_amount is not None and min_amount > amount:
        raise ValueError("min_amount cannot exceed amount")
    if max_amount is not None and max_amount > amount:
        raise ValueError("max_amount cannot exceed amount")
    if min_amount is not None and max_amount is not None and min_amount > max_amount:
        raise ValueError("min_amount cannot exceed max_amount")
