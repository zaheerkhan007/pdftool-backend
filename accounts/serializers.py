from django.contrib.auth.models import User
from rest_framework import serializers

from .models import ToolUsage


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            password=validated_data["password"],
        )


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "date_joined"]


class ToolUsageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ToolUsage
        fields = ["id", "tool", "file_count", "input_bytes", "output_bytes", "created_at"]
