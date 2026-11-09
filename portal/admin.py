from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import MemberProfile, TeamMember, Country, City, Niche, OutreachMethod, Strategy, DailyReport, ToolIntegrationConfig, ToolAccessPermission, ToolAccessSession, ToolAccessLog

class ProfileInline(admin.StackedInline):
    model = MemberProfile
    fk_name = "user"
    can_delete = False
    extra = 0

class UserAdmin(BaseUserAdmin):
    inlines = [ProfileInline]
    list_display = ("username", "email", "first_name", "last_name", "is_staff", "profile_role", "profile_status")
    list_filter = ("is_staff", "is_active", "profile__role", "profile__status")

    @admin.display(description="Portal status")
    def profile_status(self, obj):
        return getattr(getattr(obj, "profile", None), "status", "Admin / no profile")

    @admin.display(description="Portal role")
    def profile_role(self, obj):
        profile = getattr(obj, "profile", None)
        return profile.get_role_display() if profile else "Admin"

admin.site.unregister(User)
admin.site.register(User, UserAdmin)

@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "referred_by", "status", "whatsapp", "created_at")
    list_filter = ("role", "status")
    search_fields = ("user__username", "user__email", "user__first_name", "whatsapp", "referred_by__username")
    list_editable = ("status",)
    autocomplete_fields = ("referred_by",)

@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ("name", "role", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("name", "role", "description")
    list_editable = ("role", "is_active", "sort_order")
    fieldsets = (
        (None, {"fields": ("name", "role", "description", "photo", "is_active", "sort_order")}),
    )

@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    search_fields = ("name", "iso2")
    list_display = ("name", "iso2")
    ordering = ("name",)

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "country")
    list_filter = ("country",)
    search_fields = ("name", "country__name")
    autocomplete_fields = ("country",)

@admin.register(Niche)
class NicheAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "slug")
    list_filter = ("parent",)
    search_fields = ("name", "parent__name")

@admin.register(OutreachMethod)
class OutreachMethodAdmin(admin.ModelAdmin):
    search_fields = ("name",)

@admin.register(Strategy)
class StrategyAdmin(admin.ModelAdmin):
    list_display = ("member", "country", "city", "niche", "method", "created_at")
    list_filter = ("country", "niche", "method")
    search_fields = ("member__username", "city__name", "niche__name")

@admin.register(DailyReport)
class DailyReportAdmin(admin.ModelAdmin):
    list_display = ("member", "report_date", "emails_sent", "messages_sent", "replies_received", "interested_leads", "deals_closed")
    list_filter = ("report_date",)
    search_fields = ("member__username", "member__email")
    date_hierarchy = "report_date"


@admin.register(ToolIntegrationConfig)
class ToolIntegrationConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "is_enabled", "automation_acknowledged", "has_credentials", "updated_at")
    readonly_fields = ("username_encrypted", "password_encrypted", "updated_at")

    @admin.display(boolean=True, description="Credentials configured")
    def has_credentials(self, obj):
        return obj.has_credentials


@admin.register(ToolAccessPermission)
class ToolAccessPermissionAdmin(admin.ModelAdmin):
    list_display = ("user", "enabled", "granted_by", "granted_at", "revoked_at")
    list_filter = ("enabled",)
    search_fields = ("user__username",)


@admin.register(ToolAccessSession)
class ToolAccessSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "started_at", "ended_at", "ip_address")
    list_filter = ("status",)
    search_fields = ("user__username",)
    readonly_fields = ("token", "cookies_encrypted")


@admin.register(ToolAccessLog)
class ToolAccessLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "status", "ip_address")
    list_filter = ("action", "status")
    search_fields = ("user__username", "details")
