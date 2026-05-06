from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('mb_details', '0003_add_measurement_date'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='mbitem',
            name='prior_percentage',
        ),
    ]
