import time
from threading import Thread
from flask import Flask, jsonify
from config import CRM_PHONE_NUMBER
from crm_api import CRMAPI
import re
import logging
import os
import openai

app = Flask(__name__)
bot_thread = None
crm_api = CRMAPI()

# Initialize OpenAI with your API key
openai.api_key = os.getenv("OPENAI_API_KEY")

def get_wall_height(sms_text):
    logging.info(f"Analyzing SMS text for wall height: {sms_text}")  # Add this line
    prompt = f"The following SMS text contains a mention of the wall height of a trailer: \"{sms_text}\". What is the wall height?"
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ]
    )
    wall_height = response['choices'][0]['message']['content'].strip()
    logging.info(f"Extracted wall height: {wall_height}")  # Add this line
    return wall_height

def select_template(lead_data, templates, wall_height):
    logging.info(f"Selecting template for lead data: {lead_data}, wall height: {wall_height}")  # Add this line
    trailer_size = None
    hitch_type = None
    for note in lead_data['notes']:
        if 'Trailer size?' in note['note']:
            trailer_size = note['note'].split('?')[-1].strip()
        if 'Preferred Hitch type?' in note['note']:
            hitch_type = note['note'].split('?')[-1].strip()
    if trailer_size is None or hitch_type is None:
        logging.info("Insufficient lead data for template selection")  # Add this line
        return None
    for template in templates:
        if trailer_size in template['name'] and hitch_type in template['name'] and wall_height in template['name']:
            logging.info(f"Selected template: {template}")  # Add this line
            return template
    logging.info("No matching template found")  # Add this line
    return None

def analyze_data_with_ai(data):
    # Use OpenAI's GPT-3.5-turbo model to analyze the data
    logging.info(f"Analyzing data with AI: {data}")
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": data},
        ]
    )
    ai_response = response['choices'][0]['message']['content'].strip()
    logging.info(f"AI response: {ai_response}")
    return


def run_bot():
    logging.info("Running the bot...")
    # Define the specific opportunity statuses we are interested in
    specific_statuses = ['stat_GKAEbEJMZeyQlU7IYFOpd6PorjXupqmcNmmSzQBbcVJ', 'stat_6cqDnnaff2GYLV52VABicFqCV6cat7pyJn7wCJALGWz']

    while True:
        try:
            logging.info("Fetching unresponded incoming SMS tasks...")
            tasks = crm_api.get_unresponded_incoming_sms_tasks()
            logging.info(f"Fetched {len(tasks)} tasks.")
            templates = crm_api.get_sms_templates()
            logging.info(f"Fetched {len(templates)} templates.")
            sent_counter = 0
            human_intervention_counter = 0
            failed_counter = 0
            for task in tasks:
                try:
                    lead_id = task['lead_id']
                    logging.info(f"Processing lead {lead_id}...")
                    lead_data = crm_api.get_lead_data(lead_id)
                    if lead_data is None:
                        logging.error(f"Failed to get lead data for lead {lead_id}")
                        continue

                    lead_data['notes'] = crm_api.get_lead_notes(lead_id)
                    incoming_sms = crm_api.get_latest_incoming_sms(lead_id)
                    outgoing_sms = crm_api.get_latest_outgoing_sms(lead_id)
                    if incoming_sms is not None and (outgoing_sms is None or incoming_sms["date_created"] > outgoing_sms["date_created"]):
                        wall_height = get_wall_height(incoming_sms['text'])
                        if wall_height:
                            template = select_template(lead_data, templates, wall_height)
                            if template:
                                message = template['text'].replace('{{ wall_height }}', wall_height)
                                # Analyze the incoming SMS with AI before sending the message
                                ai_response = analyze_data_with_ai(incoming_sms['text'])
                                logging.info(f"AI response for incoming SMS: {ai_response}")
                                if crm_api.send_message(lead_id, message, task['id'], template['id']):
                                    sent_counter += 1
                                    logging.info(f"Successfully sent SMS template for lead {lead_id}")
                                else:
                                    crm_api.update_lead_status(lead_id, 'stat_w1TTOIbT1rYA24hSNF3c2pjazxxD0C05TQRgiVUW0A3')  # replace 'stat_X' with the actual status_id for 'Human Intervention'
                                    human_intervention_counter += 1
                                    logging.info(f"Updated status to 'Human Intervention' for lead {lead_id} due to SMS sending failure")
                            else:
                                crm_api.update_lead_status(lead_id, 'stat_w1TTOIbT1rYA24hSNF3c2pjazxxD0C05TQRgiVUW0A3')  # replace 'stat_X' with the actual status_id for 'Human Intervention'
                                human_intervention_counter += 1
                                logging.info(f"Updated status to 'Human Intervention' for lead {lead_id} due to no matching template")
                        else:
                            crm_api.update_lead_status(lead_id, 'stat_w1TTOIbT1rYA24hSNF3c2pjazxxD0C05TQRgiVUW0A3')  # replace 'stat_X' with the actual status_id for 'Human Intervention'
                            human_intervention_counter += 1
                            logging.info(f"Updated status to 'Human Intervention' for lead {lead_id} due to no valid wall height found in SMS")
                    else:
                        logging.error(f"No incoming SMS found for lead {lead_id}")
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
        logging.info("Bot thread started.")
    return jsonify(success=True)

@app.route('/stop', methods=['POST'])
def stop_bot():
    global bot_thread
    if bot_thread is not None and bot_thread.is_alive():
        bot_thread = None
        logging.info("Bot thread stopped.")
    return jsonify(success=True)

@app.route('/logs', methods=['GET'])
def get_logs():
    with open('app.log', 'r') as f:
        return f.read()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
