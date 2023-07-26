import time
from threading import Thread
from flask import Flask, jsonify
from config import CRM_PHONE_NUMBER
from crm_api import CRMAPI
import re
import logging
import os
import openai
import sys

# Define a Handler which writes INFO messages or higher to the sys.stderr (this could be your console)
console = logging.StreamHandler(sys.stderr)
console.setLevel(logging.INFO)

# Define a Handler for the log file
file_handler = logging.FileHandler('app.log')
file_handler.setLevel(logging.DEBUG)

# Set a format which is simpler for console use
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')

# Tell the handler to use this format
console.setFormatter(formatter)
file_handler.setFormatter(formatter)

logging.basicConfig(
    level=logging.DEBUG,
    handlers=[file_handler, console])

app = Flask(__name__)
bot_thread = None
crm_api = CRMAPI()

# Initialize OpenAI with your API key
openai.api_key = os.getenv("OPENAI_API_KEY")

def get_wall_height(sms_text):
    logging.info(f"Analyzing SMS text for wall height: {sms_text}")
    prompt = f"In the following SMS text, a customer is discussing the wall height of a trailer they're interested in. The height will be a number somewhere in their response, either 2, 3, or 4, possibly 2', 4', 5' and will be in their natural language or conversation, here is the text you need to analyze and extract the single digit wall height from: \"{sms_text}\". Could you tell me the wall height the customer is referring to? YOU MUST respond with a single numerical digit only, no additional text or explanation."
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant and follow directions perfectly"},
            {"role": "user", "content": prompt},
        ]
    )
    wall_height_response = response['choices'][0]['message']['content'].strip()
    # Extract just the number from the AI's response
    match = re.search(r'\d+', wall_height_response)
    if match is not None:
        wall_height = match.group()
    else:
        wall_height = "No wall height found in the response"
        # Or alternatively, raise a more descriptive error
        # raise ValueError("No wall height found in the response")
    logging.info(f"Extracted wall height: {wall_height}")
    return wall_height

def extract_information(lead_data):
    logging.debug(f"Extracting information from lead data: {lead_data}")
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
    logging.info(f"Selecting template for hitch type: {hitch_type}, trailer size: {trailer_size}, wall height: {wall_height}")
    # Format the attributes into a string similar to template names
    formatted_attributes = f"{hitch_type} {trailer_size}x{wall_height}"
    # Normalize the attributes string to compare with normalized template names
    normalized_attributes = formatted_attributes.lower().replace(' ', '')
    for template in templates:
        # Normalize the template name
        normalized_template_name = template['name'].lower().replace(' ', '')
        if normalized_attributes in normalized_template_name:
            logging.info(f"Selected template: {template}")
            return template
    logging.info("No matching template found")
    return None

def analyze_data_with_ai(data):
    # Use OpenAI's GPT-4 model to analyze the data
    logging.debug(f"Sending data to AI for analysis: {data}")
    logging.info(f"Analyzing data with AI: {data}")
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": data},
        ]
    )
    ai_response = response['choices'][0]['message']['content'].strip()
    logging.info(f"AI response: {ai_response}")
    return ai_response

def load_processed_tasks(filename):
    try:
        with open(filename, 'r') as f:
            return set(line.strip() for line in f)
    except FileNotFoundError:
        return set()

def save_processed_tasks(filename, task_id):
    with open(filename, 'a') as f:
        f.write(task_id + '\n')

