from datetime import datetime
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Currency = Literal["USD", "EUR", "RUB", "USDT", "USDC", "AR"]
AdSide = Literal["BUY", "SELL"]
AdStatus = Literal["ACTIVE", "REVOKED", "HIDDEN", "EXPIRED", "COMPLETED"]
PaymentMethod = Literal["CASH", "TRANSFER", "CRYPTO"]

DecimalAmount = Decimal
ALLOWED_PAYMENT_METHODS: tuple[PaymentMethod, ...] = ("CASH", "TRANSFER", "CRYPTO")


class AuthorResponse(BaseModel):
    id: int
    username: str | None


class AdCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_currency: Currency
    quote_currency: Currency
    amount: DecimalAmount = Field(gt=0, max_digits=18, decimal_places=8)
    payment_method: str = Field(min_length=1, max_length=120)
    location: str | None = Field(default=None, max_length=120)

    @field_validator("payment_method", mode="before")
    @classmethod
    def normalize_required_payment_methods(cls, value: object) -> str:
        return _normalize_payment_methods(value)

    @field_validator("location")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def validate_create(self) -> Self:
        _validate_currency_pair(self.base_currency, self.quote_currency)
        _validate_cash_location(self.payment_method, self.location)
        return self


class AdUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: DecimalAmount | None = Field(default=None, gt=0, max_digits=18, decimal_places=8)
    payment_method: str | None = Field(default=None, min_length=1, max_length=120)
    location: str | None = Field(default=None, max_length=120)
    expires_at: datetime | None = None

    @field_validator("payment_method", mode="before")
    @classmethod
    def normalize_optional_payment_methods(cls, value: object) -> str | None:
        if value is None:
            return None
        return _normalize_payment_methods(value)

    @field_validator("location")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("expires_at")
    @classmethod
    def validate_expires_at_is_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("expires_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_non_nullable_fields(self) -> Self:
        for field_name in ("amount", "expires_at"):
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
    message: str


def _validate_currency_pair(base_currency: str, quote_currency: str) -> None:
    if base_currency == quote_currency:
        raise ValueError("base_currency and quote_currency must differ")


def _validate_cash_location(payment_method: str, location: str | None) -> None:
    if payment_method_has_cash(payment_method) and not location:
        raise ValueError("location is required for cash payment method")


def payment_method_has_cash(payment_method: str | None) -> bool:
    if payment_method is None:
        return False
    return "CASH" in _split_payment_methods(payment_method)


def _normalize_payment_methods(value: object) -> str:
    if isinstance(value, str):
        raw_methods = value.split(",")
    elif isinstance(value, list):
        raw_methods = value
    else:
        raise ValueError("payment_method must be a string or list")

    methods: list[str] = []
    seen: set[str] = set()
    for raw_method in raw_methods:
        if not isinstance(raw_method, str):
            raise ValueError("payment_method values must be strings")
        method = raw_method.strip().upper()
        if not method:
            continue
        if method not in ALLOWED_PAYMENT_METHODS:
            raise ValueError("payment_method must contain only CASH, TRANSFER, CRYPTO")
        if method not in seen:
            methods.append(method)
            seen.add(method)

    if not methods:
        raise ValueError("payment_method cannot be empty")
    return ",".join(methods)


def _split_payment_methods(payment_method: str) -> set[str]:
    return {method.strip().upper() for method in payment_method.split(",") if method.strip()}


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
