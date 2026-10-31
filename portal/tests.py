from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase

from portal.models import City, Country, MemberProfile, Niche, OutreachMethod, Strategy


class HealthAndHostChecks(TestCase):
    def test_health_endpoint_returns_ok(self):
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')

    def test_testserver_host_is_allowed(self):
        response = self.client.get('/login/', HTTP_HOST='testserver')
        self.assertEqual(response.status_code, 200)

    def test_home_page_renders_join_team_content(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Aurevo System')
        self.assertContains(response, 'Join Aurevo System')

    def test_our_team_page_renders(self):
        response = self.client.get('/our-team/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Our Team')
        self.assertContains(response, 'This section is intentionally empty until team members are added from the admin panel.')

    def test_session_settings_persist_user_login_state(self):
        self.assertTrue(getattr(settings, 'SESSION_SAVE_EVERY_REQUEST', False))
        self.assertGreater(getattr(settings, 'SESSION_COOKIE_AGE', 0), 0)

    def test_logged_in_user_keeps_session_and_dashboard_access(self):
        user = User.objects.create_user(username='testmember', password='TestPass123!')
        MemberProfile.objects.create(user=user, status='active')

        login_result = self.client.login(username='testmember', password='TestPass123!')
        self.assertTrue(login_result)
        self.assertIsNotNone(self.client.session.session_key)

        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 200)

    def test_dynamic_dropdown_endpoints_return_country_and_niche_children(self):
        country = Country.objects.create(name='United States')
        city = City.objects.create(country=country, name='New York')
        parent = Niche.objects.create(name='Business Services')
        child = Niche.objects.create(parent=parent, name='Marketing Agency')

        city_response = self.client.get('/cities/', {'country_id': country.id})
        self.assertEqual(city_response.status_code, 200)
        self.assertIn({'id': city.id, 'name': 'New York'}, city_response.json()['cities'])

        niche_response = self.client.get(f'/niches/{parent.id}/')
        self.assertEqual(niche_response.status_code, 200)
        self.assertIn({'id': child.id, 'name': 'Marketing Agency'}, niche_response.json()['children'])


class NicheHierarchyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="hierarchymember", password="TestPass123!")
        MemberProfile.objects.create(user=self.user, status="active")
        self.country = Country.objects.create(name="Pakistan")
        self.city = City.objects.create(country=self.country, name="Lahore")
        self.main = Niche.objects.create(name="Dental Clinics")
        self.sub = Niche.objects.create(parent=self.main, name="Cosmetic Dentistry")
        self.micro = Niche.objects.create(parent=self.sub, name="Best Cosmetic Dentistry")
        self.method = OutreachMethod.objects.create(name="Cold Email")
        self.client.login(username="hierarchymember", password="TestPass123!")

    def test_tree_endpoint_returns_sub_niches_and_micro_niches(self):
        response = self.client.get(f"/niches/{self.main.id}/tree/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["niche"]["name"], "Dental Clinics")
        self.assertEqual(len(data["children"]), 1)
        self.assertEqual(data["children"][0]["name"], "Cosmetic Dentistry")
        self.assertIn(
            {"id": self.micro.id, "name": "Best Cosmetic Dentistry"},
            data["children"][0]["children"],
        )

    def test_dashboard_lists_all_countries_and_niches(self):
        Country.objects.create(name="Zimbabwe")
        Niche.objects.create(name="Bicycle Repair")
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Zimbabwe")
        self.assertContains(response, "Bicycle Repair")
        self.assertContains(response, "explorer-grid")

    def test_strategy_saves_the_selected_micro_niche(self):
        response = self.client.post(
            "/strategy/add/",
            {
                "country": self.country.id,
                "city": self.city.id,
                "niche_parent": self.main.id,
                "niche": self.sub.id,
                "niche_micro": self.micro.id,
                "method": self.method.id,
                "notes": "Micro-niche targeting",
            },
        )
        self.assertEqual(response.status_code, 302)
        strategy = Strategy.objects.get(member=self.user)
        self.assertEqual(strategy.niche, self.micro)
        self.assertEqual(strategy.niche.full_path, "Dental Clinics / Cosmetic Dentistry / Best Cosmetic Dentistry")

    def test_strategy_rejects_micro_niche_from_another_sub_niche(self):
        other_sub = Niche.objects.create(parent=self.main, name="Orthodontics")
        other_micro = Niche.objects.create(parent=other_sub, name="Best Orthodontics")
        response = self.client.post(
            "/strategy/add/",
            {
                "country": self.country.id,
                "city": self.city.id,
                "niche_parent": self.main.id,
                "niche": self.sub.id,
                "niche_micro": other_micro.id,
                "method": self.method.id,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Strategy.objects.filter(member=self.user).exists())


class NicheGeneratorTests(TestCase):
    def test_micro_niche_generation_is_stable_and_unique(self):
        from portal.niche_data import generate_micro_niches

        first = generate_micro_niches("Dental Clinics")
        second = generate_micro_niches("Dental Clinics")
        self.assertEqual(first, second)
        self.assertEqual(len(first), len(set(first)))
        self.assertTrue(all("Dental Clinics" in name for name in first))

    def test_curated_sub_niches_are_used_when_available(self):
        from portal.niche_data import CURATED_SUB_NICHES, generate_sub_niches

        self.assertIn("Dental Clinics", CURATED_SUB_NICHES)
        self.assertEqual(generate_sub_niches("Dental Clinics"), CURATED_SUB_NICHES["Dental Clinics"])

    def test_fallback_sub_niches_are_generated_for_unknown_categories(self):
        from portal.niche_data import generate_sub_niches

        subs = generate_sub_niches("Left-Handed Widgets")
        self.assertTrue(subs)
        self.assertTrue(all("Left-Handed Widgets" in name for name in subs))


class CountrySeedHelperTests(TestCase):
    def test_country_rows_are_deduplicated_by_iso_code(self):
        from portal.management.commands.seed_locations import _get_or_create_country

        first = _get_or_create_country("Pakistan", "PK")
        second = _get_or_create_country("Islamic Republic of Pakistan", "PK", rename=True)

        self.assertEqual(first.id, second.id)
        self.assertEqual(Country.objects.filter(iso2="PK").count(), 1)
        self.assertEqual(second.name, "Islamic Republic of Pakistan")

    def test_iso_lookup_handles_pycountry_aliases(self):
        from portal.management.commands.seed_locations import _lookup_iso2

        self.assertEqual(_lookup_iso2("Turkey"), "TR")
        self.assertEqual(_lookup_iso2("Russia"), "RU")
        self.assertEqual(_lookup_iso2("Ivory Coast"), "CI")
        self.assertEqual(_lookup_iso2("Pakistan"), "PK")

    def test_unknown_country_is_created_once_by_name(self):
        from portal.management.commands.seed_locations import _get_or_create_country

        first = _get_or_create_country("Atlantis")
        second = _get_or_create_country("atlantis")
        self.assertEqual(first.id, second.id)
        self.assertEqual(Country.objects.filter(name__iexact="Atlantis").count(), 1)
