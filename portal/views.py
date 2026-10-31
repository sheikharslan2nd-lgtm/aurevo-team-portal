import json
from datetime import date
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from .forms import RegisterForm, StrategyForm, DailyReportForm
from .models import MemberProfile, TeamMember, Strategy, DailyReport, Country, City, Niche, OutreachMethod


def _is_admin(user):
    return user.is_authenticated and user.is_staff


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
            )
        messages.success(request, "Account created. Your account is pending admin approval.")
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
            if user.is_staff:
                login(request, user)
                return redirect("admin_panel")
            _ensure_profile(user)
            if user.profile.status != "active":
                error = "Your account is pending approval or has been suspended. Contact the admin."
            else:
                login(request, user)
                return redirect("dashboard")
        else:
            error = "Invalid username or password."
    return render(request, "portal/login.html", {"error": error})


def home(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect("admin_panel")
        return redirect("dashboard")
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
    return JsonResponse({"cities": list(cities)})


@require_GET
def niches_for_parent(request, parent_id):
    parent = get_object_or_404(Niche, pk=parent_id)
    children = list(parent.children.order_by("name").values("id", "name"))
    return JsonResponse({"children": children})


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
    return JsonResponse(
        {
            "niche": {"id": niche.id, "name": niche.name, "parent_id": niche.parent_id},
            "children": children,
        }
    )


@login_required
@user_passes_test(_is_admin)
def admin_panel(request):
    profiles = MemberProfile.objects.select_related("user").order_by("status", "user__username")
    reports = DailyReport.objects.select_related("member").all()[:100]
    strategies = Strategy.objects.select_related("member", "country", "city", "niche", "method").all()[:100]
    context = {
        "profiles": profiles,
        "reports": reports,
        "strategies": strategies,
        "pending_count": MemberProfile.objects.filter(status="pending").count(),
        "active_count": MemberProfile.objects.filter(status="active").count(),
        "report_count": DailyReport.objects.count(),
        "countries_count": Country.objects.count(),
        "cities_count": City.objects.count(),
        "niches_count": Niche.objects.count(),
        "methods_count": OutreachMethod.objects.count(),
    }
    return render(request, "portal/admin_panel.html", context)


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
    else:
        profile.status = status
        profile.save(update_fields=["status"])
        messages.success(request, f"{user.username} status updated to {status}.")
    return redirect("admin_panel")
