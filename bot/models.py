from django.db import models

class MeetingSlot(models.Model):
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=10)  # 'available', 'booked', etc.