from flask import Flask, request, jsonify
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv('ai.env')

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.route("/ask", methods=["POST"])
def ask():
    message = request.json["message"]

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=message
    )

    return jsonify({"reply": response.output_text})

app.run(debug=True)