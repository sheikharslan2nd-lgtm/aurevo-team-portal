from django.urls import path
from . import views

urlpatterns = [
    path("health/", views.health_check, name="health_check"),
    path("", views.home, name="home"),
    path("our-team/", views.our_team, name="our_team"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("strategy/add/", views.add_strategy, name="add_strategy"),
    path("strategy/<int:pk>/delete/", views.delete_strategy, name="delete_strategy"),
    path("report/save/", views.save_report, name="save_report"),
    path("cities/", views.cities_for_country, name="cities_for_country"),
    path("niches/<int:parent_id>/", views.niches_for_parent, name="niches_for_parent"),
    path("niches/<int:niche_id>/tree/", views.niche_tree, name="niche_tree"),
    path("admin-panel/", views.admin_panel, name="admin_panel"),
    path("admin-panel/member/<int:user_id>/status/", views.update_member_status, name="update_member_status"),
]
