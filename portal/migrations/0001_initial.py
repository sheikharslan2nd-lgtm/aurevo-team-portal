# Generated migration for the initial Aurevo team portal schema.
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="Country",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("iso2", models.CharField(blank=True, db_index=True, max_length=2)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Niche",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="OutreachMethod",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="MemberProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("whatsapp", models.CharField(blank=True, max_length=40)),
                ("qualification", models.CharField(blank=True, max_length=160)),
                ("skills", models.TextField(blank=True)),
                ("experience", models.CharField(blank=True, max_length=160)),
                ("status", models.CharField(choices=[("pending", "Pending approval"), ("active", "Active"), ("suspended", "Suspended")], default="pending", max_length=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="profile", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="City",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("country", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="cities", to="portal.country")),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Strategy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("city", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="strategies", to="portal.city")),
                ("country", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="strategies", to="portal.country")),
                ("member", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="strategies", to=settings.AUTH_USER_MODEL)),
                ("method", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="strategies", to="portal.outreachmethod")),
                ("niche", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="strategies", to="portal.niche")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="DailyReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("report_date", models.DateField(default=django.utils.timezone.localdate)),
                ("emails_sent", models.PositiveIntegerField(default=0)),
                ("messages_sent", models.PositiveIntegerField(default=0)),
                ("calls_made", models.PositiveIntegerField(default=0)),
                ("replies_received", models.PositiveIntegerField(default=0)),
                ("interested_leads", models.PositiveIntegerField(default=0)),
                ("meetings_booked", models.PositiveIntegerField(default=0)),
                ("deals_closed", models.PositiveIntegerField(default=0)),
                ("followups", models.PositiveIntegerField(default=0)),
                ("notes", models.TextField(blank=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("member", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="daily_reports", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-report_date", "-updated_at"]},
        ),
        migrations.AddConstraint(
            model_name="city",
            constraint=models.UniqueConstraint(fields=("country", "name"), name="unique_city_per_country"),
        ),
        migrations.AddConstraint(
            model_name="dailyreport",
            constraint=models.UniqueConstraint(fields=("member", "report_date"), name="one_daily_report_per_member"),
        ),
    ]
