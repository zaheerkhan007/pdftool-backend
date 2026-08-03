from django.urls import path

from . import views

# APPEND_SLASH=False, so every route is registered with AND without the
# trailing slash — otherwise one spelling 404s through the Next.js proxy.
urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("register", views.RegisterView.as_view()),
    path("me/", views.MeView.as_view(), name="me"),
    path("me", views.MeView.as_view()),
    path("dashboard/stats/", views.DashboardStatsView.as_view(), name="dashboard-stats"),
    path("dashboard/stats", views.DashboardStatsView.as_view()),
    path("admin/stats/", views.AdminStatsView.as_view(), name="admin-stats"),
    path("admin/stats", views.AdminStatsView.as_view()),
]
