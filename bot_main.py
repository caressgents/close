import time
from threading import Thread
from flask import Flask, jsonify
from config import CRM_PHONE_NUMBER
from crm_api import CRMAPI
from openai_api import generate_response
import re
import logging

app = Flask(__name__)
bot_thread = None
crm_api = CRMAPI()

def extract_wall_heights(sms_text):
    """Extract wall height(s) from sms text using regular expression."""
    # This regular expression matches any number followed by an optional '
    matches = re.findall(r"(\d+)'?", sms_text)
    return [match + "'" for match in matches]

def select_template(lead_data, templates, wall_height):
    if templates is None or len(templates) == 0:
        print("No templates available.")
        return None

    preferred_hitch_type = None
    trailer_size = None

    # Extracting trailer size and hitch type from notes
    if 'notes' in lead_data and len(lead_data['notes']) > 0:
        note_content = lead_data['notes'][0]['note']
        match = re.search(r"(7x20|7x14|6x12|7x16|7x18|7x20|8x20)(gooseneck|bumper pull)", note_content)
        if match:
            trailer_size = match.group(1)
            preferred_hitch_type = match.group(2)
        else:
            print(f"No match found in notes for lead_id {lead_data['id']}")
            return None

    if preferred_hitch_type is None or trailer_size is None:
        print("Insufficient lead data to select a template.")
        return None

    template_title = f"{trailer_size}{' Gooseneck' if preferred_hitch_type == 'Gooseneck' else ''} {wall_height}'"

    for template in templates:
        if template['name'] == template_title:
            return template

    print(f"No template found for title: {template_title}")
    return None


def run_bot():
    print("Running the bot...")
    logging.basicConfig(filename='app.log', level=logging.INFO)

    while True:
        try:
            tasks = crm_api.get_unprocessed_incoming_sms_tasks()
            templates = crm_api.get_sms_templates()
            sent_counter = 0
            human_intervention_counter = 0
            failed_counter = 0
            for task in tasks:
                try:
                    lead_id = task['lead_id']
                    lead_data = crm_api.get_lead_data(lead_id)
                    if lead_data is None:
                        logging.error(f"Failed to get lead data for lead {lead_id}")
                        continue
                    lead_data['notes'] = crm_api.get_lead_notes(lead_id)
                    incoming_sms = crm_api.get_latest_incoming_sms(lead_id)
                    if incoming_sms is not None:
                        wall_heights = extract_wall_heights(incoming_sms['text'])
                        if len(wall_heights) > 1:
                            crm_api.update_lead_status(lead_id, 'stat_X')  # replace 'stat_X' with the actual status_id for 'Human Intervention'
                            human_intervention_counter += 1
                            print(f"Updated status to 'Human Intervention' for lead {lead_id} due to multiple wall heights")
                            crm_api.mark_task_as_complete(task['id'])
                        elif len(wall_heights) == 1:
                            template = select_template(lead_data, templates, wall_heights[0])
                            if template:
                                message = template['text'].replace('{{ wall_height }}', wall_heights[0])
                                if crm_api.send_message(lead_id, message, task['id'], template['id']):
                                    sent_counter += 1
                                    print(f"Successfully sent SMS template for lead {lead_id}")
                                    crm_api.mark_task_as_complete(task['id'])
                                else:
                                    crm_api.update_lead_status(lead_id, 'stat_X')  # replace 'stat_X' with the actual status_id for 'Human Intervention'
                                    human_intervention_counter += 1
                                    print(f"Updated status to 'Human Intervention' for lead {lead_id}")
                                    crm_api.mark_task_as_complete(task['id'])
                        else:
                            logging.error(f"No valid wall height found in SMS for lead {lead_id}")
                    else:
                        logging.error(f"No incoming SMS found for lead {lead_id}")
                except Exception as e:
                    logging.exception(f"Failed to process lead {lead_id}")
                    failed_counter += 1
            print(f"Sent {sent_counter} messages, marked {human_intervention_counter} leads for human intervention, failed to process {failed_counter} leads")
        except Exception as e:
            logging.exception("Failed to fetch tasks")
        time.sleep(5)


@app.route('/start', methods=['POST'])
def start_bot():
    global bot_thread
    if bot_thread is None or not bot_thread.is_alive():
        bot_thread = Thread(target=run_bot)
        bot_thread.start()
    return jsonify(success=True)

@app.route('/stop', methods=['POST'])
def stop_bot():
    global bot_thread
    if bot_thread is not None and bot_thread.is_alive():
        bot_thread = None
    return jsonify(success=True)

@app.route('/logs', methods=['GET'])
def get_logs():
    with open('app.log', 'r') as f:
        return f.read()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
