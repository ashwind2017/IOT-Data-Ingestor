from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Device, Payload


def base_payload(**overrides):
    body = {
        'fCnt': 100,
        'devEUI': 'abcdabcdabcdabcd',
        'data': 'AQ==',
        'rxInfo': [{'gatewayID': 'g1', 'rssi': -57, 'loRaSNR': 10}],
        'txInfo': {'frequency': 86810000, 'dr': 5},
    }
    body.update(overrides)
    return body


class PayloadEndpointTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='x')
        self.token = Token.objects.create(user=self.user)
        self.url = reverse('create_payload')
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

    def test_creates_payload_and_device(self):
        res = self.client.post(self.url, base_payload(), format='json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['status'], 'passing')
        self.assertEqual(Device.objects.count(), 1)
        self.assertEqual(Payload.objects.count(), 1)

    def test_passing_when_value_is_one(self):
        res = self.client.post(self.url, base_payload(data='AQ=='), format='json')
        self.assertEqual(res.data['status'], 'passing')

    def test_failing_when_value_is_not_one(self):
        res = self.client.post(self.url, base_payload(data='Ag=='), format='json')
        self.assertEqual(res.data['status'], 'failing')

    def test_duplicate_fcnt_for_same_device_rejected(self):
        self.client.post(self.url, base_payload(fCnt=5), format='json')
        res = self.client.post(self.url, base_payload(fCnt=5), format='json')
        self.assertEqual(res.status_code, 409)

    def test_same_fcnt_different_devices_both_accepted(self):
        a = self.client.post(self.url, base_payload(devEUI='aaaa', fCnt=1), format='json')
        b = self.client.post(self.url, base_payload(devEUI='bbbb', fCnt=1), format='json')
        self.assertEqual(a.status_code, 201)
        self.assertEqual(b.status_code, 201)

    def test_missing_token_returns_401(self):
        self.client.credentials()
        res = self.client.post(self.url, base_payload(), format='json')
        self.assertEqual(res.status_code, 401)

    def test_latest_status_updates_on_device(self):
        self.client.post(self.url, base_payload(fCnt=1, data='AQ=='), format='json')
        device = Device.objects.get(devEUI='abcdabcdabcdabcd')
        self.assertEqual(device.latest_status, 'passing')

        self.client.post(self.url, base_payload(fCnt=2, data='Ag=='), format='json')
        device.refresh_from_db()
        self.assertEqual(device.latest_status, 'failing')

    def test_invalid_base64_returns_400(self):
        res = self.client.post(self.url, base_payload(data='not!!base64'), format='json')
        self.assertEqual(res.status_code, 400)

    def test_missing_required_field_returns_400(self):
        body = base_payload()
        del body['devEUI']
        res = self.client.post(self.url, body, format='json')
        self.assertEqual(res.status_code, 400)
