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
    logging.info(f"Analyzing SMS text for wall height: {sms_text}")  
    prompt = f"In the following SMS text, a customer is discussing the wall height of a trailer they're interested in, it will be a number somewhere in their response either 2, 3, or 4, and will be in natural language: \"{sms_text}\". Could you tell me the wall height the customer is referring to? respond with a single numerical digit only, nothing else, no special characters, nothing, do not respond with anything other than the number you find?"
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ]
    )
    wall_height_response = response['choices'][0]['message']['content'].strip()
    # Extract just the number from the AI's response
    wall_height = re.search(r'\d+', wall_height_response).group()
    logging.info(f"Extracted wall height: {wall_height}")  
    return wall_height


def extract_information(lead_data):
    notes = [note['note'] for note in lead_data.get('notes', [])]
    combined_data = ' '.join(notes)
    hitch_type_pattern = r"(bumper pull|gooseneck)"
    trailer_size_pattern = r"(6x10|6x12|7x14|7x16|7x18|7x20|8x20)"
    hitch_type = re.search(hitch_type_pattern, combined_data, re.IGNORECASE)
    trailer_size = re.search(trailer_size_pattern, combined_data)
    if hitch_type:
        hitch_type = hitch_type.group(0)
    if trailer_size:
        trailer_size = trailer_size.group(0)
    return hitch_type, trailer_size

def select_template(hitch_type, trailer_size, wall_height, templates):
    logging.info(f"Selecting template for hitch type: {hitch_type}, trailer size: {trailer_size}, wall height: {wall_height}")  # Add this line
    # Format the attributes into a string similar to template names
    formatted_attributes = f"{hitch_type} {trailer_size}x{wall_height}"
    # Normalize the attributes string to compare with normalized template names
    normalized_attributes = formatted_attributes.lower().replace(' ', '')
    for template in templates:
        # Normalize the template name
        normalized_template_name = template['name'].lower().replace(' ', '')
        if normalized_attributes in normalized_template_name:
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

                    # Extract the first phone number of the first contact
                    contacts = lead_data.get('contacts', [])
                    if contacts and 'phones' in contacts[0] and contacts[0]['phones']:
                        remote_phone = contacts[0]['phones'][0]['phone']
                    else:
                        logging.error(f"No phone number found for lead {lead_id}")
                        continue

                    lead_data['notes'] = crm_api.get_lead_notes(lead_id)

                    hitch_type, trailer_size = extract_information(lead_data)
                    if hitch_type is None or trailer_size is None:
                        logging.info("Insufficient lead data for hitch type or trailer size")
                        continue

                    incoming_sms = crm_api.get_latest_incoming_sms(lead_id)
                    outgoing_sms = crm_api.get_latest_outgoing_sms(lead_id)

                    if incoming_sms is not None and (outgoing_sms is None or incoming_sms["date_created"] > outgoing_sms["date_created"]):
                        wall_height = get_wall_height(incoming_sms['text'])
                        if wall_height:
                            template = select_template(hitch_type, trailer_size, wall_height, templates)
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
