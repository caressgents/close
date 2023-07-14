import time
from threading import Thread
from flask import Flask, jsonify
from config import CRM_PHONE_NUMBER
from crm_api import CRMAPI
from openai_api import generate_response
import re

app = Flask(__name__)
bot_thread = None
crm_api = CRMAPI()


def find_template(lead_data, templates):
    # Extract the necessary fields from the lead data
    hitch_type = lead_data['custom_fields'].get('preferred_hitch_type', '')
    size = lead_data['custom_fields'].get('what_size_dump_trailer_do_you_need?', '')
    
    # Extract the wall size from the lead's last message using a regular expression
    wall_size_search = re.search(r'(\d+)', lead_data['last_received_message'].get('text', ''))
    wall_size = wall_size_search.group(1) if wall_size_search else ''

    # Construct the template title based on the lead data
    template_title = ''
    if hitch_type.lower() == 'gooseneck':
        template_title += 'Gooseneck '
    template_title += f'{size}x{wall_size}'

    # Find the template with the matching title
    for template in templates:
        if template['title'] == template_title:
            return template

    # If no matching template is found, return None
    return None


def run_bot(max_leads_per_run=10):
    while True:
        # Initialize counters
        sent_counter = 0
        human_intervention_counter = 0
        fail_counter = 0

        # Get unread messages
        tasks = crm_api.get_unread_messages()[:max_leads_per_run]
        for task in tasks:
            lead_id = task['lead_id']
            message_id = task['id']

            # Get lead data
            lead_data = crm_api.get_lead_data(lead_id)
            if not lead_data or 'last_received_message' not in lead_data:
                fail_counter += 1
                continue

            # Generate a response using the OpenAI API
            response_text = generate_response(lead_data['last_received_message']['text'])

            # Find a matching template
            template = find_template(lead_data, templates)
            if template:
                # If a matching template is found, use it to send a response
                crm_api.send_message(lead_id, template['text'], message_id)
                sent_counter += 1
            else:
                # If no matching template is found, mark the lead for human intervention
                crm_api.update_lead_status(lead_id, 'Human Intervention')
                human_intervention_counter += 1

            # Mark the task as complete
            crm_api.mark_task_as_complete(task['id'])

        print(f"Successfully sent messages to {sent_counter} leads.")
        print(f"Marked {human_intervention_counter} leads for human intervention.")
        print(f"Failed to process {fail_counter} leads.")

        time.sleep(5)

@app.route('/start', methods=['POST'])
def start_bot():
    global bot_thread
    if bot_thread is None:
        bot_thread = Thread(target=run_bot)
        bot_thread.start()
    return jsonify(success=True)

@app.route('/stop', methods=['POST'])
def stop_bot():
    global bot_thread
    if bot_thread is not None:
        bot_thread.join()
        bot_thread = None
    return jsonify(success=True)

if __name__ == "__main__":
    app.run(port=5000, debug=False)
