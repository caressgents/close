# crm_api.py

import requests
from requests.auth import HTTPBasicAuth
import logging
import time
from config import CRM_API_KEY, CRM_API_URL, CRM_PHONE_NUMBER
from datetime import datetime, timedelta

logger = logging.getLogger("crm_api")

class CRMAPI:
    def __init__(self):
        self.auth = HTTPBasicAuth(CRM_API_KEY, "")
        self.base_url = CRM_API_URL

    def iter_open_sms_tasks(self, limit=100):
        """
        Yield (tasks, total_results) pages of open incoming_sms tasks
        so the bot processes every inbox item exactly once.
        """
        skip = 0
        total = None
        while True:
            params = {
                "_limit": limit,
                "_skip": skip,
                "is_complete": "false",
                "_type": "incoming_sms"
            }
            url = f"{self.base_url}/task/"
            resp = requests.get(url, params=params, auth=self.auth, timeout=30)
            resp.raise_for_status()
            body = resp.json()
            tasks = body.get("data", [])
            if total is None:
                total = body.get("total_results", len(tasks))
            yield tasks, total
            if not body.get("has_more", False):
                break
            skip += limit

    def get_sms_activity(self, sms_id):
        """Fetch a single SMS activity by its ID."""
        url = f"{self.base_url}/activity/sms/{sms_id}/"
        resp = requests.get(url, auth=self.auth, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        return None

    def find_task_for_sms(self, sms_id, lead_id):
        """Locate the open incoming_sms task for this SMS."""
        url = f"{self.base_url}/task/"
        params = {
            "_limit": 100,
            "is_complete": "false",
            "_type": "incoming_sms",
            "lead_id": lead_id
        }
        try:
            resp = requests.get(url, params=params, auth=self.auth, timeout=15)
            if resp.status_code == 200:
                for task in resp.json().get("data", []):
                    if task.get("object_id") == sms_id:
                        return task.get("id")
        except Exception:
            logger.exception(f"Error finding task for SMS {sms_id}")
        return None

    def mark_task_as_complete(self, task_id):
        url = f"{self.base_url}/task/{task_id}/"
        try:
            resp = requests.put(
                url,
                json={"is_complete": True},
                auth=self.auth,
                timeout=15
            )
            logger.info(f"✅ Task {task_id} marked complete ({resp.status_code})")
        except Exception:
            logger.exception(f"Error marking task {task_id} complete")

    def get_lead_id_from_contact(self, contact_id):
        url = f"{self.base_url}/contact/{contact_id}/"
        resp = requests.get(url, auth=self.auth, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("lead_id")
        return None

    def get_sms_thread_for_contact(self, lead_id, contact_id):
        url = f"{self.base_url}/activity/sms/"
        resp = requests.get(
            url,
            params={"lead_id": lead_id, "contact_id": contact_id},
            auth=self.auth,
            timeout=15
        )
        if resp.status_code == 200:
            return resp.json().get("data", [])
        return []

    def get_contact_phone(self, contact_id):
        url = f"{self.base_url}/contact/{contact_id}/"
        try:
            resp = requests.get(url, auth=self.auth, timeout=10)
            if resp.status_code == 200:
                phones = resp.json().get("phones", [])
                if phones:
                    return phones[0].get("phone")
        except Exception:
            logger.error(f"Error fetching phone for contact {contact_id}")
        return None

    def get_lead_name_from_contact(self, contact_id):
        url = f"{self.base_url}/contact/{contact_id}/"
        resp = requests.get(url, auth=self.auth, timeout=10)
        if resp.status_code == 200:
            lead_id = resp.json().get("lead_id")
            if lead_id:
                lead_resp = requests.get(
                    f"{self.base_url}/lead/{lead_id}/",
                    auth=self.auth,
                    timeout=10
                )
                if lead_resp.status_code == 200:
                    return lead_resp.json().get("display_name")
        return "Unknown Lead"

    def send_sms_to_lead(self, lead_id, contact_id, text):
        """
        Send an SMS via Close.com API with all required fields.
        """
        try:
            remote_phone = self.get_contact_phone(contact_id)
            if not remote_phone:
                logger.error(f"No remote_phone for contact {contact_id}")
                return False

            payload = {
                "lead_id": lead_id,
                "contact_id": contact_id,
                "local_phone": CRM_PHONE_NUMBER,
                "remote_phone": remote_phone,
                "text": text,
                "status": "outbox"
            }
            resp = requests.post(
                f"{self.base_url}/activity/sms/",
                json=payload,
                auth=self.auth,
                timeout=15
            )
            if 200 <= resp.status_code < 300:
                logger.info(f"✅ SMS queued (status={resp.status_code}) for contact {contact_id}")
                return True
            logger.error(f"❌ SMS failed: {resp.status_code} {resp.text}")
            return False
        except Exception:
            logger.exception(f"Exception sending SMS to {contact_id}")
            return False

    #
    # ─── STUBS FOR QUICK-QUOTE FIELDS ───────────────────────────────────
    #

    def get_lead_custom_fields(self, lead_id):
        """
        Stub: return a dict of custom fields if you have a “quick quote” stored.
        Example return value:
            { "size": "7x16x4", "wall_height": "4", "axles": "16K" }
        If none found, return None or {}.
        """
        return None

    def get_latest_quote_note(self, lead_id):
        """
        Stub: return the text of the latest “Quick Quote” note from CRM notes.
        If none found, return None.
        """
        return None

    def flag_lead_for_review(self, lead_id, reason="Inappropriate conversation"):
        url = f"{self.base_url}/lead/{lead_id}/"
        try:
            data = {"note": reason}
            requests.put(url, json=data, auth=self.auth)
            logger.info(f"Lead {lead_id} flagged for review: {reason}")
        except Exception as e:
            logger.exception(f"Error flagging lead {lead_id}")
