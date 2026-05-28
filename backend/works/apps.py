from django.apps import AppConfig


class WorksConfig(AppConfig):
    name = 'works'

    def ready(self):
        import works.signals  # noqa: F401
