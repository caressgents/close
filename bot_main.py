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

def find_template(lead_data, templates):
    ...
    # (This function remains unchanged)
    ...

def run_bot(max_leads_per_run=10):
    logging.basicConfig(filename='app.log', level=logging.INFO)

    while True:
        try:
            sent_counter = 0
            human_intervention_counter = 0
            fail_counter = 0

            # Get unprocessed tasks of type 'incoming_sms'
            tasks = crm_api.get_unprocessed_incoming_sms_tasks()[:max_leads_per_run]
            for task in tasks:
                lead_id = task['lead_id']

                if lead_id is None:
                    logging.warning("Skipping task with None lead_id.")
                    continue

                lead_data = crm_api.get_lead_data(lead_id)
                if not lead_data or 'last_received_message' not in lead_data:
                    fail_counter += 1
                    continue

                response_text = generate_response(lead_data['last_received_message']['text'])

                template = find_template(lead_data, templates)
                if template:
                    crm_api.send_message(lead_id, template['text'], CRM_PHONE_NUMBER)
                    sent_counter += 1
                else:
                    crm_api.update_lead_status(lead_id, 'Human Intervention')
                    human_intervention_counter += 1

                # Mark the task as complete
                crm_api.mark_task_as_complete(task['id'])

            print(f"Successfully sent messages to {sent_counter} leads.")
            print(f"Marked {human_intervention_counter} leads for human intervention.")
            print(f"Failed to process {fail_counter} leads.")
            time.sleep(5)

        except Exception as e:
            logging.error(f"Error in run_bot: {str(e)}")

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
