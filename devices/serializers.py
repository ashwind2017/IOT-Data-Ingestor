from rest_framework import serializers


class PayloadInputSerializer(serializers.Serializer):
    fCnt = serializers.IntegerField(min_value=0)
    devEUI = serializers.CharField(max_length=64)
    data = serializers.CharField(allow_blank=False)
    rxInfo = serializers.ListField(required=False, default=list)
    txInfo = serializers.DictField(required=False, default=dict)
