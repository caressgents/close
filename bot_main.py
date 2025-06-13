# bot_main.py

import logging
import sys
import time
import math
import re
from multiprocessing import Process
from flask import Flask, jsonify, request
import os
import csv
from datetime import datetime
from crm_api import CRMAPI
from openai_api import generate_response
from config import CRM_PHONE_NUMBER
from openai_api import moderate_content


# === Logging Setup (root logger) ===
console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.INFO)
file_handler = logging.FileHandler("app.log")
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
console.setFormatter(formatter)
file_handler.setFormatter(formatter)

root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
    root_logger.addHandler(console)
    root_logger.addHandler(file_handler)

logger = logging.getLogger(__name__)
app = Flask(__name__)
crm = CRMAPI()

CSV_PATH = "ai_sms_log.csv"
FAILURE_CSV = "ai_sms_failures.csv"
PROCESSED_IDS_FILE = "processed_ids.txt"
PROMPT_PATH = "system_prompt.txt"
OPT_OUT = [
    "stop", "unsubscribe", "opt out", "no more texts",
    "wrong number", "already bought", "just bought one",
    "bought one", "purchased one", "already purchased"
]

# Ensure success CSV header
if not os.path.isfile(CSV_PATH):
    with open(CSV_PATH, "w", newline="") as f:
        csv.writer(f).writerow([
            "timestamp", "source", "lead_name", "message_id", "message_text"
        ])

# Ensure failure CSV header
if not os.path.isfile(FAILURE_CSV):
    with open(FAILURE_CSV, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["timestamp", "source", "lead_name", "message_id", "message_text", "status"]
        )
        writer.writeheader()

def load_system_prompt(path):
    try:
        return open(path).read()
    except Exception as e:
        logger.error(f"❌ Failed to load system prompt: {e}")
        return ""

SYSTEM_PROMPT = load_system_prompt(PROMPT_PATH)

# Load processed SMS IDs
if os.path.exists(PROCESSED_IDS_FILE):
    processed_sms = set(open(PROCESSED_IDS_FILE).read().split())
else:
    processed_sms = set()

def save_processed_id(mid):
    processed_sms.add(mid)
    with open(PROCESSED_IDS_FILE, "a") as f:
        f.write(mid + "\n")

