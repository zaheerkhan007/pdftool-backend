from django.contrib.auth.models import User
from django.db.models import Count, Sum
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ToolUsage
from .serializers import RegisterSerializer, ToolUsageSerializer, UserSerializer


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


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
            .annotate(runs=Count("id"), saved=Sum("input_bytes") - Sum("output_bytes"))
            .order_by("-runs")
        )
        return Response(
            {
                "total_runs": qs.count(),
                "by_tool": list(by_tool),
                "recent": ToolUsageSerializer(qs[:10], many=True).data,
            }
        )
