from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('works', '0006_work_extension_bill'),
    ]

    operations = [
        # WorkItem: track execution progress separately from supply
        migrations.AddField(
            model_name='workitem',
            name='executed_quantity',
            field=models.FloatField(blank=True, default=0, null=True),
        ),
        # WorkItemEntry: differentiate supply vs execution lots
        migrations.AddField(
            model_name='workitementry',
            name='entry_type',
            field=models.CharField(
                choices=[('supply', 'Supply'), ('execution', 'Execution')],
                default='supply',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='workitementry',
            name='location',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='workitementry',
            name='remarks',
            field=models.TextField(blank=True, null=True),
        ),
    ]
