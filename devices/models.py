from django.db import models


class Device(models.Model):
    devEUI = models.CharField(max_length=64, unique=True)
    latest_status = models.CharField(max_length=16, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.devEUI


class Payload(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='payloads')
    fCnt = models.PositiveIntegerField()
    data_hex = models.CharField(max_length=512)
    status = models.CharField(max_length=16)
    rx_info = models.JSONField(default=list, blank=True)
    tx_info = models.JSONField(default=dict, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('device', 'fCnt')
        ordering = ['-received_at']

    def __str__(self):
        return f'{self.device.devEUI} fCnt={self.fCnt}'
