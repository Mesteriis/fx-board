from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.ads import AdDetailResponse, PaginationResponse
from app.schemas.reports import ReportReason, ReportStatus


class AdminUserSummaryResponse(BaseModel):
    id: int
    username: str | None


class AdminUserResponse(BaseModel):
    id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    is_admin: bool
    is_banned: bool
    banned_reason: str | None


class AdminReportResponse(BaseModel):
    id: int
    reporter: AdminUserSummaryResponse
    target: AdminUserSummaryResponse
    ad_id: int | None
    reason: ReportReason
    comment: str | None
    status: ReportStatus
    resolved_by_user_id: int | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AdminReportListResponse(BaseModel):
    items: list[AdminReportResponse]
    pagination: PaginationResponse


class AdminReportUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ReportStatus


class AdminBanUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=500)


class AdminDashboardResponse(BaseModel):
    users_total: int
    users_banned: int
    ads_active: int
    ads_hidden: int
    reports_new: int


class AdminAuditLogItemResponse(BaseModel):
    id: int
    actor_user_id: int | None
    action: str
    entity_type: str
    entity_id: int | None
    payload: dict[str, object] | None
    ip_hash: str | None
    created_at: datetime


class AdminAuditLogResponse(BaseModel):
    items: list[AdminAuditLogItemResponse]
    pagination: PaginationResponse


AdminAdResponse = AdDetailResponse
