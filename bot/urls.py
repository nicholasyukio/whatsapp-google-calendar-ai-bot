from django.urls import path
from .views import whatsapp_webhook, telegram_webhook, home

urlpatterns = [
    path('', home, name='home'),
    path('whatsapp/', whatsapp_webhook, name='whatsapp_webhook'),
    path("telegram/", telegram_webhook, name="telegram_webhook"),
]
