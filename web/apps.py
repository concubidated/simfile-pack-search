"""web app config"""
from django.apps import AppConfig


class WebConfig(AppConfig):
    """Web config"""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'web'
