import crm_api
import openai_api

# Define your templates here. Replace with your actual templates.
templates = {
    "6x12x2": {"triggers": ["6x12x2", "compact", "small dump trailer"], "response": "..."},
    "6x12x3": {"triggers": ["6x12x3", "medium", "medium dump trailer"], "response": "..."},
    "6x12x4": {"triggers": ["6x12x4", "large", "large dump trailer"], "response": "..."},
    "7x14x2": {"triggers": ["7x14x2", "balance", "balance of size and capacity"], "response": "..."},
    "7x14x3": {"triggers": ["7x14x3", "extra capacity", "extra load"], "response": "..."},
    "7x14x4": {"triggers": ["7x14x4", "extra capacity", "extra load"], "response": "..."},
    "7x16x2": {"triggers": ["7x16x2", "large", "demanding hauls"], "response": "..."},
    "7x16x3": {"triggers": ["7x16x3", "large", "demanding hauls"], "response": "..."},
    "7x16x4": {"triggers": ["7x16x4", "large", "demanding hauls"], "response": "..."},
    "7x18 and 7x20 bumper pull": {"triggers": ["7x18", "7x20", "large dump trailer"], "response": "..."},
    "Check out our reviews": {"triggers": ["reviews", "quality"], "response": "..."},
    "Financing": {"triggers": ["financing", "payment"], "response": "..."},
    "Gooseneck 7x14x2": {"triggers": ["gooseneck", "7x14x2"], "response": "..."},
    "Gooseneck 7x14x3": {"triggers": ["gooseneck", "7x14x3"], "response": "..."},
    "Gooseneck 7x14x4": {"triggers": ["gooseneck", "7x14x4"], "response": "..."},
    "Gooseneck 7x16x2": {"triggers": ["gooseneck", "7x16x2"], "response": "..."},
    "Gooseneck 7x16x3": {"triggers": ["gooseneck", "7x16x3"], "response": "..."},
    "Gooseneck 7x16x4": {"triggers": ["gooseneck", "7x16x4"], "response": "..."},
    "Gooseneck 8x20x4": {"triggers": ["gooseneck", "8x20x4"], "response": "..."},
    "INTERESTED IN GETTING AN ORDER STARTED": {"triggers": ["order", "start", "purchase"], "response": "..."},
    "Our address": {"triggers": ["address", "location"], "response": "..."},
    "Sorry for the delay": {"triggers": ["late", "delay"], "response": "..."},
    "WEBSITE SPECS - 7x14": {"triggers": ["7x14", "specs", "details"], "response": "..."},
    "WEBSITE SPECS - 7x16": {"triggers": ["7x16", "specs", "details"], "response": "..."},
    "WEBSITE SPECS - 8x20": {"triggers": ["8x20", "specs", "details"], "response": "..."},
}

def find_template(lead_data, templates):
    # This function should analyze the lead data and find a matching template.
    # For now, it just returns the first template that matches the last message.
    for template_name, template in templates.items():
        if any(trigger in lead_data["last_message"].lower() for trigger in template["triggers"]):
            return template
    return None

def respond_to_unread_messages():
    # Retrieve unread messages
    unread_messages = crm_api.get_unread_messages("api_goes_here_crm")

    for msg in unread_messages:
        # Retrieve the lead's data
        lead_data = crm_api.get_lead_data("api_goes_here_crm", msg["lead_id"])

        # Analyze the message and lead's data to find a matching template
        template = find_template(lead_data, templates)

        if template is not None:
            # If a template is found, use the template response
            response = template["response"]
        else:
            # If no template is found, generate a response
            prompt = msg["content"]  # use the message content as the prompt
            response = openai_api.generate_response("gpt4_api_goes_here", prompt)

        # Send the response
        crm_api.send_message("api_goes_here_crm", msg["lead_id"], response)

# Run the function
# respond_to_unread_messages()  # commented out to prevent it from running automatically
