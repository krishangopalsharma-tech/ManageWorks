from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('site_register', '0009_att_serial'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteregisterthread',
            name='location',
            field=models.CharField(blank=True, default='', max_length=300),
        ),
    ]
