from django.db import migrations, models


def migrate_roles(apps, schema_editor):
    UserProfile = apps.get_model('users', 'UserProfile')
    UserProfile.objects.filter(role__in=['user', 'observer']).update(role='consignee')


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(migrate_roles, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='userprofile',
            name='role',
            field=models.CharField(
                choices=[('consignee', 'Consignee'), ('admin', 'Admin')],
                default='consignee',
                max_length=20,
            ),
        ),
    ]
