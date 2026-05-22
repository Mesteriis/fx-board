import logging

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.errors import AppError
from app.core.time import utc_now
from app.db.models import Ad, Report, User
from app.db.transactions import begin_sqlite_immediate
from app.schemas.admin import (
    AdminReportListResponse,
    AdminReportResponse,
    AdminReportUpdateRequest,
    AdminUserSummaryResponse,
)
from app.schemas.ads import PaginationResponse
from app.schemas.reports import ReportCreateRequest, ReportResponse
from app.services.ads import ACTIVE, NotFoundError
from app.services.audit import write_audit
from app.telegram.notifications import (
    NotificationSink,
    get_notification_sink,
    notify_admin_auto_hide_ad,
)

logger = logging.getLogger(__name__)


async def create_report(
    db: AsyncSession,
    *,
    reporter_user_id: int,
    payload: ReportCreateRequest,
    auto_hide_threshold: int,
    notification_sink: NotificationSink | None = None,
) -> Report:
    await begin_sqlite_immediate(db)
    if reporter_user_id == payload.target_user_id:
        raise AppError("cannot report yourself")

    ad: Ad | None = None
    if payload.ad_id is not None:
        ad = await db.get(Ad, payload.ad_id)
        if ad is None:
            raise NotFoundError("ad not found")
        if ad.user_id != payload.target_user_id:
            raise AppError("target_user_id does not match ad author")
        existing_report = await db.scalar(
            select(Report).where(
                Report.reporter_user_id == reporter_user_id,
                Report.ad_id == payload.ad_id,
            )
        )
        if existing_report is not None:
            raise AppError("ad already reported")
    else:
        target_user = await db.get(User, payload.target_user_id)
        if target_user is None:
            raise NotFoundError("target user not found")

    now = utc_now()
    report = Report(
        reporter_user_id=reporter_user_id,
        target_user_id=payload.target_user_id,
        ad_id=payload.ad_id,
        reason=payload.reason,
        comment=payload.comment,
        status="NEW",
        created_at=now,
        updated_at=now,
    )
    db.add(report)
    try:
        await db.flush()
    except IntegrityError as exc:
        if payload.ad_id is not None:
            raise AppError("ad already reported") from exc
        raise

    auto_hide_notification: tuple[int, int] | None = None
    if ad is not None:
        unique_count = await db.scalar(
            select(func.count(func.distinct(Report.reporter_user_id))).where(
                Report.ad_id == payload.ad_id
            )
        )
        ad.report_count = int(unique_count or 0)
        if ad.status == ACTIVE and ad.report_count >= auto_hide_threshold:
            ad.status = "HIDDEN"
            ad.hidden_at = now
            ad.updated_at = now
            await write_audit(
                db,
                actor_user_id=None,
                action="auto_hide_ad",
                entity_type="ad",
                entity_id=ad.id,
                payload={"report_count": ad.report_count},
            )
            auto_hide_notification = (ad.id, ad.report_count)
        await db.flush()
        if auto_hide_notification is not None:
            await _notify_auto_hide_ad(
                notification_sink,
                ad_id=auto_hide_notification[0],
                report_count=auto_hide_notification[1],
            )

    return report


def report_response(report: Report) -> ReportResponse:
    return ReportResponse(id=report.id, status=report.status)  # type: ignore[arg-type]


async def list_reports(
    db: AsyncSession,
    *,
    limit: int,
    offset: int,
) -> AdminReportListResponse:
    reporter = aliased(User)
    target = aliased(User)
    total = (await db.execute(select(func.count()).select_from(Report))).scalar_one()
    result = await db.execute(
        select(Report, reporter, target)
        .join(reporter, reporter.id == Report.reporter_user_id)
        .join(target, target.id == Report.target_user_id)
        .order_by(Report.created_at.desc(), Report.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return AdminReportListResponse(
        items=[
            admin_report_response(report, reporter_user, target_user)
            for report, reporter_user, target_user in result.all()
        ],
        pagination=PaginationResponse(limit=limit, offset=offset, total=total),
    )


async def update_report_status(
    db: AsyncSession,
    *,
    report_id: int,
    payload: AdminReportUpdateRequest,
    actor: User,
) -> AdminReportResponse:
    report = await db.get(Report, report_id)
    if report is None:
        raise NotFoundError("report not found")

    old_status = report.status
    now = utc_now()
    report.status = payload.status
    report.updated_at = now
    if payload.status in {"RESOLVED", "REJECTED"}:
        report.resolved_by_user_id = actor.id
        report.resolved_at = now
    else:
        report.resolved_by_user_id = None
        report.resolved_at = None

    await write_audit(
        db,
        actor_user_id=actor.id,
        action="update_report",
        entity_type="report",
        entity_id=report.id,
        payload={"old_status": old_status, "new_status": payload.status},
    )
    await db.flush()
    return await get_admin_report(db, report_id=report.id)


async def get_admin_report(db: AsyncSession, *, report_id: int) -> AdminReportResponse:
    reporter = aliased(User)
    target = aliased(User)
    result = await db.execute(
        select(Report, reporter, target)
        .join(reporter, reporter.id == Report.reporter_user_id)
        .join(target, target.id == Report.target_user_id)
        .where(Report.id == report_id)
    )
    row = result.one_or_none()
    if row is None:
        raise NotFoundError("report not found")
    report, reporter_user, target_user = row
    return admin_report_response(report, reporter_user, target_user)


def admin_report_response(
    report: Report,
    reporter_user: User,
    target_user: User,
) -> AdminReportResponse:
    return AdminReportResponse(
        id=report.id,
        reporter=AdminUserSummaryResponse(id=reporter_user.id, username=reporter_user.username),
        target=AdminUserSummaryResponse(id=target_user.id, username=target_user.username),
        ad_id=report.ad_id,
        reason=report.reason,  # type: ignore[arg-type]
        comment=report.comment,
        status=report.status,  # type: ignore[arg-type]
        resolved_by_user_id=report.resolved_by_user_id,
        resolved_at=report.resolved_at,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


async def _notify_auto_hide_ad(
    notification_sink: NotificationSink | None,
    *,
    ad_id: int,
    report_count: int,
) -> None:
    sink = notification_sink or get_notification_sink()
    try:
        await notify_admin_auto_hide_ad(sink, ad_id=ad_id, report_count=report_count)
    except Exception:
        logger.exception("failed to record auto-hide admin notification intent")
