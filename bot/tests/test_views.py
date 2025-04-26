from django.test import TestCase
from django.urls import reverse

class AvailableSlotsTest(TestCase):
    def test_get_available_slots(self):
        # Hit the API endpoint to fetch available slots
        response = self.client.get(reverse('available_slots'))

        # Check if the response is successful (status code 200)
        self.assertEqual(response.status_code, 200)

        # Optionally, you can add more assertions depending on the structure
        # For example, check if the response contains a list
        self.assertIsInstance(response.json(), list)
