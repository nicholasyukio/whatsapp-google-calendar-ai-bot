from django.urls import path
from .views import whatsapp_webhook, get_available_slots
from .whatsapp.webhook import webhook as new_webhook

urlpatterns = [
    path('whatsapp/', whatsapp_webhook, name='whatsapp_webhook'),
    path('webhook/', new_webhook, name='new_webhook'),
    path('available_slots/', get_available_slots, name='available_slots'),
]
