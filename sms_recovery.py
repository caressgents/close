import os
import requests
import logging
import csv
from datetime import datetime, timedelta
from openai_api import generate_response
from config import CRM_API_KEY, CRM_API_URL, CRM_PHONE_NUMBER

# Load system prompt manually
PROMPT_PATH = 'system_prompt.txt'
try:
    with open(PROMPT_PATH, 'r') as pf:
        SYSTEM_PROMPT = pf.read()
except Exception as e:
    print(f"❌ Failed to load system prompt: {e}")
    SYSTEM_PROMPT = ""

# Setup logger
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

auth = (CRM_API_KEY, '')
base_url = CRM_API_URL
LOG_FILE = 'ai_sms_log.csv'

# Ensure CSV has header
if not os.path.isfile(LOG_FILE):
    with open(LOG_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'source', 'lead_id', 'contact_id', 'contact_name', 'message_text'])

def fetch_recent_inbound_sms(hours=48):
    url = f"{base_url}/activity/sms/"
    after_date = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    params = {
        "direction": "inbound",
        "date_created__gte": after_date,
        "_limit": 100
    }
    results = []
    skip = 0
    while True:
        params["_skip"] = skip
        resp = requests.get(url, params=params, auth=auth)
        data = resp.json().get("data", [])
        if not data:
            break
        results.extend(data)
        if len(data) < 100:
            break
        skip += 100
    return results

def get_task_for_sms(sms_id, lead_id):
    url = f"{base_url}/task/"
    params = {
        "_type": "incoming_sms",
        "lead_id": lead_id,
        "is_complete": "false",
        "_limit": 100
    }
    resp = requests.get(url, params=params, auth=auth)
    for task in resp.json().get("data", []):
        if task.get("object_id") == sms_id:
            return task["id"]
    return None

def get_thread(lead_id, contact_id):
    url = f"{base_url}/activity/sms/"
    params = {
        "lead_id": lead_id,
        "contact_id": contact_id,
        "_limit": 100
    }
    resp = requests.get(url, auth=auth, params=params)
    return resp.json().get("data", [])

def get_contact_phone(contact_id):
    url = f"{base_url}/contact/{contact_id}/"
    resp = requests.get(url, auth=auth)
    if resp.status_code == 200:
        phones = resp.json().get("phones", [])
        if phones:
            return phones[0]["phone"]
    return None

def get_lead_id(contact_id):
    url = f"{base_url}/contact/{contact_id}/"
    resp = requests.get(url, auth=auth)
    return resp.json().get("lead_id") if resp.status_code == 200 else None

def get_lead_name(contact_id):
    url = f"{base_url}/contact/{contact_id}/"
    resp = requests.get(url, auth=auth)
    if resp.status_code == 200:
        lead_id = resp.json().get("lead_id")
        if lead_id:
            lead_url = f"{base_url}/lead/{lead_id}/"
            r2 = requests.get(lead_url, auth=auth)
            return r2.json().get("display_name") if r2.status_code == 200 else None
    return "Unknown"

def send_sms(contact_id, lead_id, text, remote_phone):
    """
    Send outbound SMS via Close API with correct payload and log to CSV.
    """
    url = f"{base_url}/activity/sms/"
    payload = {
        "lead_id": lead_id,
        "contact_id": contact_id,
        "local_phone": CRM_PHONE_NUMBER,
        "remote_phone": remote_phone,
        "text": text,
        "status": "outbox"
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, json=payload, auth=auth, headers=headers)

    if response.status_code == 200:
        # Fetch contact name for logging
        try:
            c_resp = requests.get(f"{base_url}/contact/{contact_id}/", auth=auth, timeout=10)
            c_resp.raise_for_status()
            contact_name = c_resp.json().get('name', '')
        except Exception:
            contact_name = ''

        # Log to CSV
        timestamp = datetime.utcnow().isoformat()
        with open(LOG_FILE, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, 'sms_recovery', lead_id, contact_id, contact_name, text])

        logging.info(f"📤 SMS logged for {contact_name} (lead: {lead_id})")
        return True
    else:
        logging.error(f"❌ SMS failed ({response.status_code}): {response.text}")
        return False


def main():
    messages = fetch_recent_inbound_sms()
    logging.info(f"Found {len(messages)} inbound SMS from the last 24h.")
    for msg in messages:
        sms_id = msg.get("id")
        cid = msg.get("contact_id")
        if not cid or not sms_id:
            continue
        lid = get_lead_id(cid)
        if not lid:
            continue
        thread = get_thread(lid, cid)
        if not thread:
            continue
        thread = sorted(thread, key=lambda m: m.get('activity_at') or m.get('date_created'))
        last = thread[-1]
        if last.get("direction") == "outbound":
            logging.info(f"⏭️ Already replied to {sms_id}, skipping.")
            continue
        convo = []
        for m in thread:
            txt = (m.get("text") or "").strip()
            if not txt:
                continue
            speaker = "Lead" if m.get("direction") == "inbound" else "Agent"
            convo.append(f"{speaker}: {txt}")
        history = "\n".join(convo)
        first_name = get_lead_name(cid).split()[0]
        prompt = f"Lead First Name: {first_name}\nConversation:\n{history}\n\nRespond to the lead’s last message naturally and helpfully."

        reply = generate_response(SYSTEM_PROMPT, prompt)
        logging.info(f"✅ OpenAI reply: {reply}")
        logging.info(f"💬 {sms_id} AI reply: {reply}")

        remote_phone = get_contact_phone(cid)
        if not remote_phone:
            logging.error(f"❌ Missing remote_phone for {get_lead_name(cid)} ({cid})")
            continue

        success = send_sms(cid, lid, reply, remote_phone)
        if success:
            logging.info(f"📤 SMS sent to {get_lead_name(cid)}")
        else:
            logging.error(f"❌ Failed to send SMS to {get_lead_name(cid)} ({cid})")

if __name__ == "__main__":
    main()
