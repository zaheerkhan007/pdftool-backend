from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("health", views.health),
    path("merge/", views.MergeView.as_view(), name="merge"),
    path("merge", views.MergeView.as_view()),
    path("split/", views.SplitView.as_view(), name="split"),
    path("split", views.SplitView.as_view()),
    path("compress/", views.CompressView.as_view(), name="compress"),
    path("compress", views.CompressView.as_view()),
    path("rotate/", views.RotateView.as_view(), name="rotate"),
    path("rotate", views.RotateView.as_view()),
]
