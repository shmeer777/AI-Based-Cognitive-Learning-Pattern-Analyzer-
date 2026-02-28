from openai import OpenAI
from dotenv import load_dotenv
import os

env_path = os.path.join(os.path.dirname(__file__), "back", ".env")
load_dotenv(env_path)

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY not found in .env file")

client = OpenAI(api_key=api_key)

def ask_ai_question(conversation):
    try:
        system_prompt = {"role":"system","content":"You are GitHub Copilot, a helpful AI assistant that answers student questions clearly and concisely. When responding, first restate what the user just asked (e.g. 'You asked: ...'), then provide the answer."}
        msgs = conversation[:]
        if not msgs or msgs[0].get("role") != "system":
            msgs.insert(0, system_prompt)
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=msgs
        )
        return response.choices[0].message.content
    except Exception as e:
        print("AI request failed:", e)
        return "[Error contacting AI: {}]".format(str(e))
