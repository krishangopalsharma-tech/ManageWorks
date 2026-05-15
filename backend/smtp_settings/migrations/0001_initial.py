from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='SmtpConfig',
            fields=[
                ('id',            models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('host',          models.CharField(default='smtp.gmail.com', max_length=255)),
                ('port',          models.PositiveIntegerField(default=587)),
                ('use_tls',       models.BooleanField(default=True)),
                ('host_user',     models.EmailField(default='adimanageworks@gmail.com', max_length=255)),
                ('host_password', models.CharField(blank=True, default='', max_length=255)),
                ('from_email',    models.EmailField(default='adimanageworks@gmail.com', max_length=255)),
                ('updated_at',    models.DateTimeField(auto_now=True)),
            ],
            options={'verbose_name': 'SMTP Configuration'},
        ),
    ]
