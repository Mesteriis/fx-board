from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError
from app.db.models import User
from app.db.session import get_session
from app.schemas.admin import (
    AdminAdResponse,
    AdminAuditLogResponse,
    AdminBanUserRequest,
    AdminDashboardResponse,
    AdminReportListResponse,
    AdminReportResponse,
    AdminReportUpdateRequest,
    AdminUserResponse,
)
from app.services import admin as admin_service
from app.services import reports as reports_service
from app.services.auth import require_csrf, require_current_user

router = APIRouter(prefix="/api/admin", tags=["admin"])


async def require_admin_user(
    user: Annotated[User, Depends(require_current_user)],
) -> User:
    if not user.is_admin:
        raise ForbiddenError("admin access required")
    return user


async def require_admin_mutation(
    _csrf: Annotated[None, Depends(require_csrf)],
    user: Annotated[User, Depends(require_admin_user)],
) -> User:
    return user


@router.get("/reports", response_model=AdminReportListResponse)
async def list_reports(
    db: Annotated[AsyncSession, Depends(get_session)],
    _admin: Annotated[User, Depends(require_admin_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminReportListResponse:
    return await reports_service.list_reports(db, limit=limit, offset=offset)


@router.patch("/reports/{report_id}", response_model=AdminReportResponse)
async def update_report(
    report_id: int,
    payload: AdminReportUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(require_admin_mutation)],
) -> AdminReportResponse:
    response = await reports_service.update_report_status(
        db,
        report_id=report_id,
        payload=payload,
        actor=admin,
    )
    await db.commit()
    return response


@router.post("/users/{user_id}/ban", response_model=AdminUserResponse)
async def ban_user(
    user_id: int,
    payload: AdminBanUserRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(require_admin_mutation)],
) -> AdminUserResponse:
    response = await admin_service.ban_user(db, user_id=user_id, payload=payload, actor=admin)
    await db.commit()
    return response


@router.post("/users/{user_id}/unban", response_model=AdminUserResponse)
async def unban_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(require_admin_mutation)],
) -> AdminUserResponse:
    response = await admin_service.unban_user(db, user_id=user_id, actor=admin)
    await db.commit()
    return response


@router.post("/ads/{ad_id}/hide", response_model=AdminAdResponse)
async def hide_ad(
    ad_id: int,
    db: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(require_admin_mutation)],
) -> AdminAdResponse:
    response = await admin_service.hide_ad(db, ad_id=ad_id, actor=admin)
    await db.commit()
    return response


@router.post("/ads/{ad_id}/restore", response_model=AdminAdResponse)
async def restore_ad(
    ad_id: int,
    db: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(require_admin_mutation)],
) -> AdminAdResponse:
    response = await admin_service.restore_ad(db, ad_id=ad_id, actor=admin)
    await db.commit()
    return response


@router.get("/dashboard", response_model=AdminDashboardResponse)
async def dashboard(
    db: Annotated[AsyncSession, Depends(get_session)],
    _admin: Annotated[User, Depends(require_admin_user)],
) -> AdminDashboardResponse:
    return await admin_service.get_dashboard(db)


@router.get("/audit-log", response_model=AdminAuditLogResponse)
async def audit_log(
    db: Annotated[AsyncSession, Depends(get_session)],
    _admin: Annotated[User, Depends(require_admin_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminAuditLogResponse:
    return await admin_service.list_audit_log(db, limit=limit, offset=offset)
