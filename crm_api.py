import requests
from requests.auth import HTTPBasicAuth
import logging
from config import CRM_API_KEY, CRM_API_URL

logging.basicConfig(filename='app.log', level=logging.INFO, format='%(levelname)s - %(message)s')

class CRMAPI:
    def __init__(self):
        self.auth = HTTPBasicAuth(CRM_API_KEY, ' ')
        self.base_url = CRM_API_URL

    def log_response(self, response):
        logging.info(f"Response status code: {response.status_code}")
        logging.info(f"Response content: {response.text}")

    def get_unprocessed_incoming_sms_tasks(self):
        filter_date = '2023-06-01'
        url = f'{self.base_url}/task?_type=incoming_sms&is_complete=false&date_created__gt={filter_date}'
        response = requests.get(url, auth=self.auth)
        self.log_response(response)
        if response.status_code == 200:
            return response.json()['data']
        else:
            logging.error(f"Failed to get unprocessed incoming SMS tasks: {response.text}")
            return []

    def get_lead_data(self, lead_id):
        url = f'{self.base_url}/lead/{lead_id}'
        response = requests.get(url, auth=self.auth)
        self.log_response(response)
        if response.status_code == 200:
            lead_data = response.json()
            logging.info(f"Received lead data for lead_id {lead_id}: {lead_data}")
            return lead_data
        else:
            logging.error(f"Failed to get lead data for lead_id {lead_id}: {response.text}")
            return None

    def get_lead_notes(self, lead_id):
        url = f'{self.base_url}/activity/note/?lead_id={lead_id}'
        response = requests.get(url, auth=self.auth)
        self.log_response(response)
        if response.status_code == 200:
            return response.json()['data']
        else:
            logging.error(f"Failed to get lead notes for lead_id {lead_id}: {response.text}")
            return None

    def get_latest_incoming_sms(self, lead_id):
        try:
            url = f"{self.base_url}/activity/sms/?lead_id={lead_id}"
            response = requests.get(url, auth=self.auth)
            if response.status_code == 200:
                activities = response.json()["data"]
                incoming_sms = [sms for sms in activities if sms["direction"] == "inbound"]
                if incoming_sms:
                    latest_sms = max(incoming_sms, key=lambda sms: sms["date_created"])
                    return latest_sms
            else:
                logging.error(f"Failed to get latest incoming SMS for lead_id {lead_id}: {response.status_code} {response.text}")
                return None
        except Exception as e:
            logging.exception(f"Failed to get latest incoming SMS for lead_id {lead_id}")
            return None

    def send_message(self, lead_id, message, task_id, template_id):
        url = f'{self.base_url}/activity/sms'
        data = {
            'lead_id': lead_id,
            'text': message,
            'status': 'outbox',
            'direction': 'outbound',
            'related_to': task_id,
            'template_id': template_id
        }
        response = requests.post(url, json=data, auth=self.auth)
        self.log_response(response)
        if response.status_code == 201:
            return True
        else:
            logging.error(f"Failed to send message for lead_id {lead_id}: {response.text}")
            return False

    def mark_task_as_complete(self, task_id):
        url = f'{self.base_url}/task/{task_id}'
        data = {
            'is_complete': True
        }
        response = requests.put(url, json=data, auth=self.auth)
        self.log_response(response)
        if response.status_code == 200:
            return True
        else:
            logging.error(f"Failed to mark task as complete for task_id {task_id}: {response.text}")
            return False

    def update_lead_status(self, lead_id, status_id):
        url = f'{self.base_url}/lead/{lead_id}'
        data = {
            'status_id': status_id
        }
        response = requests.put(url, json=data, auth=self.auth)
        self.log_response(response)
        if response.status_code == 200:
            return True
        else:
            logging.error(f"Failed to update lead status for lead_id {lead_id}: {response.text}")
            return False

    def get_sms_templates(self):
        url = f'{self.base_url}/sms_template/'
        response = requests.get(url, auth=self.auth)
        self.log_response(response)
        if response.status_code == 200:
            return response.json()['data']
        else:
            logging.error(f"Failed to get SMS templates: {response.text}")
            return None
