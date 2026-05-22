from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ReportReason = Literal[
    "SCAM",
    "SPAM",
    "WRONG_RATE",
    "OFFENSIVE",
    "DUPLICATE",
    "FAKE_CONTACT",
    "OTHER",
]
ReportStatus = Literal["NEW", "IN_REVIEW", "RESOLVED", "REJECTED"]


class ReportCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ad_id: int | None = None
    target_user_id: int
    reason: ReportReason
    comment: str | None = Field(default=None, max_length=500)


class ReportResponse(BaseModel):
    id: int
    status: ReportStatus
