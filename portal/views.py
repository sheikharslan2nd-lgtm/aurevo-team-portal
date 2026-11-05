import json
from datetime import date, timedelta
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Max, Sum
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from .forms import RegisterForm, StrategyForm, DailyReportForm, TeamLeaderCreateForm
from .models import MemberProfile, TeamMember, Strategy, DailyReport, Country, City, Niche, OutreachMethod


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
