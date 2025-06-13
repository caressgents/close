import openai
import logging
from config import OPENAI_API_KEY

logger = logging.getLogger("openai_api")
openai.api_key = OPENAI_API_KEY

def generate_response(system_prompt, user_prompt):
    try:
        logger.debug("🤖 Sending prompt to OpenAI...")
        response = openai.ChatCompletion.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=1,
            max_tokens=250
        )
        reply = response['choices'][0]['message']['content'].strip()
        logger.info(f"✅ OpenAI reply: {reply}")
        return reply
    except Exception as e:
        logger.exception("❌ OpenAI error, returning fallback reply")
        return "Thanks for your message! We'll be in touch shortly."
    
def moderate_content(text):
    try:
        response = openai.Moderation.create(input=text)
        return response["results"][0]["flagged"]
    except Exception as e:
        logger.exception("Moderation API error")
        return False

