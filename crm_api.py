import requests
from requests.auth import HTTPBasicAuth
import logging
from config import CRM_API_KEY, CRM_API_URL

logging.basicConfig(filename='app.log', level=logging.INFO)

class CRMAPI:
    def __init__(self):
        self.auth = HTTPBasicAuth(CRM_API_KEY, ' ')

    def get_unprocessed_incoming_sms_tasks(self):
        url = f'{CRM_API_URL}/task?_type=incoming_sms&is_complete=false'
        response = requests.get(url, auth=self.auth)
        if response.status_code == 200:
            return response.json()['data']
        else:
            logging.error(f"Failed to get unprocessed incoming SMS tasks: {response.text}")
            return []

    def get_lead_data(self, lead_id):
        url = f'{CRM_API_URL}/lead/{lead_id}'
        response = requests.get(url, auth=self.auth)
        if response.status_code == 200:
            lead_data = response.json()
            logging.info(f"Received lead data for lead_id {lead_id}: {lead_data}")
            return lead_data
        else:
            logging.error(f"Failed to get lead data for lead_id {lead_id}: {response.text}")
            return None

    def get_lead_notes(self, lead_id):
        url = f'{CRM_API_URL}/activity/note/?lead_id={lead_id}'
        response = requests.get(url, auth=self.auth)
        if response.status_code == 200:
            return response.json()['data']
        else:
            logging.error(f"Failed to get lead notes for lead_id {lead_id}: {response.text}")
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
        if response.status_code == 201:
            return True
        else:
            logging.error(f"Failed to send message for lead_id {lead_id}: {response.text}")
            return False

    def mark_task_as_complete(self, task_id):
        url = f'{CRM_API_URL}/task/{task_id}'
        data = {
            'is_complete': True
        }
        response = requests.put(url, json=data, auth=self.auth)
        if response.status_code == 200:
            return True
        else:
            logging.error(f"Failed to mark task as complete for task_id {task_id}: {response.text}")
            return False

    def update_lead_status(self, lead_id, status):
        url = f'{CRM_API_URL}/lead/{lead_id}'
        data = {
            'status_label': status
        }
        response = requests.put(url, json=data, auth=self.auth)
        if response.status_code == 200:
            return True
        else:
            logging.error(f"Failed to update lead status for lead_id {lead_id}: {response.text}")
            return False

    def get_sms_templates(self):
        url = f'{CRM_API_URL}/sms_template/'
        response = requests.get(url, auth=self.auth)
        if response.status_code == 200:
            return response.json()['data']
        else:
            logging.error(f"Failed to get SMS templates: {response.text}")
            return None
