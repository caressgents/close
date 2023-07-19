import requests
from requests.auth import HTTPBasicAuth
import logging
from config import CRM_API_KEY, CRM_API_URL
import phonenumbers
import sys

# Define a Handler which writes INFO messages or higher to the sys.stderr (this could be your console)
console = logging.StreamHandler(sys.stderr)
console.setLevel(logging.INFO)

# Define a Handler for the log file
file_handler = logging.FileHandler('app.log')
file_handler.setLevel(logging.DEBUG)

# Set a format which is simpler for console use
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')

# Tell the handler to use this format
console.setFormatter(formatter)
file_handler.setFormatter(formatter)

logging.basicConfig(
    level=logging.DEBUG,
    handlers=[file_handler, console]
)


class CRMAPI:
    def __init__(self):
        self.auth = HTTPBasicAuth(CRM_API_KEY, ' ')
        self.base_url = CRM_API_URL

    def log_response(self, response):
        logging.info(f"Response status code: {response.status_code}")
        logging.info(f"Response content: RECEIVED")

    def update_task_status(self, task_id):
        logging.debug(f"Updating task status for task ID: {task_id}")
        url = f'{self.base_url}/task/{task_id}/'
        data = {
            'is_complete': True
        }
        response = requests.put(url, json=data, auth=self.auth)
        self.log_response(response)
        if response.status_code == 200:
            logging.info(f"Task {task_id} marked as complete.")
            return True
        else:
            logging.error(f"Failed to update task status for task_id {task_id}: {response.text}")
            return False

    def get_unresponded_incoming_sms_tasks(self):
        logging.debug("Fetching unresponded incoming SMS tasks...")
        url = f'{self.base_url}/activity/sms/'
        query = {'direction': 'inbound'}
        response = requests.get(url, params=query, auth=self.auth)
        self.log_response(response)
        if response.status_code == 200:
            all_incoming_sms = response.json()['data']
            unresponded_sms_tasks = []
            with open('processed_tasks.txt', 'r') as file:
                processed_tasks = file.read().splitlines()
            for sms in all_incoming_sms:
                if sms['id'] in processed_tasks:
                    continue
                lead_id = sms['lead_id']
                latest_outgoing_sms = self.get_latest_outgoing_sms(lead_id)
                if latest_outgoing_sms is None or sms['date_created'] > latest_outgoing_sms['date_created']:
                    unresponded_sms_tasks.append(sms)
            return unresponded_sms_tasks
        else:
            logging.error(f"Failed to get unresponded incoming SMS tasks: {response.text}")
            return []

    def get_lead_data(self, lead_id):
        logging.debug(f"Fetching lead data for lead ID: {lead_id}")
        logging.info(f"Getting lead data for lead_id {lead_id}")
        url = f'{self.base_url}/lead/{lead_id}'
        response = requests.get(url, auth=self.auth)
        self.log_response(response)
        if response.status_code == 200:
            lead_data = response.json()
            logging.info(f"Received lead data for lead_id {lead_id}")
            lead_data['contacts'] = self.get_contacts(lead_id)
            return lead_data
        else:
            logging.error(f"Failed to get lead data for lead_id {lead_id}: {response.text}")
            return None

    def get_contacts(self, lead_id):
        logging.debug(f"Fetching contacts for lead ID: {lead_id}")
        logging.info(f"Getting contacts for lead_id {lead_id}")
        url = f'{self.base_url}/contact/?lead_id={lead_id}'
        response = requests.get(url, auth=self.auth)
        self.log_response(response)
        if response.status_code == 200:
            return response.json()['data']
        else:
            logging.error(f"Failed to get contacts for lead_id {lead_id}: {response.text}")
            return None

    def get_lead_notes(self, lead_id):
        logging.debug(f"Fetching lead notes for lead ID: {lead_id}")
        logging.info(f"Getting lead notes for lead_id {lead_id}")
        url = f'{self.base_url}/activity/note/?lead_id={lead_id}'
        response = requests.get(url, auth=self.auth)
        self.log_response(response)
        if response.status_code == 200:
            return response.json()['data']
        else:
            logging.error(f"Failed to get lead notes for lead_id {lead_id}: {response.text}")
            return None

    def get_latest_incoming_sms(self, lead_id):
        logging.debug(f"Fetching latest incoming SMS for lead ID: {lead_id}")
        try:
            logging.info(f"Getting latest incoming SMS for lead_id {lead_id}")
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

    def get_latest_outgoing_sms(self, lead_id):
        logging.debug(f"Fetching latest outgoing SMS for lead ID: {lead_id}")
        try:
            logging.info(f"Getting latest outgoing SMS for lead_id {lead_id}")
            url = f"{self.base_url}/activity/sms/?lead_id={lead_id}"
            response = requests.get(url, auth=self.auth)
            if response.status_code == 200:
                activities = response.json()["data"]
                outgoing_sms = [sms for sms in activities if sms["direction"] == "outbound"]
                if outgoing_sms:
                    latest_sms = max(outgoing_sms, key=lambda sms: sms["date_created"])
                    return latest_sms
            else:
                logging.error(f"Failed to get latest outgoing SMS for lead_id {lead_id}: {response.status_code} {response.text}")
                return None
        except Exception as e:
            logging.exception(f"Failed to get latest outgoing SMS for lead_id {lead_id}")
            return None

    def send_message(self, lead_id, message, task_id, template_id):
        logging.debug(f"Preparing to send message for lead ID: {lead_id}")
        logging.info(f"Attempting to send message for lead_id {lead_id}")
        # Get lead data
        lead_data = self.get_lead_data(lead_id)
        if not lead_data:
            logging.error(f"No data for lead_id {lead_id}")
            return False

        # Get remote phone number
        remote_phone = lead_data['contacts'][0]['phones'][0]['phone']

        # Log the remote_phone value
        logging.info(f"Remote phone number for lead_id {lead_id}: {remote_phone}")

        # Parse phone number
        try:
            parsed_phone = phonenumbers.parse(remote_phone, 'US')
        except phonenumbers.phonenumberutil.NumberParseException as e:
            logging.error(f"Failed to parse phone number for lead_id {lead_id}: {e}")
            return False

        # Prepare data
        data = {
            'lead_id': lead_id,
            'status': 'outbox',
            'direction': 'outbound',
            'related_to': task_id,
            'template_id': template_id,
            'local_phone': '+19042994707',
            'remote_phone': remote_phone
        }

        logging.info(f"Prepared data for sending message: {data}")

        # Send the request to CRM API
        url = f'{self.base_url}/activity/sms/'
        response = requests.post(url, json=data, auth=self.auth)
        self.log_response(response)

        if response.status_code in {200, 201}:
            logging.info(f"Message sent successfully for lead_id {lead_id}")
            return True
        else:
            logging.error(f"Failed to send message for lead_id {lead_id}: {response.text}")
            return False

    def mark_task_as_complete(self, task_id):
        logging.debug(f"Marking task as complete for task ID: {task_id}")
        logging.info(f"Marking task as complete for task_id {task_id}")
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
        logging.debug(f"Updating lead status for lead ID: {lead_id}")
        logging.info(f"Updating lead status for lead_id {lead_id}")
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
        logging.debug("Fetching SMS templates...")
        logging.info("Getting SMS templates")
        url = f'{self.base_url}/sms_template/'
        response = requests.get(url, auth=self.auth)
        self.log_response(response)
        if response.status_code == 200:
            return response.json()['data']
        else:
            logging.error(f"Failed to get SMS templates: {response.text}")
            return None

    def get_leads_with_specific_statuses(self, specific_statuses):
        logging.debug("Fetching all leads with specific statuses...")
        status_ids = ','.join(specific_statuses)
        base_url = f'{self.base_url}/opportunity/'
        lead_ids = []
        limit = 100  # Fetch 100 records at a time as per the API's documentation
        skip = 0  # Start with the first record

        while True:
            query = {'status_id__in': status_ids, '_limit': limit, '_skip': skip}
            url = f'{base_url}'
            response = requests.get(url, params=query, auth=self.auth)
            self.log_response(response)
            if response.status_code == 200:
                opportunities = response.json()['data']
                lead_ids.extend([opp['lead_id'] for opp in opportunities])

                if not response.json().get('has_more'):  # If there's no more data, stop fetching
                    break
                else:
                    skip += limit  # Otherwise, move to the next page of data
            else:
                logging.error(f"Failed to fetch leads with specific statuses: {response.text}")
                break

        logging.info(f"Fetched {len(lead_ids)} leads with the specific statuses.")
        return lead_ids
