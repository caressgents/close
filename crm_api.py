import requests

CRM_API_KEY = "CRM_API_GOES_HERE"
CRM_API_URL = "https://api.close.com/api/v1/"

def get_unread_messages():
    url = f"{CRM_API_URL}/activity/sms/"

    headers = {
        "Authorization": f"Bearer {CRM_API_KEY}",
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise Exception(f"Failed to fetch messages: {response.text}")

    return response.json()

def get_lead_data(lead_id):
    url = f"{CRM_API_URL}/lead/{lead_id}"

    headers = {
        "Authorization": f"Bearer {CRM_API_KEY}",
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise Exception(f"Failed to fetch lead data: {response.text}")

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
        "local_phone": "INPUT_CRM_SMS_#_HERE"  # the CRM's built-in number
    }

    response = requests.post(url, headers=headers, json=data)

    if response.status_code != 201:
        raise Exception(f"Failed to send message: {response.text}")

    return response.json()
