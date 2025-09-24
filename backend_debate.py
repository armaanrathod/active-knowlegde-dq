import requests
import json
import re
from flask import Flask, request, jsonify
from flask_cors import CORS

# --- Configuration ---
OLLAMA_API = "http://localhost:11434/api/generate"  # Ollama endpoint
OLLAMA_MODEL = "phi3"  # Ollama model

app = Flask(__name__)
CORS(app)

# --- Global state for debate tracking ---
debate_state = {
    "debate_history": [],
    "round_count": 0,
    "total_points": 0,
    "relevant_points": 0,
    "relevance_percentage": 100.0
}

# --- Prompt helper ---
def create_debate_prompt(article_text, side="For", first_turn=False, round_number=1):
    """
    Creates a prompt for AI.
    - first_turn=True: generate initial debate (5 For/5 Against points)
    - first_turn=False: continue debate with conversation history
    """
    if first_turn:
        return f"""
You are a debate generator AI.

Read the article below and generate a structured debate with exactly 5 points for each side.

Format your response as follows:

**FOR SIDE (5 Points):**
1. [Strong argument supporting the topic]
2. [Second supporting argument]
3. [Third supporting argument] 
4. [Fourth supporting argument]
5. [Fifth supporting argument]

**AGAINST SIDE (5 Points):**
1. [Strong argument opposing the topic]
2. [Second opposing argument]
3. [Third opposing argument]
4. [Fourth opposing argument]
5. [Fifth opposing argument]

Each point should be 1-2 sentences and directly relate to the article content.

Article:
{article_text}
"""
    else:
        return f"""
You are a debate generator AI continuing a debate. This is round {round_number}.

Previous debate context:
{article_text}

Generate 5 new points for the {side} side that build upon or respond to previous arguments.
Format your response as:

**{side.upper()} SIDE - Round {round_number} (5 Points):**
1. [New argument]
2. [New argument]
3. [New argument]
4. [New argument]
5. [New argument]

Each point should be 1-2 sentences and maintain relevance to the original topic.
If the topic has been exhausted, you may respond with fewer points or indicate "Topic exhausted."
"""

def calculate_relevance(debate_text, original_article):
    """
    Simple relevance calculation based on keyword overlap.
    In a real implementation, this could use more sophisticated NLP.
    """
    # Extract keywords from original article
    article_words = set(re.findall(r'\w+', original_article.lower()))
    article_words = {word for word in article_words if len(word) > 3}
    
    # Extract words from debate text
    debate_words = set(re.findall(r'\w+', debate_text.lower()))
    debate_words = {word for word in debate_words if len(word) > 3}
    
    # Calculate overlap
    if not article_words:
        return 100.0
    
    overlap = len(article_words.intersection(debate_words))
    relevance = (overlap / len(article_words)) * 100
    return min(100.0, relevance)

def generate_user_questions():
    """
    Generate three questions to ask the user about continuing the debate.
    """
    questions = [
        "Are you finding new insights from this debate?",
        "Do you want to explore more arguments on this topic?", 
        "Should the debate continue with additional points?"
    ]
    return questions

# --- Routes ---
@app.route("/start_debate", methods=["POST"])
def start_debate():
    """Start a new debate session"""
    global debate_state
    data = request.json
    article = data.get("article", "").strip()

    if not article:
        return jsonify({"error": "No article text provided"}), 400

    # Reset debate state
    debate_state = {
        "debate_history": [],
        "round_count": 0,
        "total_points": 0,
        "relevant_points": 0,
        "relevance_percentage": 100.0,
        "original_article": article
    }

    prompt = create_debate_prompt(article, first_turn=True)

    def stream_response():
        try:
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": True
            }
            response = requests.post(OLLAMA_API, json=payload, stream=True)
            response.raise_for_status()

            full_response = ""
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line.decode("utf-8"))
                        if "response" in chunk:
                            full_response += chunk["response"]
                            yield chunk["response"]
                    except json.JSONDecodeError:
                        continue
            
            # Update debate state
            debate_state["debate_history"].append(full_response)
            debate_state["round_count"] = 1
            debate_state["total_points"] = 10  # 5 for + 5 against
            debate_state["relevance_percentage"] = calculate_relevance(full_response, article)
            
        except requests.RequestException as e:
            yield f"Error connecting to Ollama: {e}"

    return app.response_class(stream_response(), mimetype="text/plain")

@app.route("/continue_debate", methods=["POST"])
def continue_debate():
    """Continue the debate with a new round"""
    global debate_state
    data = request.json
    side = data.get("side", "For")

    if not debate_state.get("original_article"):
        return jsonify({"error": "No active debate session"}), 400

    # Check if relevance is below 40%
    if debate_state["relevance_percentage"] < 40.0:
        return jsonify({
            "message": "Debate has reached the relevance threshold (40%). Gracefully ending the debate.",
            "final_relevance": debate_state["relevance_percentage"],
            "total_rounds": debate_state["round_count"]
        })

    debate_state["round_count"] += 1
    
    # Create context from debate history
    context = f"Original Article: {debate_state['original_article']}\n\n"
    context += "Previous debate rounds:\n" + "\n".join(debate_state["debate_history"])
    
    prompt = create_debate_prompt(context, side, first_turn=False, round_number=debate_state["round_count"])

    def stream_response():
        try:
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": True
            }
            response = requests.post(OLLAMA_API, json=payload, stream=True)
            response.raise_for_status()

            full_response = ""
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line.decode("utf-8"))
                        if "response" in chunk:
                            full_response += chunk["response"]
                            yield chunk["response"]
                    except json.JSONDecodeError:
                        continue
            
            # Update debate state
            debate_state["debate_history"].append(full_response)
            debate_state["total_points"] += 5  # 5 new points
            debate_state["relevance_percentage"] = calculate_relevance(full_response, debate_state["original_article"])
            
        except requests.RequestException as e:
            yield f"Error connecting to Ollama: {e}"

    return app.response_class(stream_response(), mimetype="text/plain")

@app.route("/get_user_questions", methods=["GET"])
def get_user_questions():
    """Get the three questions to ask the user"""
    questions = generate_user_questions()
    return jsonify({
        "questions": questions,
        "current_relevance": debate_state.get("relevance_percentage", 100.0),
        "round_count": debate_state.get("round_count", 0),
        "below_threshold": debate_state.get("relevance_percentage", 100.0) < 40.0
    })

@app.route("/debate_status", methods=["GET"])
def debate_status():
    """Get current debate status"""
    return jsonify(debate_state)

@app.route("/generate_debate", methods=["POST"])
def generate_debate():
    """Legacy endpoint - redirects to start_debate"""
    return start_debate()


if __name__ == "__main__":
    app.run(port=5000, debug=True)
