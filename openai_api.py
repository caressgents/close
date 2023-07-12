import openai
from config import OPENAI_API_KEY

def generate_response(prompt):
    openai.api_key = OPENAI_API_KEY

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ]
    )
    
    return response['choices'][0]['message']['content']
