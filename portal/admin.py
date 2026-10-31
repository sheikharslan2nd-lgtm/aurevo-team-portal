from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import MemberProfile, TeamMember, Country, City, Niche, OutreachMethod, Strategy, DailyReport

class ProfileInline(admin.StackedInline):
    model = MemberProfile
    can_delete = False
    extra = 0

class UserAdmin(BaseUserAdmin):
    inlines = [ProfileInline]
    list_display = ("username", "email", "first_name", "last_name", "is_staff", "profile_status")
    list_filter = ("is_staff", "is_active", "profile__status")

    @admin.display(description="Portal status")
    def profile_status(self, obj):
        return getattr(getattr(obj, "profile", None), "status", "Admin / no profile")

admin.site.unregister(User)
admin.site.register(User, UserAdmin)

@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "whatsapp", "created_at")
    list_filter = ("status",)
    search_fields = ("user__username", "user__email", "user__first_name", "whatsapp")
    list_editable = ("status",)

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
