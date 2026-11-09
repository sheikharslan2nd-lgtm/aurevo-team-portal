from django.conf import settings
from django.db import models
from django.utils import timezone


class MemberProfile(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending approval"),
        ("active", "Active"),
        ("suspended", "Suspended"),
    ]
    ROLE_CHOICES = [
        ("member", "Team member"),
        ("leader", "Team leader"),
    ]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    whatsapp = models.CharField(max_length=40, blank=True)
    qualification = models.CharField(max_length=160, blank=True)
    skills = models.TextField(blank=True)
    experience = models.CharField(max_length=160, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="member")
    referred_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="team_members",
        limit_choices_to={"profile__role": "leader"},
        help_text="Team leader who referred this member.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_leader(self):
        return self.role == "leader"

    @property
    def team_size(self):
        return self.user.team_members.count()

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()} · {self.status})"


class TeamMember(models.Model):
    name = models.CharField(max_length=120)
    role = models.CharField(max_length=120)
    description = models.TextField()
    photo = models.ImageField(upload_to="team/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class Country(models.Model):
    name = models.CharField(max_length=120, unique=True)
    iso2 = models.CharField(max_length=2, blank=True, db_index=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class City(models.Model):
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name="cities")
    name = models.CharField(max_length=120)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["country", "name"], name="unique_city_per_country")
        ]

    def __str__(self):
        return f"{self.name}, {self.country.name}"


class Niche(models.Model):
    name = models.CharField(max_length=180)
    parent = models.ForeignKey("self", on_delete=models.CASCADE, related_name="children", null=True, blank=True)
    slug = models.SlugField(max_length=220, blank=True)
    description = models.TextField(blank=True)
    search_keywords = models.TextField(
        blank=True,
        help_text="Comma-separated search keywords/terms to find prospects in this niche (English).",
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["parent", "name"], name="unique_niche_name_per_parent")
        ]

    def __str__(self):
        if self.parent_id:
            return f"{self.parent.name} / {self.name}"
        return self.name

    @property
    def full_path(self):
        """Full hierarchy path, e.g. ``Health / Skin Care / Best Skin Care``."""
        parts = []
        node = self
        while node is not None and len(parts) < 6:
            parts.append(node.name)
            node = node.parent
        return " / ".join(reversed(parts))


class OutreachMethod(models.Model):
    name = models.CharField(max_length=100, unique=True)
    approach_note = models.TextField(
        blank=True,
        help_text="Detailed English note on how to approach prospects using this method.",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Strategy(models.Model):
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="strategies")
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name="strategies")
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="strategies")
    niche = models.ForeignKey(Niche, on_delete=models.PROTECT, related_name="strategies")
    method = models.ForeignKey(OutreachMethod, on_delete=models.PROTECT, related_name="strategies")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.city_id and self.country_id and self.city.country_id != self.country_id:
            raise ValidationError({"city": "Selected city does not belong to the selected country."})

    def __str__(self):
        return f"{self.member.username}: {self.niche} / {self.city}"


class DailyReport(models.Model):
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="daily_reports")
    report_date = models.DateField(default=timezone.localdate)
    emails_sent = models.PositiveIntegerField(default=0)
    messages_sent = models.PositiveIntegerField(default=0)
    calls_made = models.PositiveIntegerField(default=0)
    replies_received = models.PositiveIntegerField(default=0)
    interested_leads = models.PositiveIntegerField(default=0)
    meetings_booked = models.PositiveIntegerField(default=0)
    deals_closed = models.PositiveIntegerField(default=0)
    followups = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-report_date", "-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["member", "report_date"], name="one_daily_report_per_member")
        ]

    def __str__(self):
        return f"{self.member.username} — {self.report_date}"


import uuid

from .crypto import decrypt_value, encrypt_value


class ToolIntegrationConfig(models.Model):
    """Singleton holding the (encrypted) PakSEOtools credentials."""

    name = models.CharField(max_length=80, default="PakSEOtools")
    login_url = models.URLField(default="https://app.pakseotools.com/login", blank=True)
    member_url = models.URLField(default="https://app.pakseotools.com/member", blank=True)
    username_encrypted = models.TextField(blank=True, default="")
    password_encrypted = models.TextField(blank=True, default="")
    is_enabled = models.BooleanField(default=False)
    automation_acknowledged = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        verbose_name = "Tool integration config"

    def __str__(self):
        return f"{self.name} integration"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={"name": "PakSEOtools"})
        return obj

    def set_credentials(self, username, password):
        self.username_encrypted = encrypt_value(username or "")
        self.password_encrypted = encrypt_value(password or "")

    def get_credentials(self):
        return decrypt_value(self.username_encrypted), decrypt_value(self.password_encrypted)

    @property
    def has_credentials(self):
        username, password = self.get_credentials()
        return bool(username and password)

    @property
    def masked_username(self):
        username, _ = self.get_credentials()
        if not username:
            return "Not configured"
        if len(username) <= 4:
            return "*" * len(username)
        return username[:2] + "*" * (len(username) - 4) + username[-2:]

    @property
    def integration_ready(self):
        return bool(self.is_enabled and self.has_credentials and self.automation_acknowledged)


class ToolAccessPermission(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tool_access_permission")
    enabled = models.BooleanField(default=False)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="granted_tool_access"
    )
    granted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}: {'enabled' if self.enabled else 'disabled'}"

    def enable(self, granted_by=None):
        from django.utils import timezone

        self.enabled = True
        self.granted_by = granted_by
        self.granted_at = timezone.now()
        self.revoked_at = None
        self.save()

    def disable(self, revoked_by=None):
        from django.utils import timezone

        self.enabled = False
        self.revoked_at = timezone.now()
        self.save()


class ToolAccessSession(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("ended", "Ended"),
        ("revoked", "Revoked"),
        ("expired", "Expired"),
        ("failed", "Failed"),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tool_access_sessions")
    permission = models.ForeignKey(ToolAccessPermission, on_delete=models.SET_NULL, null=True, blank=True)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="active")
    started_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    backend_user_agent = models.TextField(blank=True)
    cookies_encrypted = models.TextField(blank=True, default="")
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.user.username} session {self.token} ({self.status})"

    def mark_ended(self, status="ended"):
        from django.utils import timezone

        self.status = status
        self.ended_at = timezone.now()
        self.cookies_encrypted = ""
        self.save(update_fields=["status", "ended_at", "cookies_encrypted"])

    @property
    def is_expired(self):
        from django.utils import timezone

        return bool(self.expires_at and self.expires_at < timezone.now())


class ToolAccessLog(models.Model):
    ACTION_CHOICES = [
        ("credential_update", "Credential update"),
        ("access_enabled", "Access enabled"),
        ("access_disabled", "Access disabled"),
        ("session_started", "Session started"),
        ("session_failed", "Session failed"),
        ("session_ended", "Session ended"),
        ("session_revoked", "Session revoked"),
        ("access_denied", "Access denied"),
        ("integration_toggled", "Integration toggled"),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="tool_access_logs")
    session = models.ForeignKey(ToolAccessSession, on_delete=models.SET_NULL, null=True, blank=True, related_name="logs")
    action = models.CharField(max_length=32, choices=ACTION_CHOICES)
    status = models.CharField(max_length=16, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} {self.user} @ {self.created_at}"
