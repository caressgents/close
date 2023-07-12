import os

# Load environment variables
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
CRM_API_KEY = os.getenv('CRM_API_KEY')
CRM_API_URL = os.getenv('CRM_API_URL', 'https://api.close.com/api/v1/')
CRM_PHONE_NUMBER = os.getenv('CRM_PHONE_NUMBER')
