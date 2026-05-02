from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('works', '0010_add_name_of_work'),
    ]

    operations = [
        migrations.AddField(
            model_name='workitementry',
            name='receive_note_no',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='workitementry',
            name='date_of_receipt',
            field=models.DateField(blank=True, null=True),
        ),
    ]
