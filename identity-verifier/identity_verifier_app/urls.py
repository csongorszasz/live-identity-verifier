from django.urls import path

from .views import IdentityVerifier

urlpatterns = [
    path("verify-identity/", IdentityVerifier.as_view(), name="verify-identity"),
]
