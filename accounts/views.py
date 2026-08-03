from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import Count, F, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import ToolUsage
from .serializers import (
    EmailTokenObtainPairSerializer,
    RegisterSerializer,
    ToolUsageSerializer,
    UserSerializer,
)


class EmailTokenObtainPairView(TokenObtainPairView):
    """POST {email, password} -> {access, refresh, user}."""

    serializer_class = EmailTokenObtainPairSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = s.save()
        # Hand back tokens immediately so signup lands the user signed in
        # instead of bouncing them to a login form they just filled out.
        tokens = EmailTokenObtainPairSerializer.get_token(user)
        return Response(
            {
                "access": str(tokens.access_token),
                "refresh": str(tokens),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class DashboardStatsView(APIView):
    """Aggregate stats for the logged-in user's dashboard."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = ToolUsage.objects.filter(user=request.user)
        by_tool = (
            qs.values("tool")
            .annotate(runs=Count("id"), saved=Sum(F("input_bytes") - F("output_bytes")))
            .order_by("-runs")
        )
        return Response(
            {
                "total_runs": qs.count(),
                "by_tool": list(by_tool),
                "recent": ToolUsageSerializer(qs[:10], many=True).data,
            }
        )


class AdminStatsView(APIView):
    """Site-wide stats. Staff only."""

    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        now = timezone.now()
        last_30 = now - timedelta(days=30)
        qs = ToolUsage.objects.all()
        recent_qs = qs.filter(created_at__gte=last_30)

        by_tool = (
            qs.values("tool")
            .annotate(runs=Count("id"), saved=Sum(F("input_bytes") - F("output_bytes")))
            .order_by("-runs")[:15]
        )
        runs_per_day = (
            recent_qs.annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(runs=Count("id"))
            .order_by("day")
        )
        totals = qs.aggregate(bytes_in=Sum("input_bytes"), files=Sum("file_count"))

        return Response(
            {
                "total_runs": qs.count(),
                "runs_30d": recent_qs.count(),
                "total_files": totals["files"] or 0,
                "total_bytes_in": totals["bytes_in"] or 0,
                "anonymous_runs": qs.filter(user__isnull=True).count(),
                "total_users": User.objects.count(),
                "users_30d": User.objects.filter(date_joined__gte=last_30).count(),
                "by_tool": list(by_tool),
                "runs_per_day": list(runs_per_day),
                "recent_signups": UserSerializer(
                    User.objects.order_by("-date_joined")[:10], many=True
                ).data,
            }
        )