def run_bot_once():
    print("Starting bot run...")
    print("Running the bot...")
    sent_counter = 0
    human_intervention_counter = 0
    failed_counter = 0
    specific_statuses = ['stat_GKAEbEJMZeyQlU7IYFOpd6PorjXupqmcNmmSzQBbcVJ', 'stat_6cqDnnaff2GYLV52VABicFqCV6cat7pyJn7wCJALGWz']
    while True:
        processed_tasks = load_processed_tasks('processed_tasks.txt')
        users_data = crm_api.get_all_users()
        if isinstance(users_data.get('data', {}), list):
            users = users_data['data']
            user_ids = [user['id'] for user in users] if users else []
        else:
            print("Error: users_data['data'] is not a list")
            user_ids = []
        skip = 0
        lead_ids = []
        while True:
            fetched_lead_ids = crm_api.get_leads_with_specific_statuses(specific_statuses, skip=skip)
            if not fetched_lead_ids:
                break
            lead_ids.extend(fetched_lead_ids)
            skip += len(fetched_lead_ids)
        leads_to_process = []
        for lead_id in lead_ids:
            if lead_id not in processed_tasks:
                leads_to_process.append(lead_id)
        print(f"Fetched {len(leads_to_process)} unprocessed leads with the specific statuses.")
        if not leads_to_process:
            print("No unprocessed leads found. Breaking the main loop...")
            break
        for lead_id in leads_to_process:
            print("Fetching unresponded incoming SMS tasks...")
            tasks = crm_api.get_unresponded_incoming_sms_tasks_for_lead(lead_id)
            if tasks is None:
                print("Failed to fetch tasks")
                continue
            print(f"Fetched {len(tasks)} tasks.")
            templates = crm_api.get_sms_templates()
            if templates is None:
                print("Failed to fetch templates")
                continue
            print(f"Fetched {len(templates)} templates.")
            sent_counter = 0
            human_intervention_counter = 0
            failed_counter = 0
            tasks_processed = 0
            for task in tasks:
                if task.get('lead_id') is None:
                    print(f"Skipping task {task['id']} because it has no lead_id")
                    continue
                print(f"Starting processing for task {task['id']}")
                try:
                    if task['id'] in processed_tasks:
                        print(f"Task {task['id']} has already been processed, skipping")
                        continue
                    lead_id = task['lead_id']
                    print(f"Processing lead {lead_id}...")
                    lead_data = crm_api.get_lead_data(lead_id)
                    if lead_data is None:
                        print(f"Failed to get lead data for lead {lead_id}")
                        crm_api.update_lead_status(lead_id, 'stat_w1TTOIbT1rYA24hSNF3c2pjazxxD0C05TQRgiVUW0A3')
                        human_intervention_counter += 1
                        continue
                    contacts = lead_data.get('contacts', [])
                    if contacts and 'phones' in contacts[0] and contacts[0]['phones']:
                        remote_phone = contacts[0]['phones'][0]['phone']
                    else:
                        print(f"No phone number found for lead {lead_id}")
                        crm_api.update_lead_status(lead_id, 'stat_w1TTOIbT1rYA24hSNF3c2pjazxxD0C05TQRgiVUW0A3')
                        human_intervention_counter += 1
                        continue
                    lead_data['notes'] = crm_api.get_lead_notes(lead_id)
                    hitch_type, trailer_size = extract_information(lead_data)
                    if hitch_type is None or trailer_size is None:
                        print("Insufficient lead data for hitch type or trailer size")
                        crm_api.update_lead_status(lead_id, 'stat_w1TTOIbT1rYA24hSNF3c2pjazxxD0C05TQRgiVUW0A3')
                        human_intervention_counter += 1
                        continue

                    sms_text = task['content']['content']
                    wall_height = get_wall_height(sms_text)

                    if wall_height is None or wall_height == "No wall height found in the response":
                        print("Insufficient SMS data for wall height")
                        crm_api.update_lead_status(lead_id, 'stat_w1TTOIbT1rYA24hSNF3c2pjazxxD0C05TQRgiVUW0A3')
                        human_intervention_counter += 1
                        continue

                    template = select_template(hitch_type, trailer_size, wall_height, templates)
                    
                    if template is None:
                        print("No matching template found")
                        crm_api.update_lead_status(lead_id, 'stat_w1TTOIbT1rYA24hSNF3c2pjazxxD0C05TQRgiVUW0A3')
                        human_intervention_counter += 1
                        continue

                    sent = crm_api.send_sms(remote_phone, CRM_PHONE_NUMBER, template['content'])
                    if sent:
                        print(f"Successfully sent SMS for lead {lead_id}")
                        crm_api.update_lead_status(lead_id, 'stat_wMLYSSNRQRGu8YCBABMdcYkQCyPhVXxfUrXr9IKPwMc')
                        sent_counter += 1
                        save_processed_tasks('processed_tasks.txt', task['id'])
                    else:
                        print(f"Failed to send SMS for lead {lead_id}")
                        crm_api.update_lead_status(lead_id, 'stat_w1TTOIbT1rYA24hSNF3c2pjazxxD0C05TQRgiVUW0A3')
                        failed_counter += 1

                except Exception as e:
                    print(f"Error processing task {task['id']}: {e}")
                    crm_api.update_lead_status(lead_id, 'stat_w1TTOIbT1rYA24hSNF3c2pjazxxD0C05TQRgiVUW0A3')
                    human_intervention_counter += 1
                    continue

            tasks_processed += 1
            print(f"Processed tasks: {tasks_processed}")
            print(f"Successful SMS sent: {sent_counter}")
            print(f"Human intervention required: {human_intervention_counter}")
            print(f"Failed SMS sending: {failed_counter}")

        time.sleep(60 * 10)

@app.route('/start_bot')
def start_bot():
    global bot_thread
    if bot_thread is not None and bot_thread.is_alive():
        return jsonify({"status": "Bot already running."})

    bot_thread = Thread(target=run_bot_once)
    bot_thread.start()
    return jsonify({"status": "Bot started."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)