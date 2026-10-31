from django.conf import settings
from django.db import models
from django.utils import timezone


class MemberProfile(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending approval"),
        ("active", "Active"),
        ("suspended", "Suspended"),
    ]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    whatsapp = models.CharField(max_length=40, blank=True)
    qualification = models.CharField(max_length=160, blank=True)
    skills = models.TextField(blank=True)
    experience = models.CharField(max_length=160, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.status})"


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