def process_sms():
    logger.info("Checking for new SMS tasks in CRM Inbox…")
    responded_phones = set()
    summary = {"sent": 0, "opt_out": 0, "skipped": 0, "failed": 0}

    for page_num, (tasks, total) in enumerate(crm.iter_open_sms_tasks(limit=100), start=1):
        batch_size = len(tasks)
        total_pages = math.ceil(total / 100)
        logger.info(
            f"🔄 Processing batch {page_num}/{total_pages} of {total} tasks ({batch_size} in this batch)"
        )

        for idx, task in enumerate(tasks, start=1):
            task_id = task.get("id")
            sms_id  = task.get("object_id")
            if not sms_id or sms_id in processed_sms:
                continue

            sms = crm.get_sms_activity(sms_id)
            if not sms:
                logger.warning(
                    f"[batch {page_num} msg {idx}/{batch_size}] ❌ Couldn’t fetch SMS {sms_id}, skipping"
                )
                processed_sms.add(sms_id)
                continue

            mid = sms_id
            cid = sms.get("contact_id")
            txt = (sms.get("text") or "").strip()
            if moderate_content(txt):
                crm.send_sms_to_lead(lead_id, cid, "We only handle serious trailer inquiries. Call 888-643-7498 for assistance.")
                crm.mark_task_as_complete(task_id)
                save_processed_id(mid)
                logger.warning(f"Inappropriate content detected from {lead_name}, conversation terminated.")
                continue  # immediately skip further processing
            lead_id = sms.get("lead_id")
            remote_phone = crm.get_contact_phone(cid) if cid else None

            # Dedupe within this run
            if remote_phone and remote_phone in responded_phones:
                logger.info(
                    f"[batch {page_num} msg {idx}/{batch_size}] ⚠️ Already texted {remote_phone}, skipping {mid}"
                )
                crm.mark_task_as_complete(task_id)
                summary["skipped"] += 1
                save_processed_id(mid)
                continue

            # Quick filters
            if not cid:
                logger.info(
                    f"[batch {page_num} msg {idx}/{batch_size}] ⚠️ Missing contact, skipping {mid}"
                )
                crm.mark_task_as_complete(task_id)
                summary["skipped"] += 1
                save_processed_id(mid)
                continue
            if any(opt in txt.lower() for opt in OPT_OUT):
                logger.info(
                    f"[batch {page_num} msg {idx}/{batch_size}] ⚠️ Opt-out for {mid}: {txt}"
                )
                crm.mark_task_as_complete(task_id)
                summary["opt_out"] += 1
                save_processed_id(mid)
                continue

            thread = crm.get_sms_thread_for_contact(lead_id, cid)
            if not thread:
                logger.info(
                    f"[batch {page_num} msg {idx}/{batch_size}] ⚠️ No thread, skipping {mid}"
                )
                crm.mark_task_as_complete(task_id)
                summary["skipped"] += 1
                save_processed_id(mid)
                continue

            last = sorted(
                thread, key=lambda m: m.get("activity_at") or m.get("date_created")
            )[-1]
            if last.get("direction") == "outbound":
                logger.info(
                    f"[batch {page_num} msg {idx}/{batch_size}] ✅ Already responded, marking done {mid}"
                )
                crm.mark_task_as_complete(task_id)
                summary["skipped"] += 1
                save_processed_id(mid)
                continue

            # Build history
            history = "\n".join(
                f"{'Lead' if m['direction']=='inbound' else 'Agent'}: {(m.get('text') or '').strip()}"
                for m in sorted(
                    thread, key=lambda m: m.get("activity_at") or m.get("date_created")
                )
                if m.get("text")
            )

            # ── FETCH ANY “QUICK QUOTE” DATA ───────────────────────────────────
            known_quote = crm.get_lead_custom_fields(lead_id)
            if not known_quote or not known_quote.get("size"):
                quote_note = crm.get_latest_quote_note(lead_id)
            else:
                quote_note = None

            # Build a short “quote_context” string
            quote_context = ""
            if known_quote and known_quote.get("size"):
                size_val    = known_quote.get("size")
                walls_val   = known_quote.get("wall_height")
                axles_val   = known_quote.get("axles")
                missing = []
                if not walls_val: missing.append("wall height")
                if not axles_val: missing.append("axles")
                if missing:
                    quote_context = (
                        f"Quick Quote Info – Size: {size_val}, Walls: {walls_val or 'unknown'}. "
                        f"Missing: {', '.join(missing)}."
                    )
                else:
                    quote_context = (
                        f"Quick Quote Info – Size: {size_val}, Walls: {walls_val}, Axles: {axles_val}."
                    )
            elif quote_note:
                quote_context = f"Quick Quote Form: {quote_note.strip()}"

            # ── CLASSIFICATION ───────────────────────────────────────────────────
            cls_prompt = (
                "Here is the SMS thread:\n"
                f"{history}\n\n"
                "Classify the *last* inbound message as exactly one of:\n"
                " • WRONG_NUMBER  – customer said wrong number\n"
                " • ACK           – just a thank-you/ok/anytime, no question\n"
                " • PROCEED       – asking for pricing, details, next steps\n"
                " • OTHER         – anything else\n"
            )
            try:
                cls = generate_response(SYSTEM_PROMPT, cls_prompt).strip().upper()
            except Exception as e:
                logger.error(
                    f"[batch {page_num} msg {idx}/{batch_size}] ❌ Classification error: {e}"
                )
                cls = "PROCEED"

            # SKIP wrong numbers entirely
            if cls == "WRONG_NUMBER":
                apology = "Sorry about that mix-up—thanks for your time!"
                crm.send_sms_to_lead(lead_id, cid, apology)
                crm.mark_task_as_complete(task_id)
                summary["sent"] += 1
                save_processed_id(mid)
                if remote_phone:
                    responded_phones.add(remote_phone)
                continue

            # ACK simple acknowledgements
            if cls == "ACK":
                ack_prompt = (
                    "You are a friendly assistant. Reply *briefly* to the last customer message "
                    "with a short acknowledgment like “No problem!” or “Glad to help!”"
                )
                ack = generate_response(SYSTEM_PROMPT, ack_prompt).strip()
                crm.send_sms_to_lead(lead_id, cid, ack)
                crm.mark_task_as_complete(task_id)
                summary["sent"] += 1
                save_processed_id(mid)
                if remote_phone:
                    responded_phones.add(remote_phone)
                continue

            # APOLOGIZE for mis-communications
            if cls == "APOLOGIZE":
                apology = "Sorry about that mix-up—thanks for your time!"
                crm.send_sms_to_lead(lead_id, cid, apology)
                crm.mark_task_as_complete(task_id)
                summary["sent"] += 1
                save_processed_id(mid)
                if remote_phone:
                    responded_phones.add(remote_phone)
                continue

            # ── PROCEED or OTHER → full sales flow ────────────────────────────
            lead_name = crm.get_lead_name_from_contact(cid) or "there"
            first_name = lead_name.split()[0] if lead_name != "Unknown Lead" else "there"

            ask_images = bool(re.search(r'\b(pic|photo|image)s?\b.*\?', txt.lower()))
            image_line = (
                "You can’t send pictures via this line. "
                "Recommend they call 888-643-7498 to see photos or visit our gallery at www.topshelftrailers.com. "
            ) if ask_images else ""

            if quote_context:
                sales_prompt = (
                    f"{quote_context}\n\n"
                    f"Lead First Name: {first_name}\n"
                    f"Recent Conversation History (read carefully to respond naturally):\n{history}\n\n"
                    f"{image_line}"
                    "Respond conversationally, naturally, and avoid robotic replies. Clearly encourage calling 888-643-7498 to proceed."
                )
            else:
                sales_prompt = (
                    f"Lead First Name: {first_name}\n"
                    f"Recent Conversation History (read carefully to respond naturally):\n{history}\n\n"
                    f"{image_line}"
                    "Respond conversationally, naturally, and avoid robotic replies. Clearly encourage calling 888-643-7498 to proceed."
                )

            logger.info(
                f"[batch {page_num} msg {idx}/{batch_size}] 🧠 Generating sales reply for {mid}"
            )
            try:
                reply = generate_response(SYSTEM_PROMPT, sales_prompt).strip()
            except Exception as e:
                logger.error(
                    f"[batch {page_num} msg {idx}/{batch_size}] ❌ Error generating reply: {e}"
                )
                summary["failed"] += 1
                save_processed_id(mid)
                continue

            if not reply:
                logger.info(
                    f"[batch {page_num} msg {idx}/{batch_size}] ⚠️ Empty reply, skipping {mid}"
                )
                summary["failed"] += 1
                save_processed_id(mid)
                continue

            logger.info(f"[batch {page_num} msg {idx}/{batch_size}] 📨 Reply: {reply}")
            sent = crm.send_sms_to_lead(lead_id, cid, reply)
            if sent:
                crm.mark_task_as_complete(task_id)
                save_processed_id(mid)
                if remote_phone:
                    responded_phones.add(remote_phone)
                with open(CSV_PATH, "a", newline="") as f:
                    csv.writer(f).writerow([
                        datetime.utcnow().isoformat(),
                        "bot_main",
                        lead_name,
                        mid,
                        reply
                    ])
                summary["sent"] += 1
                logger.info(
                    f"[batch {page_num} msg {idx}/{batch_size}] ✅ Sent SMS to {lead_name}"
                )
            else:
                failure_row = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "bot_main",
                    "lead_name": lead_name,
                    "message_id": mid,
                    "message_text": reply,
                    "status": "FAILED"
                }
                with open(FAILURE_CSV, "a", newline="") as ff:
                    writer = csv.DictWriter(
                        ff,
                        fieldnames=["timestamp", "source", "lead_name", "message_id", "message_text", "status"]
                    )
                    writer.writerow(failure_row)

                logger.warning(
                    f"[batch {page_num} msg {idx}/{batch_size}] 🛑 SMS failed for {mid}"
                )
                summary["failed"] += 1

    logger.info(
        f"🏁 Finished: Sent {summary['sent']} | Opt-out {summary['opt_out']} | "
        f"Skipped {summary['skipped']} | Failed {summary['failed']}"
    )

def run_bot():
    while True:
        try:
            process_sms()
            time.sleep(10)
        except Exception as e:
            logger.error(f"❌ Error in run loop: {e}")
            time.sleep(30)

@app.route("/start", methods=["POST","GET"])
def start_bot():
    global bot_proc
    if "bot_proc" not in globals() or not bot_proc.is_alive():
        bot_proc = Process(target=run_bot)
        bot_proc.start()
        return jsonify({"status":"bot started"})
    return jsonify({"status":"already running"})

@app.route("/stop", methods=["POST","GET"])
def stop_bot():
    global bot_proc
    if "bot_proc" in globals() and bot_proc.is_alive():
        bot_proc.terminate()
        bot_proc.join(timeout=5)
        return jsonify({"status":"bot stopped"})
    return jsonify({"status":"not running"})

import signal
def shutdown(signum, frame):
    logger.info("Shutting down…")
    if "bot_proc" in globals() and bot_proc.is_alive():
        bot_proc.terminate()
        bot_proc.join(timeout=5)
    sys.exit(0)
signal.signal(signal.SIGINT, shutdown)

if __name__ == "__main__":
    app.run(port=5000, debug=True, use_reloader=False)
