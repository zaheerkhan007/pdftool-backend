from django.conf import settings
from django.db import migrations

# Django's stock User.email has no unique constraint, which would let two
# accounts share an address and make email login ambiguous. We cannot alter
# another app's model from here, so enforce it with an index instead.
#
# LOWER(email) because logins are case-insensitive; the partial WHERE clause
# exempts accounts with no email (superusers created via createsuperuser
# without one). Both SQLite and Postgres support expression + partial indexes.
CREATE_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS accounts_auth_user_email_ci_uniq
ON auth_user (LOWER(email))
WHERE email <> '';
"""

DROP_INDEX = "DROP INDEX IF EXISTS accounts_auth_user_email_ci_uniq;"


def fail_on_existing_duplicates(apps, schema_editor):
    """
    Creating the index blows up with a confusing database error if duplicate
    emails already exist. Check first and raise something actionable.
    """
    User = apps.get_model("auth", "User")
    seen, dupes = set(), set()
    for email in User.objects.exclude(email="").values_list("email", flat=True):
        key = email.lower()
        if key in seen:
            dupes.add(key)
        seen.add(key)
    if dupes:
        raise RuntimeError(
            "Cannot enforce unique emails — these are used by more than one "
            f"account: {', '.join(sorted(dupes))}. Merge or clear the duplicates "
            "in /admin/, then re-run migrate."
        )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            fail_on_existing_duplicates, migrations.RunPython.noop, elidable=False
        ),
        migrations.RunSQL(CREATE_INDEX, DROP_INDEX),
    ]
