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

# Global state for debate sessions
debate_sessions = {}

# --- Prompt helpers ---
def create_initial_points_prompt(article_text):
    """Generate 5 points for and against the article topic"""
    return f"""
You are a debate generator AI. Read the article below and generate exactly 5 strong points FOR and 5 strong points AGAINST the main arguments presented.

Format your response exactly as:

FOR:
1. [Point 1]
2. [Point 2]
3. [Point 3]
4. [Point 4]
5. [Point 5]

AGAINST:
1. [Point 1]
2. [Point 2]
3. [Point 3]
4. [Point 4]
5. [Point 5]

Each point should be 1-2 sentences maximum. Focus on the most compelling arguments.

Article:
{article_text}
"""

def create_continuation_prompt(article_text, conversation_history, side, round_num):
    """Generate additional points for continuing the debate"""
    return f"""
You are continuing a debate. Based on the article and conversation history, generate 5 additional strong points for the {side} side.

Conversation so far:
{conversation_history}

Your task:
- Generate exactly 5 new points for the {side} side
- Make sure these points are different from what was already discussed
- Rate the relevance of each point from 1-100
- If most points would have relevance below 40, respond with: "DEBATE_EXHAUSTED: No further meaningful arguments available."

Format your response as:
1. [Point 1] (Relevance: XX%)
2. [Point 2] (Relevance: XX%)
3. [Point 3] (Relevance: XX%)
4. [Point 4] (Relevance: XX%)
5. [Point 5] (Relevance: XX%)

Article:
{article_text}
"""

def create_questions_prompt(article_text, current_points):
    """Generate 3 engagement questions for the user"""
    return f"""
Based on the debate points below, create exactly 3 thought-provoking questions that would help determine if the user wants to continue the debate.

Current debate points:
{current_points}

Generate exactly 3 questions in this format:
1. [Question 1]
2. [Question 2]  
3. [Question 3]

Each question should encourage critical thinking about the topic and help gauge user interest in continuing.

Article context:
{article_text}
"""

# --- Helper functions ---
def call_ollama(prompt):
    """Make a synchronous call to Ollama API"""
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False
        }
        response = requests.post(OLLAMA_API, json=payload)
        response.raise_for_status()
        return response.json().get("response", "")
    except requests.RequestException as e:
        return f"Error connecting to Ollama: {e}"

def parse_relevance_scores(text):
    """Extract relevance scores from debate points"""
    relevance_pattern = r'Relevance:\s*(\d+)%'
    scores = [int(match) for match in re.findall(relevance_pattern, text)]
    return scores

def should_continue_debate(relevance_scores, threshold=40):
    """Determine if debate should continue based on relevance scores"""
    if not relevance_scores:
        return True
    avg_relevance = sum(relevance_scores) / len(relevance_scores)
    return avg_relevance >= threshold

# --- Routes ---
@app.route("/start_debate", methods=["POST"])
def start_debate():
    """Start a new debate session with initial 5 points for and against"""
    data = request.json
    article = data.get("article", "").strip()
    session_id = data.get("session_id", "default")
    
    if not article:
        return jsonify({"error": "No article text provided"}), 400
    
    # Generate initial points
    prompt = create_initial_points_prompt(article)
    response = call_ollama(prompt)
    
    if response.startswith("Error"):
        return jsonify({"error": response}), 500
    
    # Initialize session
    debate_sessions[session_id] = {
        "article": article,
        "conversation_history": response,
        "round": 1,
        "total_rounds": 1
    }
    
    return jsonify({
        "session_id": session_id,
        "initial_points": response,
        "round": 1
    })

@app.route("/generate_questions", methods=["POST"])
def generate_questions():
    """Generate 3 questions for user engagement"""
    data = request.json
    session_id = data.get("session_id", "default")
    
    if session_id not in debate_sessions:
        return jsonify({"error": "Session not found"}), 404
    
    session = debate_sessions[session_id]
    prompt = create_questions_prompt(session["article"], session["conversation_history"])
    questions = call_ollama(prompt)
    
    if questions.startswith("Error"):
        return jsonify({"error": questions}), 500
    
    return jsonify({
        "questions": questions,
        "session_id": session_id
    })

@app.route("/continue_debate", methods=["POST"])
def continue_debate():
    """Continue debate with additional 5 points based on user responses"""
    data = request.json
    session_id = data.get("session_id", "default")
    side = data.get("side", "For")  # "For" or "Against"
    user_responses = data.get("user_responses", [])
    
    if session_id not in debate_sessions:
        return jsonify({"error": "Session not found"}), 404
    
    session = debate_sessions[session_id]
    
    # Check if user wants to continue (at least one "yes" response)
    continue_debate_flag = any(response.lower() in ["yes", "y", "continue", "true"] for response in user_responses)
    
    if not continue_debate_flag:
        return jsonify({
            "message": "Debate ended by user choice.",
            "session_ended": True
        })
    
    # Generate continuation points
    prompt = create_continuation_prompt(
        session["article"], 
        session["conversation_history"],
        side,
        session["round"] + 1
    )
    response = call_ollama(prompt)
    
    if response.startswith("Error"):
        return jsonify({"error": response}), 500
    
    # Check if debate should be exhausted
    if "DEBATE_EXHAUSTED" in response:
        return jsonify({
            "message": "Debate concluded: No further meaningful arguments available.",
            "session_ended": True
        })
    
    # Check relevance scores
    relevance_scores = parse_relevance_scores(response)
    if relevance_scores and not should_continue_debate(relevance_scores):
        return jsonify({
            "message": "Debate concluded: Relevance threshold reached (below 40%).",
            "session_ended": True,
            "final_points": response
        })
    
    # Update session
    session["conversation_history"] += f"\n\nRound {session['round'] + 1} ({side}):\n{response}"
    session["round"] += 1
    session["total_rounds"] += 1
    
    return jsonify({
        "new_points": response,
        "round": session["round"],
        "session_id": session_id,
        "relevance_scores": relevance_scores
    })

@app.route("/get_session", methods=["GET"])
def get_session():
    """Get current session state"""
    session_id = request.args.get("session_id", "default")
    
    if session_id not in debate_sessions:
        return jsonify({"error": "Session not found"}), 404
    
    return jsonify(debate_sessions[session_id])


if __name__ == "__main__":
    app.run(port=5000, debug=True)
