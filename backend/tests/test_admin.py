import json
from decimal import Decimal

from sqlalchemy import select

from app.core.time import utc_now
from app.db.models import Ad, AuditLog, Report, User


def make_user(
    *,
    telegram_id: int,
    username: str,
    is_admin: bool = False,
    is_banned: bool = False,
) -> User:
    now = utc_now()
    return User(
        telegram_id=telegram_id,
        username=username,
        is_admin=is_admin,
        is_banned=is_banned,
        first_seen_at=now,
        last_seen_at=now,
        created_at=now,
        updated_at=now,
    )


async def seed_ad(test_session, *, user: User, status: str = "ACTIVE") -> Ad:
    now = utc_now()
    ad = Ad(
        user_id=user.id,
        side="SELL",
        base_currency="USD",
        quote_currency="RUB",
        amount=Decimal("100.00"),
        rate=Decimal("92.50"),
        status=status,
        report_count=0,
        expires_at=now.replace(year=now.year + 1),
        hidden_at=now if status == "HIDDEN" else None,
        created_at=now,
        updated_at=now,
    )
    test_session.add(ad)
    await test_session.flush()
    return ad


async def seed_report(
    test_session,
    *,
    reporter: User,
    target: User,
    ad: Ad | None = None,
    status: str = "NEW",
) -> Report:
    now = utc_now()
    report = Report(
        reporter_user_id=reporter.id,
        target_user_id=target.id,
        ad_id=ad.id if ad is not None else None,
        reason="SCAM",
        comment="looks bad",
        status=status,
        created_at=now,
        updated_at=now,
    )
    test_session.add(report)
    await test_session.flush()
    return report


async def test_admin_endpoints_reject_non_admin(client, authenticate) -> None:
    await authenticate(client, telegram_id=7001, username="regular")

    response = await client.get("/api/admin/dashboard")

    assert response.status_code == 403
    assert response.json()["message"] == "admin access required"


async def test_admin_dashboard_returns_moderation_counts(
    client,
    authenticate,
    test_session,
) -> None:
    active_author = make_user(telegram_id=7011, username="active")
    hidden_author = make_user(telegram_id=7012, username="hidden", is_banned=True)
    reporter = make_user(telegram_id=7013, username="reporter")
    test_session.add_all([active_author, hidden_author, reporter])
    await test_session.flush()
    active_ad = await seed_ad(test_session, user=active_author, status="ACTIVE")
    await seed_ad(test_session, user=hidden_author, status="HIDDEN")
    await seed_report(test_session, reporter=reporter, target=active_author, ad=active_ad)
    await test_session.commit()
    await authenticate(client, telegram_id=123, username="admin")

    response = await client.get("/api/admin/dashboard")

    assert response.status_code == 200
    assert response.json() == {
        "users_total": 4,
        "users_banned": 1,
        "ads_active": 1,
        "ads_hidden": 1,
        "reports_new": 1,
    }


async def test_admin_can_list_reports_without_exposing_telegram_ids(
    client,
    authenticate,
    test_session,
) -> None:
    reporter = make_user(telegram_id=7021, username="reporter")
    target = make_user(telegram_id=7022, username="target")
    test_session.add_all([reporter, target])
    await test_session.flush()
    ad = await seed_ad(test_session, user=target)
    report = await seed_report(test_session, reporter=reporter, target=target, ad=ad)
    await test_session.commit()
    await authenticate(client, telegram_id=123, username="admin")

    response = await client.get("/api/admin/reports")

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"] == {"limit": 50, "offset": 0, "total": 1}
    item = body["items"][0]
    assert item["id"] == report.id
    assert item["reporter"] == {"id": reporter.id, "username": "reporter"}
    assert item["target"] == {"id": target.id, "username": "target"}
    assert "telegram_id" not in json.dumps(item)


async def test_admin_can_update_report_status_and_audit_change(
    client,
    authenticate,
    test_session,
) -> None:
    reporter = make_user(telegram_id=7031, username="reporter")
    target = make_user(telegram_id=7032, username="target")
    test_session.add_all([reporter, target])
    await test_session.flush()
    report = await seed_report(test_session, reporter=reporter, target=target)
    await test_session.commit()
    csrf_token = await authenticate(client, telegram_id=123, username="admin")

    response = await client.patch(
        f"/api/admin/reports/{report.id}",
        json={"status": "RESOLVED"},
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "RESOLVED"
    await test_session.refresh(report)
    admin = (await test_session.execute(select(User).where(User.telegram_id == 123))).scalar_one()
    assert report.status == "RESOLVED"
    assert report.resolved_by_user_id == admin.id
    assert report.resolved_at is not None
    audit = (await test_session.execute(select(AuditLog))).scalar_one()
    assert audit.actor_user_id == admin.id
    assert audit.action == "update_report"
    assert audit.entity_type == "report"
    assert audit.entity_id == report.id


async def test_admin_mutations_require_csrf(client, authenticate, test_session) -> None:
    target = make_user(telegram_id=7041, username="target")
    test_session.add(target)
    await test_session.commit()
    await authenticate(client, telegram_id=123, username="admin")

    response = await client.post(f"/api/admin/users/{target.id}/ban", json={"reason": "spam"})

    assert response.status_code == 403
    assert response.json()["message"] == "invalid csrf token"


async def test_admin_can_ban_and_unban_user_with_audit_log(
    client,
    authenticate,
    test_session,
) -> None:
    target = make_user(telegram_id=7051, username="target")
    test_session.add(target)
    await test_session.commit()
    csrf_token = await authenticate(client, telegram_id=123, username="admin")

    ban_response = await client.post(
        f"/api/admin/users/{target.id}/ban",
        json={"reason": "spam"},
        headers={"X-CSRF-Token": csrf_token},
    )
    unban_response = await client.post(
        f"/api/admin/users/{target.id}/unban",
        headers={"X-CSRF-Token": csrf_token},
    )

    assert ban_response.status_code == 200
    assert ban_response.json()["is_banned"] is True
    assert unban_response.status_code == 200
    assert unban_response.json()["is_banned"] is False
    await test_session.refresh(target)
    assert target.is_banned is False
    assert target.banned_reason is None
    audit_actions = [
        entry.action
        for entry in (await test_session.execute(select(AuditLog).order_by(AuditLog.id)))
        .scalars()
        .all()
    ]
    assert audit_actions == ["ban_user", "unban_user"]


async def test_admin_can_hide_and_restore_ad_with_audit_log(
    client,
    authenticate,
    test_session,
) -> None:
    author = make_user(telegram_id=7061, username="author")
    test_session.add(author)
    await test_session.flush()
    ad = await seed_ad(test_session, user=author)
    await test_session.commit()
    csrf_token = await authenticate(client, telegram_id=123, username="admin")

    hide_response = await client.post(
        f"/api/admin/ads/{ad.id}/hide",
        headers={"X-CSRF-Token": csrf_token},
    )
    restore_response = await client.post(
        f"/api/admin/ads/{ad.id}/restore",
        headers={"X-CSRF-Token": csrf_token},
    )
    audit_response = await client.get("/api/admin/audit-log")

    assert hide_response.status_code == 200
    assert hide_response.json()["status"] == "HIDDEN"
    assert restore_response.status_code == 200
    assert restore_response.json()["status"] == "ACTIVE"
    await test_session.refresh(ad)
    assert ad.status == "ACTIVE"
    assert ad.hidden_at is None
    audit_actions = [item["action"] for item in audit_response.json()["items"]]
    assert audit_actions == ["restore_ad", "hide_ad"]
