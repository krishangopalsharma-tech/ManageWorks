from django.db import models


class TelegramBotConfig(models.Model):
    bot_token            = models.CharField(max_length=500, blank=True, default='')
    upload_group_chat_id = models.CharField(max_length=100, blank=True, default='')
    is_active            = models.BooleanField(default=False)
    updated_at           = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Telegram Bot Configuration'

    def __str__(self):
        return f'Telegram Bot (active={self.is_active})'
