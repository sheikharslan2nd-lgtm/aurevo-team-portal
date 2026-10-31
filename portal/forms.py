from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import MemberProfile, Strategy, DailyReport, City, Niche


class RegisterForm(forms.Form):
    username = forms.CharField(max_length=150, label="Username")
    email = forms.EmailField()
    password1 = forms.CharField(widget=forms.PasswordInput, label="Password")
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm password")
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    whatsapp = forms.CharField(max_length=40)
    qualification = forms.CharField(max_length=160, required=False)
    skills = forms.CharField(widget=forms.Textarea, required=False)
    experience = forms.CharField(max_length=160, required=False)

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("This username is already registered.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("This email is already registered.")
        return email

    def clean(self):
        data = super().clean()
        if data.get("password1") and data.get("password2") and data["password1"] != data["password2"]:
            self.add_error("password2", "Passwords do not match.")
        if data.get("password1"):
            try:
                validate_password(data["password1"])
            except ValidationError as exc:
                self.add_error("password1", exc)
        return data


class StrategyForm(forms.ModelForm):
    niche_parent = forms.ModelChoiceField(
        queryset=Niche.objects.filter(parent__isnull=True),
        label="Main niche",
        required=False,
    )
    niche_micro = forms.ModelChoiceField(
        queryset=Niche.objects.none(),
        label="Micro-niche",
        required=False,
    )

    class Meta:
        model = Strategy
        fields = ["country", "city", "niche_parent", "niche", "niche_micro", "method", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Target audience, pitch angle, follow-up plan..."})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["city"].queryset = City.objects.none()
        self.fields["niche"].queryset = Niche.objects.none()
        self.fields["niche_micro"].queryset = Niche.objects.none()

        country_id = self.data.get("country") or self.initial.get("country")
        if country_id:
            try:
                self.fields["city"].queryset = City.objects.filter(country_id=int(country_id))
            except (TypeError, ValueError):
                pass

        chain = self._instance_chain()
        parent_id = self.data.get("niche_parent") or self.initial.get("niche_parent")
        niche_id = self.data.get("niche") or self.initial.get("niche")
        micro_id = self.data.get("niche_micro") or self.initial.get("niche_micro")
        if parent_id is None and chain:
            parent_id = chain[0].id
        if niche_id is None and len(chain) > 1:
            niche_id = chain[1].id
        if micro_id is None and len(chain) > 2:
            micro_id = chain[2].id

        parent_id = self._as_int(parent_id)
        niche_id = self._as_int(niche_id)
        micro_id = self._as_int(micro_id)

        if parent_id:
            self.fields["niche"].queryset = Niche.objects.filter(parent_id=parent_id)
            self.fields["niche_parent"].initial = parent_id
        if niche_id:
            self.fields["niche"].initial = niche_id
            self.fields["niche_micro"].queryset = Niche.objects.filter(parent_id=niche_id)
        if micro_id:
            self.fields["niche_micro"].initial = micro_id

    @staticmethod
    def _as_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _instance_chain(self):
        """Return the saved niche path: [main, sub, micro] (as far as it exists)."""
        if not getattr(self.instance, "niche_id", None):
            return []
        chain = []
        node = self.instance.niche
        while node is not None and len(chain) < 6:
            chain.append(node)
            node = node.parent
        return list(reversed(chain))

    def clean(self):
        data = super().clean()
        country, city = data.get("country"), data.get("city")
        if country and city and city.country_id != country.id:
            self.add_error("city", "Choose a city from the selected country.")

        niche_parent, niche, micro = data.get("niche_parent"), data.get("niche"), data.get("niche_micro")
        if niche_parent and niche and niche.parent_id != niche_parent.id:
            self.add_error("niche", "Select a sub-niche from the chosen main niche category.")
        if micro:
            if not niche:
                self.add_error("niche_micro", "Choose a sub-niche before choosing a micro-niche.")
            elif micro.parent_id != niche.id:
                self.add_error("niche_micro", "Select a micro-niche from the chosen sub-niche.")
        return data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.niche = self.cleaned_data.get("niche_micro") or self.cleaned_data.get("niche")
        if commit:
            instance.save()
        return instance


class DailyReportForm(forms.ModelForm):
    class Meta:
        model = DailyReport
        fields = [
            "report_date", "emails_sent", "messages_sent", "calls_made",
            "replies_received", "interested_leads", "meetings_booked",
            "deals_closed", "followups", "notes"
        ]
        widgets = {
            "report_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Progress, client responses, blockers..."})
        }
