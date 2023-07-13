import requests
import logging
from config import CRM_API_KEY, CRM_API_URL, CRM_PHONE_NUMBER
from requests.auth import HTTPBasicAuth

# Set up logging
logger = logging.getLogger(__name__)

auth = HTTPBasicAuth(CRM_API_KEY, '')

def get_unread_messages():
    url = f"{CRM_API_URL}/activity/sms/unread"

    try:
        response = requests.get(url, auth=auth)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to get unread messages: {e}")
        return []

    # Ensure the response is a list of dictionaries
    try:
        messages = response.json()
        if isinstance(messages, list) and all(isinstance(msg, dict) for msg in messages):
            return messages
    except ValueError:
        pass

    logger.error(f"Unexpected response format from get_unread_messages: {response.text}")
    return []

def get_lead_data(lead_id):
    url = f"{CRM_API_URL}/lead/{lead_id}"

    try:
        response = requests.get(url, auth=auth)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch lead data: {e}")
        return None

    return response.json()

def send_message(lead_id, message, message_id):
    url = f"{CRM_API_URL}/activity/sms/"

    headers = {
        "Content-Type": "application/json"
    }

    data = {
        "lead_id": lead_id,
        "text": message,
        "status": "outbox",  # to send the SMS immediately
        "local_phone": CRM_PHONE_NUMBER,  # the CRM's built-in number
        "message_id": message_id  # the ID of the message being responded to
    }

    try:
        response = requests.post(url, auth=auth, headers=headers, data=json.dumps(data))
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to send message: {e}")
        return False

    return True
