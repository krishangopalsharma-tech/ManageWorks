from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('works', '0012_add_hrms_id_and_inspection_agency'),
    ]

    operations = [
        migrations.AddField(
            model_name='workitem',
            name='category',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
