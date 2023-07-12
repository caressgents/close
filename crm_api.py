import requests
import logging
from config import CRM_API_KEY, CRM_API_URL, CRM_PHONE_NUMBER

# Set up logging
logger = logging.getLogger(__name__)

def get_unread_messages():
    url = f"{CRM_API_URL}/activity/sms/"

    headers = {
        "Authorization": f"Bearer {CRM_API_KEY}",
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch messages: {e}")
        return []

    return response.json()

def get_lead_data(lead_id):
    url = f"{CRM_API_URL}/lead/{lead_id}"

    headers = {
        "Authorization": f"Bearer {CRM_API_KEY}",
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch lead data: {e}")
        return None

    return response.json()

def send_message(lead_id, message):
    url = f"{CRM_API_URL}/activity/sms/"

    headers = {
        "Authorization": f"Bearer {CRM_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "lead_id": lead_id,
        "text": message,
        "status": "outbox",  # to send the SMS immediately
        "local_phone": CRM_PHONE_NUMBER  # the CRM's built-in number
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to send message: {e}")
        return False

    return True

