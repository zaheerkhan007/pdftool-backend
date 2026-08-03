from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

User = get_user_model()


class EmailBackend(ModelBackend):
    """
    Authenticate with an email address instead of a username.

    We keep Django's stock User model rather than swapping in a custom one —
    AUTH_USER_MODEL cannot be changed once a project has migrated data, and this
    one already has. So `username` still exists (auto-derived from the email at
    signup) and stays the primary key users never see.

    ModelBackend is left enabled alongside this one so existing superusers can
    still sign into /admin/ with their username.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        # SimpleJWT passes the identifier as `email`; the admin login form and
        # anything calling authenticate() positionally passes it as `username`.
        email = kwargs.get("email") or username
        if not email or not password:
            return None
        email = email.strip()

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # Run the hasher anyway so a missing account takes the same time as
            # a wrong password — otherwise response timing leaks which emails
            # are registered.
            User().set_password(password)
            return None
        except User.MultipleObjectsReturned:
            # Only reachable for duplicate emails created before the unique
            # index in migration 0002. Oldest account wins, deterministically.
            user = User.objects.filter(email__iexact=email).order_by("pk").first()

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
