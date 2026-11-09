import json
from datetime import date, timedelta
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Max, Sum
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
import json
import uuid
from datetime import timedelta

from .forms import RegisterForm, StrategyForm, DailyReportForm, TeamLeaderCreateForm
from .models import (
    MemberProfile, TeamMember, Strategy, DailyReport, Country, City, Niche, OutreachMethod,
    ToolIntegrationConfig, ToolAccessPermission, ToolAccessSession, ToolAccessLog,
)
from .crypto import decrypt_value, encrypt_value
from .pakseo import pakseo_login, serialize_cookies, deserialize_cookies


def _is_admin(user):
    return user.is_authenticated and user.is_staff


def _is_leader(user):
    profile = getattr(user, "profile", None)
    return bool(profile and profile.is_leader and profile.status == "active")


PERFORMANCE_FIELDS = {
    "emails": "emails_sent",
    "messages": "messages_sent",
    "calls": "calls_made",
    "replies": "replies_received",
    "interested": "interested_leads",
    "meetings": "meetings_booked",
    "deals": "deals_closed",
    "followups": "followups",
}


def _performance_totals(queryset):
    return queryset.aggregate(**{key: Sum(field) for key, field in PERFORMANCE_FIELDS.items()})


def _ensure_profile(user):
    if user.is_authenticated and not user.is_staff:
        MemberProfile.objects.get_or_create(user=user)


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _log_tool_action(user, action, status="", session=None, details="", request=None):
    ToolAccessLog.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        session=session,
        action=action,
        status=status,
        ip_address=_client_ip(request) if request is not None else None,
        details=details,
    )


def _member_profile_ok(request):
    if request.user.is_staff:
        return True
    _ensure_profile(request.user)
    profile = request.user.profile
    if profile.status != "active":
        return False
    return True


def _tool_permission_for(user):
    try:
        return user.tool_access_permission
    except ToolAccessPermission.DoesNotExist:
        return None


def _active_tool_session(user):
    session = ToolAccessSession.objects.filter(user=user, status="active").order_by("-started_at").first()
    if session is None:
        return None
    if session.is_expired:
        session.mark_ended("expired")
        _log_tool_action(user, "session_ended", status="expired", session=session)
        return None
    return session


def _terminate_user_tool_sessions(user, status="revoked"):
    for session in ToolAccessSession.objects.filter(user=user, status="active"):
        session.mark_ended(status)
        _log_tool_action(user, "session_revoked", status=status, session=session)


