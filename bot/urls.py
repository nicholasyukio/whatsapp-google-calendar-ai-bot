from django.urls import path
from .views import whatsapp_webhook, home

urlpatterns = [
    path('', home, name='home'),
    path('whatsapp/', whatsapp_webhook, name='whatsapp_webhook'),
]
