from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView

from accounts.views import EmailTokenObtainPairView

urlpatterns = [
    path("admin/", admin.site.urls),
    # Auth. Login takes {email, password} — see accounts.serializers.
    # Both slash spellings, same as every other route (APPEND_SLASH=False).
    path("api/auth/token/", EmailTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token", EmailTokenObtainPairView.as_view()),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/token/refresh", TokenRefreshView.as_view()),
    path("api/accounts/", include("accounts.urls")),
    # PDF tools
    path("api/tools/", include("tools.urls")),
]
