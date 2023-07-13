import requests
from requests.auth import HTTPBasicAuth
import logging
from config import CRM_API_KEY, CRM_API_URL

logging.basicConfig(filename='app.log', level=logging.INFO)

class CRMAPI:
    def __init__(self):
        self.auth = HTTPBasicAuth(CRM_API_KEY, ' ')

    def get_unread_messages(self):
        url = f'{CRM_API_URL}/task?_type=incoming_sms&is_complete=false'
        response = requests.get(url, auth=self.auth)
        if response.status_code == 200:
            return response.json()['data']
        else:
            logging.error(f"Failed to get unread messages: {response.text}")
            return []

    def get_lead_data(self, lead_id):
        url = f'{CRM_API_URL}/lead/{lead_id}'
        response = requests.get(url, auth=self.auth)
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f"Failed to get lead data: {response.text}")
            return None

    def send_message(self, lead_id, message, message_id):
        url = f'{CRM_API_URL}/activity/sms'
        data = {
            'lead_id': lead_id,
            'text': message,
            'status': 'outbox',
            'direction': 'outbound',
            'related_to': message_id
        }
        response = requests.post(url, json=data, auth=self.auth)
        return response.status_code == 201

    def mark_task_as_complete(self, task_id):
        url = f'{CRM_API_URL}/task/{task_id}'
        data = {
            'is_complete': True
        }
        response = requests.put(url, json=data, auth=self.auth)
        return response.status_code == 200

    def update_lead_status(self, lead_id, status):
        url = f'{CRM_API_URL}/lead/{lead_id}'
        data = {
            'status_label': status
        }
        response = requests.put(url, json=data, auth=self.auth)
        return response.status_code == 200
