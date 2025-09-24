import requests
import json
from flask import Flask, request, jsonify
from flask_cors import CORS

# --- Configuration ---
OLLAMA_API = "http://localhost:11434/api/generate"  # Ollama endpoint
OLLAMA_MODEL = "phi3"  # Ollama model

app = Flask(__name__)
CORS(app)

# --- Prompt helper ---
def create_debate_prompt(article_text, side="For", first_turn=False):
    """
    Creates a prompt for AI.
    - first_turn=True: generate initial debate (For/Against)
    - first_turn=False: continue debate with conversation history
    """
    if first_turn:
        return f"""
You are a debate generator AI.

Read the article below and extract 3-4 debatable key claims.

Then generate both sides in a short debate (2 exchanges, max 3 sentences each):

Key Claims:
1. [Claim 1]
2. [Claim 2]
3. [Claim 3]

Debate:
Persona A (For): [Opening statement]
Persona B (Against): [Counter-argument]
Persona A (For): [Rebuttal]
Persona B (Against): [Final counter-rebuttal]

Article:
{article_text}
"""
    else:
        return f"""
You are a debate generator AI. Continue the debate based on the conversation:

Conversation so far:
{article_text}

Your task:
- Argue for the side: {side}
- Limit your response to max 3 sentences
- If no meaningful points are left, respond: "No further arguments."

Output ONLY your response.
"""

# --- Routes ---
@app.route("/generate_debate", methods=["POST"])
def generate_debate():
    data = request.json
    article = data.get("article", "").strip()
    side = data.get("side", "For")
    first_turn = data.get("first_turn", False)

    if not article:
        return jsonify({"error": "No article text provided"}), 400

    prompt = create_debate_prompt(article, side, first_turn)

    def stream_response():
        try:
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": True
            }
            response = requests.post(OLLAMA_API, json=payload, stream=True)
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line.decode("utf-8"))
                        if "response" in chunk:
                            yield chunk["response"]
                    except json.JSONDecodeError:
                        continue
        except requests.RequestException as e:
            yield f"Error connecting to Ollama: {e}"

    return app.response_class(stream_response(), mimetype="text/plain")


if __name__ == "__main__":
    app.run(port=5000, debug=True)
