# 'bot_main.py'
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

def parse_wall_height(message):
    # Use regex to find a digit (2, 3, or 4) in the message
    match = re.search(r"\b[234]\b", message)
    return match.group(0) if match else None

def select_template(lead_data, templates):
    # Extract lead preferences from custom fields or notes
    if 'Custom_Data' in lead_data:
        preferred_hitch_type = lead_data['Custom_Data'].get('Preferred_hitch_type')
        trailer_size = lead_data['Custom_Data'].get('What_size_dump_trailer_do_you_need')
    else:
        # Extract preferences from notes (assuming the first note contains the necessary information)
        note_content = lead_data['notes'][0]['note']
        trailer_size, preferred_hitch_type = note_content.split()

    # Generate template title based on lead preferences
    template_title = f"{trailer_size}{' Gooseneck' if preferred_hitch_type == 'Gooseneck' else ''}"

    # Return the template with the matching title
    for template in templates:
        if template['name'] == template_title:
            return template

    return None

def run_bot():
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
                    # Get lead notes
                    lead_data['notes'] = crm_api.get_lead_notes(lead_id)
                    if 'last_received_message' in lead_data:
                        wall_height = parse_wall_height(lead_data['last_received_message']['text'])
                        # Update the template selection logic
                        template = select_template(lead_data, templates)
                        if template and wall_height in template['text']:
                            message = template['text'].replace('{{ wall_height }}', wall_height)
                            crm_api.send_message(lead_id, message, task['id'])
                            sent_counter += 1
                        else:
                            crm_api.update_lead_status(lead_id, 'Human Intervention')
                            human_intervention_counter += 1
                    crm_api.mark_task_as_complete(task['id'])
                except Exception as e:
                    logging.exception(f"Failed to process lead {lead_id}")
                    failed_counter += 1
            logging.info(f"Sent {sent_counter} messages, marked {human_intervention_counter} leads for human intervention, failed to process {failed_counter} leads")
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
