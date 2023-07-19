import openai
import logging
from config import OPENAI_API_KEY

# Create a custom logger
logger = logging.getLogger(__name__)

def generate_response(prompt):
    openai.api_key = OPENAI_API_KEY

    logger.info(f"Generating response for prompt: {prompt}")

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ]
    )

    logger.info(f"Generated response: {response['choices'][0]['message']['content']}")

    return response['choices'][0]['message']['content']
