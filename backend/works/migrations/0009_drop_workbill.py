from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('works', '0008_workitementry_date_of_inspection_and_more'),
    ]

    operations = [
        migrations.DeleteModel(
            name='WorkBill',
        ),
    ]
