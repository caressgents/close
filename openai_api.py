import openai
import os

def generate_response(prompt):
    openai.api_key = "GPT4_API_KEY_HERE"

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ]
    )
    
    return response['choices'][0]['message']['content']

response = generate_response("What are pricing options for your dump trailers? Please include all specs and photos can be found on our website www.topshelftrailers.com")
