from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0007_user_role_operation")]

    operations = [
        migrations.AddField(model_name="user", name="line_user_id", field=models.CharField(blank=True, max_length=80, null=True, unique=True)),
        migrations.AddField(model_name="user", name="line_display_name", field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name="user", name="line_picture_url", field=models.URLField(blank=True)),
        migrations.AddField(model_name="user", name="line_connected_at", field=models.DateTimeField(blank=True, null=True)),
    ]