@require_GET
def health_check(request):
    return JsonResponse({"status": "ok"})


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        with transaction.atomic():
            user = User.objects.create_user(
                username=data["username"],
                email=data["email"],
                password=data["password1"],
                first_name=data["first_name"],
                last_name=data.get("last_name", ""),
                is_active=True,
            )
            MemberProfile.objects.create(
                user=user,
                whatsapp=data["whatsapp"],
                qualification=data.get("qualification", ""),
                skills=data.get("skills", ""),
                experience=data.get("experience", ""),
                status="pending",
                role="member",
                referred_by=data.get("referred_by"),
            )
        leader = data.get("referred_by")
        message = "Account created. Your account is pending admin approval."
        if leader:
            message += f" Team leader reference: {leader.get_full_name() or leader.username}."
        messages.success(request, message)
        return redirect("login")
    return render(request, "portal/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    error = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            remember = request.POST.get("remember") == "on"
            if user.is_staff:
                login(request, user)
                # Keep staff sessions short unless "remember me" is chosen.
                request.session.set_expiry(60 * 60 * 24 * 30 if remember else 0)
                return redirect("admin_panel")
            _ensure_profile(user)
            if user.profile.status != "active":
                error = "Your account is pending approval or has been suspended. Contact the admin."
            else:
                login(request, user)
                request.session.set_expiry(60 * 60 * 24 * 30 if remember else 0)
                if user.profile.is_leader:
                    return redirect("leader_dashboard")
                return redirect("dashboard")
        else:
            error = "Invalid username or password."
    return render(request, "portal/login.html", {"error": error})


def home(request):
    return render(request, "portal/home.html")


def our_team(request):
    team_members = TeamMember.objects.filter(is_active=True).order_by("sort_order", "name")
    return render(request, "portal/our_team.html", {"team_members": team_members})


def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def dashboard(request):
    if request.user.is_staff:
        return redirect("admin_panel")
    _ensure_profile(request.user)
    profile = request.user.profile
    if profile.status != "active":
        logout(request)
        messages.warning(request, "Your account is not active yet. Please contact the admin.")
        return redirect("login")

    today = timezone.localdate()
    report = DailyReport.objects.filter(member=request.user, report_date=today).first()
    report_form = DailyReportForm(instance=report, initial={"report_date": today})
    strategy_form = StrategyForm()
    config = ToolIntegrationConfig.get_solo()
    permission = _tool_permission_for(request.user)
    tool_access_enabled = bool(config.integration_ready and permission and permission.enabled)
    tool_access_message = ""
    if not config.integration_ready:
        tool_access_message = "Tool integration is not configured by the admin."
    elif not permission or not permission.enabled:
        tool_access_message = "Request access from an admin to use PakSEOtools."
    context = {
        "profile": profile,
        "is_leader": profile.is_leader,
        "team_size": profile.team_size,
        "strategy_form": strategy_form,
        "report_form": report_form,
        "strategies": Strategy.objects.filter(member=request.user).select_related(
            "country", "city", "niche__parent__parent", "method"
        ),
        "reports": DailyReport.objects.filter(member=request.user)[:14],
        "countries": Country.objects.annotate(city_count=Count("cities")).order_by("name"),
        "main_niches": Niche.objects.filter(parent__isnull=True).annotate(
            sub_count=Count("children")
        ).order_by("name"),
        "total_cities": City.objects.count(),
        "total_niches": Niche.objects.count(),
        "method_notes_json": json.dumps({m.id: m.approach_note for m in OutreachMethod.objects.all()}),
        "tool_access_enabled": tool_access_enabled,
        "tool_access_message": tool_access_message,
    }
    return render(request, "portal/dashboard.html", context)


@login_required
@require_POST
def add_strategy(request):
    if request.user.is_staff:
        return redirect("admin_panel")
    _ensure_profile(request.user)
    if request.user.profile.status != "active":
        return HttpResponseForbidden("Account is not active.")
    form = StrategyForm(request.POST)
    if form.is_valid():
        strategy = form.save(commit=False)
        strategy.member = request.user
        try:
            strategy.full_clean()
            strategy.save()
            messages.success(request, "Strategy saved.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
    else:
        messages.error(request, "Please check the strategy form and select a valid country and city.")
    return redirect("dashboard")


@login_required
@require_POST
def delete_strategy(request, pk):
    strategy = get_object_or_404(Strategy, pk=pk)
    if not request.user.is_staff and strategy.member_id != request.user.id:
        return HttpResponseForbidden("You cannot delete another member's strategy.")
    strategy.delete()
    messages.success(request, "Strategy deleted.")
    return redirect("admin_panel" if request.user.is_staff else "dashboard")


@login_required
@require_POST
def save_report(request):
    if request.user.is_staff:
        return redirect("admin_panel")
    _ensure_profile(request.user)
    if request.user.profile.status != "active":
        return HttpResponseForbidden("Account is not active.")
    existing = DailyReport.objects.filter(member=request.user, report_date=request.POST.get("report_date")).first()
    form = DailyReportForm(request.POST, instance=existing)
    if form.is_valid():
        report_date = form.cleaned_data["report_date"]
        if report_date > timezone.localdate():
            messages.error(request, "Report date cannot be in the future.")
            return redirect("dashboard")
        report = form.save(commit=False)
        report.member = request.user
        report.save()
        messages.success(request, "Daily report saved.")
    else:
        messages.error(request, "Please check the report fields and try again.")
    return redirect("dashboard")


@require_GET
def cities_for_country(request):
    country_id = request.GET.get("country_id")
    try:
        country_id = int(country_id)
    except (TypeError, ValueError):
        return JsonResponse({"cities": []})
    cities = City.objects.filter(country_id=country_id).values("id", "name")
    response = JsonResponse({"cities": list(cities)})
    # Seed data is immutable, so cache aggressively at the edge and in the browser.
    response["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=604800"
    return response


@require_GET
def niches_for_parent(request, parent_id):
    parent = get_object_or_404(Niche, pk=parent_id)
    children = list(parent.children.order_by("name").values("id", "name"))
    response = JsonResponse({"children": children})
    response["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=604800"
    return response


@require_GET
def niche_tree(request, niche_id):
    """Return one niche with every sub-niche and its micro-niches."""
    niche = get_object_or_404(Niche, pk=niche_id)
    children = list(niche.children.order_by("name").values("id", "name"))
    child_ids = [child["id"] for child in children]
    micros = Niche.objects.filter(parent_id__in=child_ids).order_by("name").values("id", "name", "parent_id")
    grouped = {child_id: [] for child_id in child_ids}
    for micro in micros:
        grouped[micro["parent_id"]].append({"id": micro["id"], "name": micro["name"]})
    for child in children:
        child["children"] = grouped.get(child["id"], [])
    response = JsonResponse(
        {
            "niche": {"id": niche.id, "name": niche.name, "parent_id": niche.parent_id},
            "children": children,
        }
    )
    response["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=604800"
    return response


@require_GET
def niche_info(request, niche_id):
    niche = get_object_or_404(Niche, pk=niche_id)
    data = {
        "id": niche.id,
        "name": niche.name,
        "full_path": niche.full_path,
        "keywords": niche.search_keywords,
    }
    response = JsonResponse(data)
    response["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=604800"
    return response


@login_required
@user_passes_test(_is_admin)
def admin_panel(request):
    profiles = (
        MemberProfile.objects.filter(role="member")
        .select_related("user", "referred_by")
        .order_by("status", "user__username")
    )
    leaders = (
        User.objects.filter(profile__role="leader")
        .select_related("profile")
        .annotate(team_count=Count("team_members", distinct=True))
        .order_by("first_name", "last_name", "username")
    )
    reports = DailyReport.objects.select_related("member").all()[:100]
    strategies = Strategy.objects.select_related("member", "country", "city", "niche", "method").all()[:100]
    config = ToolIntegrationConfig.get_solo()
    tool_enabled_count = ToolAccessPermission.objects.filter(enabled=True).count()
    tool_active_sessions = ToolAccessSession.objects.filter(status="active").count()
    context = {
        "profiles": profiles,
        "leaders": leaders,
        "leader_options": leaders.filter(profile__status="active"),
        "reports": reports,
        "strategies": strategies,
        "pending_count": MemberProfile.objects.filter(status="pending", role="member").count(),
        "active_count": MemberProfile.objects.filter(status="active", role="member").count(),
        "leader_count": leaders.count(),
        "report_count": DailyReport.objects.count(),
        "countries_count": Country.objects.count(),
        "cities_count": City.objects.count(),
        "niches_count": Niche.objects.count(),
        "methods_count": OutreachMethod.objects.count(),
        "tool_integration_ready": config.integration_ready,
        "tool_enabled_count": tool_enabled_count,
        "tool_active_sessions": tool_active_sessions,
    }
    return render(request, "portal/admin_panel.html", context)


@login_required
@user_passes_test(_is_admin)
def create_team_leader(request):
    form = TeamLeaderCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        with transaction.atomic():
            user = User.objects.create_user(
                username=data["username"],
                email=data["email"],
                password=data["password1"],
                first_name=data["first_name"],
                last_name=data.get("last_name", ""),
                is_active=True,
            )
            MemberProfile.objects.create(
                user=user,
                whatsapp=data["whatsapp"],
                qualification=data.get("qualification", ""),
                skills=data.get("skills", ""),
                experience=data.get("experience", ""),
                status="active",
                role="leader",
            )
        messages.success(
            request,
            f"Team leader {user.get_full_name() or user.username} created. Share the login details with them.",
        )
        return redirect("admin_panel")
    return render(request, "portal/admin_create_leader.html", {"form": form})


@login_required
@user_passes_test(_is_admin)
@require_POST
def update_member_status(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    if user.is_staff:
        messages.error(request, "Admin accounts cannot be changed from this panel.")
        return redirect("admin_panel")
    profile = get_object_or_404(MemberProfile, user=user)
    status = request.POST.get("status")
    if status not in {"pending", "active", "suspended"}:
        messages.error(request, "Invalid status.")
        return redirect("admin_panel")

    if profile.role == "member":
        leader_id = (request.POST.get("referred_by") or "").strip()
        if leader_id:
            leader = User.objects.filter(
                pk=leader_id, profile__role="leader", profile__status="active"
            ).first()
            if leader is None:
                messages.error(request, "Selected team leader is not active.")
                return redirect("admin_panel")
            profile.referred_by = leader
        else:
            profile.referred_by = None

    profile.status = status
    profile.save(update_fields=["status", "referred_by"])
    messages.success(request, f"{user.username} updated successfully.")
    return redirect("admin_panel")


@login_required
def leader_dashboard(request):
    if request.user.is_staff:
        return redirect("admin_panel")
    profile = getattr(request.user, "profile", None)
    if not profile or not profile.is_leader:
        messages.error(request, "Only team leaders can open the team portal.")
        return redirect("dashboard")
    if profile.status != "active":
        messages.error(request, "Your team leader account is not active.")
        return redirect("login")

    members = (
        User.objects.filter(profile__referred_by=request.user)
        .select_related("profile")
        .annotate(
            report_count=Count("daily_reports", distinct=True),
            last_report=Max("daily_reports__report_date"),
            total_emails=Sum("daily_reports__emails_sent"),
            total_messages=Sum("daily_reports__messages_sent"),
            total_calls=Sum("daily_reports__calls_made"),
            total_replies=Sum("daily_reports__replies_received"),
            total_interested=Sum("daily_reports__interested_leads"),
            total_meetings=Sum("daily_reports__meetings_booked"),
            total_deals=Sum("daily_reports__deals_closed"),
            total_followups=Sum("daily_reports__followups"),
        )
        .order_by("profile__status", "first_name", "last_name", "username")
    )
    team_reports = DailyReport.objects.filter(member__profile__referred_by=request.user)
    totals = _performance_totals(team_reports)
    week_start = timezone.localdate() - timedelta(days=6)
    week_reports = team_reports.filter(report_date__gte=week_start)
    context = {
        "profile": profile,
        "members": members,
        "team_size": members.count(),
        "active_members": members.filter(profile__status="active").count(),
        "pending_members": members.filter(profile__status="pending").count(),
        "week_reports": week_reports.count(),
        "recent_reports": team_reports.select_related("member")[:15],
        "totals": totals,
        "week_totals": _performance_totals(week_reports),
    }
    return render(request, "portal/leader_dashboard.html", context)


@login_required
def leader_member_detail(request, user_id):
    member = get_object_or_404(User.objects.select_related("profile"), pk=user_id)
    profile = getattr(member, "profile", None)

    if not request.user.is_staff:
        requester = getattr(request.user, "profile", None)
        if not requester or not requester.is_leader or requester.status != "active":
            return HttpResponseForbidden("Only active team leaders can view member performance.")
        if not profile or profile.referred_by_id != request.user.id:
            return HttpResponseForbidden("This member is not part of your team.")

    reports = member.daily_reports.all()
    week_start = timezone.localdate() - timedelta(days=6)
    context = {
        "member": member,
        "profile": profile,
        "reports": reports[:30],
        "report_count": reports.count(),
        "strategies": member.strategies.select_related("country", "city", "niche__parent__parent", "method"),
        "totals": _performance_totals(reports),
        "week_totals": _performance_totals(reports.filter(report_date__gte=week_start)),
        "last_report": reports.first(),
        "back_url": "admin_panel" if request.user.is_staff else "leader_dashboard",
    }
    return render(request, "portal/leader_member_detail.html", context)


@login_required
@user_passes_test(_is_admin)
@require_POST
def delete_member(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    if user.is_staff:
        messages.error(request, "Admin accounts cannot be deleted from this panel.")
        return redirect("admin_panel")
    username = user.username
    user.delete()
    messages.success(request, f"Team member '{username}' deleted.")
    return redirect("admin_panel")


# ---------------------------------------------------------------------------
# PakSEOtools secure access management
# ---------------------------------------------------------------------------


@login_required
@user_passes_test(_is_admin)
def admin_tool_access(request):
    config = ToolIntegrationConfig.get_solo()
    permissions = (
        ToolAccessPermission.objects.select_related("user", "granted_by")
        .order_by("user__username")
    )
    # Ensure every non-staff member has a permission row for visibility.
    for profile in MemberProfile.objects.select_related("user").filter(role="member"):
        ToolAccessPermission.objects.get_or_create(user=profile.user)
    permissions = (
        ToolAccessPermission.objects.select_related("user", "granted_by")
        .order_by("user__username")
    )
    sessions = ToolAccessSession.objects.select_related("user").all()[:50]
    logs = ToolAccessLog.objects.select_related("user").all()[:50]
    context = {
        "config": config,
        "permissions": permissions,
        "sessions": sessions,
        "logs": logs,
        "active_session_count": ToolAccessSession.objects.filter(status="active").count(),
    }
    return render(request, "portal/admin_tool_access.html", context)


@login_required
@user_passes_test(_is_admin)
@require_POST
def update_tool_credentials(request):
    config = ToolIntegrationConfig.get_solo()
    config.name = (request.POST.get("name") or "PakSEOtools").strip() or "PakSEOtools"
    config.login_url = (request.POST.get("login_url") or config.login_url).strip()
    config.member_url = (request.POST.get("member_url") or config.member_url).strip()
    username = request.POST.get("username", "")
    password = request.POST.get("password", "")
    if username or password:
        # Keep existing value when field left blank.
        current_username, current_password = config.get_credentials()
        config.set_credentials(
            username if username.strip() != "" else current_username,
            password if password.strip() != "" else current_password,
        )
    config.is_enabled = request.POST.get("is_enabled") == "on"
    config.automation_acknowledged = request.POST.get("automation_acknowledged") == "on"
    config.updated_by = request.user
    config.save()
    _log_tool_action(request.user, "credential_update", status="ok", request=request,
                     details=f"integration_enabled={config.is_enabled}")
    messages.success(request, "PakSEOtools integration settings saved.")
    return redirect("admin_tool_access")


@login_required
@user_passes_test(_is_admin)
@require_POST
def update_member_tool_access(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    if user.is_staff:
        messages.error(request, "Admin accounts are not managed here.")
        return redirect("admin_tool_access")
    permission, _ = ToolAccessPermission.objects.get_or_create(user=user)
    enabled = request.POST.get("enabled") == "on"
    if enabled:
        permission.enable(granted_by=request.user)
        _log_tool_action(request.user, "access_enabled", status="ok", request=request,
                         details=f"member={user.username}")
        messages.success(request, f"PakSEOtools access enabled for {user.username}.")
    else:
        permission.disable(revoked_by=request.user)
        _terminate_user_tool_sessions(user, status="revoked")
        _log_tool_action(request.user, "access_disabled", status="ok", request=request,
                         details=f"member={user.username}")
        messages.success(request, f"PakSEOtools access disabled for {user.username}. Active sessions revoked.")
    return redirect("admin_tool_access")


@login_required
@user_passes_test(_is_admin)
@require_POST
def revoke_tool_session(request, session_id):
    session = get_object_or_404(ToolAccessSession, pk=session_id)
    if session.status == "active":
        session.mark_ended("revoked")
        _log_tool_action(request.user, "session_revoked", status="ok", session=session, request=request,
                         details=f"member={session.user.username}")
    messages.success(request, f"Session for {session.user.username} revoked.")
    return redirect("admin_tool_access")


@login_required
@user_passes_test(_is_admin)
@require_POST
def toggle_tool_integration(request):
    config = ToolIntegrationConfig.get_solo()
    config.is_enabled = request.POST.get("is_enabled") == "on"
    config.automation_acknowledged = request.POST.get("automation_acknowledged") == "on"
    config.updated_by = request.user
    config.save()
    _log_tool_action(request.user, "integration_toggled", status="ok", request=request,
                     details=f"enabled={config.is_enabled}")
    messages.success(request, "Integration settings updated.")
    return redirect("admin_tool_access")


@login_required
@require_POST
def access_pakseotools(request):
    if not _member_profile_ok(request):
        messages.error(request, "Your account is not active.")
        return redirect("login")
    if request.user.is_staff:
        messages.error(request, "Admins manage access from the admin panel.")
        return redirect("admin_panel")

    config = ToolIntegrationConfig.get_solo()
    permission = _tool_permission_for(request.user)

    def deny(reason, action="access_denied"):
        _log_tool_action(request.user, action, status="denied", request=request, details=reason)
        messages.error(request, reason)
        return redirect("dashboard")

    if not config.integration_ready:
        return deny("PakSEOtools integration is not configured or enabled by the admin.")
    if permission is None or not permission.enabled:
        return deny("You are not authorized to access PakSEOtools.")

    # Terminate any expired sessions first.
    _active_tool_session(request.user)

    username, password = config.get_credentials()
    from django.utils import timezone

    session = ToolAccessSession.objects.create(
        user=request.user,
        permission=permission,
        ip_address=_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
        expires_at=timezone.now() + timedelta(minutes=30),
    )

    result = pakseo_login(username, password, config.login_url)
    if not result.get("ok"):
        session.status = "failed"
        session.error_message = result.get("error", "Unknown error")
        session.mark_ended("failed")
        _log_tool_action(request.user, "session_failed", status="failed", session=session, request=request,
                         details=result.get("error", ""))
        messages.error(request, "PakSEOtools is temporarily unavailable: " + result.get("error", "Unknown error"))
        return redirect("dashboard")

    session.cookies_encrypted = encrypt_value(serialize_cookies(result.get("cookies", [])))
    session.backend_user_agent = result.get("user_agent", "")
    session.status = "active"
    session.save(update_fields=["cookies_encrypted", "backend_user_agent", "status", "last_seen_at"])
    _log_tool_action(request.user, "session_started", status="ok", session=session, request=request)
    return redirect("pakseotools_session", token=session.token)


@login_required
def pakseotools_session(request, token):
    if not _member_profile_ok(request):
        return redirect("login")
    session = get_object_or_404(ToolAccessSession, token=token, user=request.user)
    config = ToolIntegrationConfig.get_solo()
    permission = _tool_permission_for(request.user)

    # Immediate revocation checks on every view.
    if not config.integration_ready or permission is None or not permission.enabled:
        if session.status == "active":
            session.mark_ended("revoked")
            _log_tool_action(request.user, "session_revoked", status="revoked", session=session, request=request,
                             details="access revoked")
        messages.error(request, "Your PakSEOtools access has been revoked.")
        return redirect("dashboard")
    if session.status != "active" or session.is_expired:
        if session.status == "active":
            session.mark_ended("expired")
        messages.warning(request, "Your PakSEOtools session has ended. Please request access again.")
        return redirect("dashboard")

    from django.utils import timezone

    session.expires_at = timezone.now() + timedelta(minutes=30)
    session.save(update_fields=["expires_at", "last_seen_at"])
    return render(request, "portal/pakseotools_session.html", {
        "session": session,
        "config": config,
    })


@login_required
@require_POST
def end_pakseotools_session(request, token):
    session = get_object_or_404(ToolAccessSession, token=token, user=request.user)
    if session.status == "active":
        session.mark_ended("ended")
        _log_tool_action(request.user, "session_ended", status="ok", session=session, request=request)
    messages.success(request, "PakSEOtools session ended.")
    return redirect("dashboard")


@login_required
def pakseotools_proxy(request, path=""):
    if not _member_profile_ok(request):
        return HttpResponseForbidden("Authentication required.")
    session = _active_tool_session(request.user)
    if session is None:
        return HttpResponseForbidden("No active PakSEOtools session.")
    config = ToolIntegrationConfig.get_solo()
    permission = _tool_permission_for(request.user)
    if not config.integration_ready or permission is None or not permission.enabled:
        _terminate_user_tool_sessions(request.user, status="revoked")
        return HttpResponseForbidden("Access revoked.")

    import requests as _requests

    base = "https://app.pakseotools.com"
    target_path = "/" + path.lstrip("/")
    query = request.META.get("QUERY_STRING", "")
    url = base + target_path
    if query:
        url = url + "?" + query

    cookies = deserialize_cookies(decrypt_value(session.cookies_encrypted))
    http_session = _requests.Session()
    for cookie in cookies:
        http_session.cookies.set(
            cookie.get("name"), cookie.get("value"),
            domain=cookie.get("domain"), path=cookie.get("path", "/"),
        )

    headers = {
        "User-Agent": session.backend_user_agent or request.META.get("HTTP_USER_AGENT", ""),
        "Accept": request.META.get("HTTP_ACCEPT", "*/*"),
        "Accept-Language": request.META.get("HTTP_ACCEPT_LANGUAGE", "en-US,en;q=0.9"),
    }
    referer = request.META.get("HTTP_REFERER")
    if referer:
        headers["Referer"] = referer

    body = request.body if request.method in ("POST", "PUT", "PATCH") else None
    content_type = request.META.get("CONTENT_TYPE")
    if content_type:
        headers["Content-Type"] = content_type

    try:
        upstream = http_session.request(
            request.method, url, headers=headers, data=body,
            allow_redirects=False, timeout=30,
        )
    except Exception as exc:
        _log_tool_action(request.user, "session_failed", status="failed", session=session, request=request,
                         details=str(exc))
        return HttpResponse("Upstream request failed.", status=502)

    # Persist refreshed cookies.
    refreshed = [
        {"name": c.name, "value": c.value, "domain": c.domain, "path": c.path}
        for c in http_session.cookies
    ]
    session.cookies_encrypted = encrypt_value(serialize_cookies(refreshed))
    session.save(update_fields=["cookies_encrypted", "last_seen_at"])

    def rewrite_url(value):
        if not value:
            return value
        if value.startswith(base):
            value = value[len(base):]
        if value.startswith("/"):
            return "/tools/pakseotools/proxy" + value
        return value

    if upstream.is_redirect:
        location = rewrite_url(upstream.headers.get("Location", ""))
        response = HttpResponse(status=upstream.status_code)
        if location:
            response["Location"] = location
        return response

    content = upstream.content
    content_type = upstream.headers.get("Content-Type", "")
    if "text/html" in content_type:
        text = content.decode(upstream.encoding or "utf-8", errors="replace")
        # Rewrite absolute and root-relative URLs so navigation stays proxied.
        text = text.replace('href="/', 'href="/tools/pakseotools/proxy/')
        text = text.replace('src="/', 'src="/tools/pakseotools/proxy/')
        text = text.replace('action="/', 'action="/tools/pakseotools/proxy/')
        text = text.replace(base + "/", "/tools/pakseotools/proxy/")
        text = text.replace(base, "/tools/pakseotools/proxy")
        content = text.encode("utf-8")

    response = HttpResponse(content, status=upstream.status_code, content_type=content_type or "application/octet-stream")
    for header in ("Content-Disposition", "Cache-Control"):
        if header in upstream.headers:
            response[header] = upstream.headers[header]
    return response
