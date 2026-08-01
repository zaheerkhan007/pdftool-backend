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
    path("pdf-to-jpg/", views.PdfToJpgView.as_view(), name="pdf-to-jpg"),
    path("pdf-to-jpg", views.PdfToJpgView.as_view()),
    path("pdf-to-word/", views.PdfToWordView.as_view(), name="pdf-to-word"),
    path("pdf-to-word", views.PdfToWordView.as_view()),
    path("word-to-pdf/", views.WordToPdfView.as_view(), name="word-to-pdf"),
    path("word-to-pdf", views.WordToPdfView.as_view()),
    path("protect/", views.ProtectView.as_view(), name="protect"),
    path("protect", views.ProtectView.as_view()),
    path("unlock/", views.UnlockView.as_view(), name="unlock"),
    path("unlock", views.UnlockView.as_view()),
]
