from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_migrate_roles_to_consignee_admin'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='plain_password',
            field=models.CharField(blank=True, default='', max_length=128),
        ),
    ]
