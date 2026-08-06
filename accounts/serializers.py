import re
import uuid

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import ToolUsage


def _username_from_email(email: str) -> str:
    """
    Derive a unique username from the email local part. Users never see or type
    this — it exists only because Django's User model requires it.
    """
    local = email.split("@")[0]
    base = re.sub(r"[^\w.@+-]", "", local)[:20].strip(".") or "user"
    if not User.objects.filter(username=base).exists():
        return base
    # Random suffix rather than a counter: no extra queries, no race between
    # two signups picking the same next number.
    for _ in range(5):
        candidate = f"{base[:24]}-{uuid.uuid4().hex[:6]}"
        if not User.objects.filter(username=candidate).exists():
            return candidate
    return f"user-{uuid.uuid4().hex[:12]}"


class RegisterSerializer(serializers.Serializer):
    """Email + password signup. Username is generated, never supplied."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8, max_length=128)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)

    def validate_email(self, value):
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                "An account with this email already exists."
            )
        return email

    def validate_password(self, value):
        # Django's configured validators (length, common passwords, all-numeric).
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def create(self, validated_data):
        email = validated_data["email"]
        try:
            with transaction.atomic():
                return User.objects.create_user(
                    username=_username_from_email(email),
                    email=email,
                    password=validated_data["password"],
                    first_name=validated_data.get("first_name", ""),
                )
        except IntegrityError:
            # The unique-email index caught a signup that raced past the
            # validate_email check between two concurrent requests.
            raise serializers.ValidationError(
                {"email": ["An account with this email already exists."]}
            )


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Swaps SimpleJWT's `username` field for `email`, so the login request body is
    {"email": ..., "password": ...}. Authentication itself is handled by
    accounts.backends.EmailBackend.
    """

    username_field = "email"

    def validate(self, attrs):
        # Normalise so "  Foo@Bar.com " matches the stored address.
        if self.username_field in attrs:
            attrs[self.username_field] = attrs[self.username_field].strip().lower()
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "date_joined", "is_staff"]


class AdminUserSerializer(serializers.ModelSerializer):
    """
    Member row for the staff dashboard. `runs` comes from an annotate() on the
    queryset, so listing 200 users costs one query rather than 200.

    Staff-only by virtue of where it is used — AdminStatsView is IsAdminUser.
    Deliberately no password, no tokens and no last-IP: this answers "who signed
    up and are they using it", not "what is this person doing".
    """

    runs = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "date_joined",
            "last_login", "is_staff", "is_active", "runs",
        ]


class ToolUsageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ToolUsage
        fields = ["id", "tool", "file_count", "input_bytes", "output_bytes", "created_at"]
