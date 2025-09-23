from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


class DownloadChatMarkdownTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="tester", password="pass")
        self.client = APIClient()
        self.client.login(username="tester", password="pass")

    def test_download_returns_markdown(self):
        messages = [
            {"sender": "user", "text": "Hello", "createdAt": 1600000000000},
            {"sender": "assistant", "text": "Hi there", "createdAt": 1600000005000},
        ]
        resp = self.client.post('/api/core/download-chat-md/', {"messages": messages}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/markdown', resp['Content-Type'])
        self.assertIn('# Chat history', resp.content.decode('utf-8'))
