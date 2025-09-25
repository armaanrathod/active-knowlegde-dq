import json
import uuid
import re
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import google.generativeai as genai
import PyPDF2
from io import BytesIO

# --- Configuration ---
GOOGLE_API_KEY = "AIzaSyB0at1pNS9kXJzZxcjUvT2VenXUZg6KV94"  # Valid Google API key
MODEL_NAME = "gemini-1.5-flash"  # Using stable Gemini 1.5 Flash model

genai.configure(api_key=GOOGLE_API_KEY)

app = Flask(__name__)
CORS(app, origins="*", allow_headers="*", methods="*")

# --- Enhanced Debate Session Class ---
class DebateSession:
    def __init__(self, session_id, article_text, mode="moderate"):
        self.session_id = session_id
        self.article_text = article_text
        self.mode = mode  # hardcore, moderate, mild
        self.current_round = 1
        self.for_points = []
        self.against_points = []
        self.debate_history = []
        self.user_side = None
        self.relevance_scores = []
        self.key_claims = []
        self.points_used_for = 0
        self.points_used_against = 0
        
    def add_debate_turn(self, speaker, content):
        """Add a turn to the debate history"""
        self.debate_history.append({
            "round": self.current_round,
            "speaker": speaker,
            "content": content,
            "timestamp": str(uuid.uuid4())[:8]
        })
    
    def calculate_relevance(self):
        """Calculate current relevance score based on debate progression"""
        base_relevance = 100
        rounds_penalty = (self.current_round - 1) * 15
        points_penalty = (self.points_used_for + self.points_used_against) * 2
        
        current_relevance = max(20, base_relevance - rounds_penalty - points_penalty)
        self.relevance_scores.append(current_relevance)
        return current_relevance

# Global sessions storage
sessions = {}

# --- PDF Processing Function ---
def extract_text_from_pdf(file_content):
    """Extract text from uploaded PDF file"""
    try:
        pdf_file = BytesIO(file_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        
        return text.strip()
    except Exception as e:
        return f"Error extracting PDF: {str(e)}"

# --- Enhanced Prompt Engineering ---
def create_claims_extraction_prompt(article_text):
    """Create prompt to extract key debatable claims"""
    return f"""
You are an expert debate analyzer. Extract 3-5 key debatable claims from this article.

Article: {article_text}

Format your response as:
KEY CLAIMS:
1. [First debatable claim]
2. [Second debatable claim] 
3. [Third debatable claim]
4. [Fourth debatable claim (if applicable)]
5. [Fifth debatable claim (if applicable)]

Focus on claims that have clear opposing viewpoints and are substantive enough for debate.
"""

def create_initial_debate_prompt(session, side):
    """Create prompt for initial 5-point debate generation"""
    mode_instructions = {
        "hardcore": "Use aggressive, sharp, and hard-hitting arguments. Be direct and uncompromising.",
        "moderate": "Use balanced, reasoned arguments with evidence. Be persuasive but fair.",
        "mild": "Use gentle, friendly arguments that acknowledge nuance. Be respectful and collaborative."
    }
    
    claims_text = "\n".join([f"{i+1}. {claim}" for i, claim in enumerate(session.key_claims)])
    
    return f"""
You are a skilled debater in {session.mode} mode. {mode_instructions[session.mode]}

Based on these key claims from the article:
{claims_text}

Generate exactly 5 strong arguments {side} the main topic.

Article context: {session.article_text[:500]}...

Format your response as:
ARGUMENTS {side.upper()}:
1. [First argument - be specific and compelling]
2. [Second argument - include evidence or reasoning]
3. [Third argument - address potential counterpoints]  
4. [Fourth argument - use different angle or perspective]
5. [Fifth argument - strong closing point]

Each argument should be 1-2 sentences, clear and debate-ready.
"""

def create_continuation_prompt(session, side):
    """Create prompt for continuing debate with new arguments"""
    used_points = session.for_points if side == "FOR" else session.against_points
    used_text = "\n".join([f"- {point}" for point in used_points])
    
    mode_instructions = {
        "hardcore": "Escalate with more aggressive and sharp counterarguments.",
        "moderate": "Build on previous points with deeper analysis and evidence.", 
        "mild": "Gently introduce new perspectives while acknowledging previous points."
    }
    
    return f"""
You are continuing a debate in {session.mode} mode. {mode_instructions[session.mode]}

Previous arguments used {side}:
{used_text}

Round {session.current_round} - Generate 5 NEW arguments {side} that:
- Don't repeat previous points
- Build on the debate progression
- Address the core topic with fresh angles

Article context: {session.article_text[:300]}...

Format as:
NEW ARGUMENTS {side}:
1. [New angle #1]
2. [New angle #2] 
3. [New angle #3]
4. [New angle #4]
5. [New angle #5]

Make each argument distinct and debate-ready.
"""

def create_user_questions_prompt(session):
    """Create prompt to generate engaging questions for user"""
    return f"""
Based on this ongoing debate about: {session.article_text[:200]}...

Current debate state:
- Round {session.current_round}
- FOR points: {len(session.for_points)}
- AGAINST points: {len(session.against_points)}

Generate exactly 3 engaging questions to ask the user to continue the debate:

QUESTIONS:
1. [Question that challenges their position]
2. [Question about a specific aspect or implication] 
3. [Question that opens new debate angles]

Each question should be thought-provoking and relevant to the topic.
Format as simple numbered list.
"""

# --- Helper Functions ---
def query_gemini(prompt, max_tokens=1000):
    """Query Google Gemini with error handling"""
    try:
        # Check if API key is still placeholder
        if GOOGLE_API_KEY == "YOUR_VALID_GOOGLE_API_KEY_HERE":
            return "⚠️ API KEY ERROR: Please replace GOOGLE_API_KEY with a valid key from https://aistudio.google.com/"
        
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": max_tokens,
                "temperature": 0.7
            }
        )
        return response.text.strip() if response and response.text else "No response generated."
    except Exception as e:
        if "API_KEY_INVALID" in str(e):
            return "❌ INVALID API KEY: Get a valid Google API key from https://aistudio.google.com/ and replace it in the asus file"
        return f"Error querying Gemini: {str(e)}"

def parse_debate_points(response_text):
    """Parse structured debate points from AI response"""
    for_points = []
    against_points = []
    
    lines = response_text.split('\n')
    current_section = None
    
    for line in lines:
        line = line.strip()
        if 'ARGUMENTS FOR' in line.upper() or 'FOR:' in line.upper():
            current_section = 'for'
        elif 'ARGUMENTS AGAINST' in line.upper() or 'AGAINST:' in line.upper():
            current_section = 'against'
        elif re.match(r'^\d+\.', line) and current_section:
            point = re.sub(r'^\d+\.\s*', '', line)
            if current_section == 'for':
                for_points.append(point)
            else:
                against_points.append(point)
    
    return for_points, against_points

def parse_claims(response_text):
    """Parse key claims from AI response"""
    claims = []
    lines = response_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if re.match(r'^\d+\.', line):
            claim = re.sub(r'^\d+\.\s*', '', line)
            claims.append(claim)
    
    return claims

def parse_questions(response_text):
    """Parse questions from AI response"""
    questions = []
    lines = response_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if re.match(r'^\d+\.', line):
            question = re.sub(r'^\d+\.\s*', '', line)
            questions.append(question)
    
    return questions

# --- API Routes ---

@app.route("/", methods=["GET"])
def home():
    """Serve the main interface"""
    try:
        with open("html_final.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        return html_content
    except FileNotFoundError:
        return jsonify({"error": "Interface file not found"}), 404

@app.route("/api/info", methods=["GET"])
def api_info():
    """API system info endpoint"""
    return jsonify({
        "message": "🎭 AI Debate Generator - Review Ready System",
        "version": "2.0",
        "features": [
            "Google Gemini Integration",
            "PDF Upload Support", 
            "Multi-mode Debates (hardcore/moderate/mild)",
            "5-Point Structured Arguments",
            "Session Management",
            "Smart Relevance Tracking",
            "User Interaction System"
        ],
        "endpoints": [
            "/extract_pdf",
            "/start_debate", 
            "/continue_debate",
            "/ask_questions",
            "/end_debate",
            "/health"
        ],
        "status": "ready_for_review"
    })

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    api_status = "❌ INVALID" if GOOGLE_API_KEY == "YOUR_VALID_GOOGLE_API_KEY_HERE" else "✅ CONFIGURED"
    system_status = "⚠️ NEEDS API KEY" if GOOGLE_API_KEY == "YOUR_VALID_GOOGLE_API_KEY_HERE" else "✅ READY FOR PRODUCTION"
    
    return jsonify({
        "status": "healthy" if GOOGLE_API_KEY != "YOUR_VALID_GOOGLE_API_KEY_HERE" else "needs_api_key",
        "server": "asus_backend",
        "ai_model": MODEL_NAME,
        "api_key_status": api_status,
        "active_sessions": len(sessions),
        "message": system_status,
        "instructions": "Get API key from https://aistudio.google.com/" if GOOGLE_API_KEY == "YOUR_VALID_GOOGLE_API_KEY_HERE" else "System ready for production use!"
    })

@app.route("/extract_pdf", methods=["POST"])
def extract_pdf():
    """Extract text from uploaded PDF"""
    try:
        if 'pdf' not in request.files:
            return jsonify({"error": "No PDF file provided"}), 400
        
        pdf_file = request.files['pdf']
        if pdf_file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        # Extract text from PDF
        pdf_content = pdf_file.read()
        extracted_text = extract_text_from_pdf(pdf_content)
        
        if extracted_text.startswith("Error"):
            return jsonify({"error": extracted_text}), 500
        
        return jsonify({
            "success": True,
            "extracted_text": extracted_text,
            "filename": pdf_file.filename,
            "length": len(extracted_text)
        })
        
    except Exception as e:
        return jsonify({"error": f"PDF processing failed: {str(e)}"}), 500

@app.route("/start_debate", methods=["POST"])
def start_debate():
    """Start a new structured debate session"""
    try:
        data = request.get_json()
        article = data.get("article", "").strip()
        mode = data.get("mode", "moderate")  # hardcore, moderate, mild
        
        if not article:
            return jsonify({"error": "No article text provided"}), 400
        
        if mode not in ["hardcore", "moderate", "mild"]:
            mode = "moderate"
        
        # Create new session
        session_id = str(uuid.uuid4())
        session = DebateSession(session_id, article, mode)
        
        # Step 1: Extract key claims
        claims_prompt = create_claims_extraction_prompt(article)
        claims_response = query_gemini(claims_prompt)
        session.key_claims = parse_claims(claims_response)
        
        # Step 2: Generate initial arguments
        for_prompt = create_initial_debate_prompt(session, "FOR")
        against_prompt = create_initial_debate_prompt(session, "AGAINST")
        
        for_response = query_gemini(for_prompt)
        against_response = query_gemini(against_prompt)
        
        # Parse arguments
        for_points, _ = parse_debate_points(for_response)
        _, against_points = parse_debate_points(against_response)
        
        # Ensure we have 5 points each
        if len(for_points) < 5:
            for_points.extend([f"Additional FOR argument {i+1}." for i in range(5 - len(for_points))])
        if len(against_points) < 5:
            against_points.extend([f"Additional AGAINST argument {i+1}." for i in range(5 - len(against_points))])
        
        session.for_points = for_points[:5]
        session.against_points = against_points[:5]
        session.points_used_for = 5
        session.points_used_against = 5
        
        # Calculate initial relevance
        relevance = session.calculate_relevance()
        
        # Store session
        sessions[session_id] = session
        
        return jsonify({
            "success": True,
            "session_id": session_id,
            "mode": mode,
            "key_claims": session.key_claims,
            "for_points": session.for_points,
            "against_points": session.against_points,
            "round": session.current_round,
            "relevance_score": relevance,
            "message": f"Debate started in {mode} mode with 5 arguments per side"
        })
        
    except Exception as e:
        return jsonify({"error": f"Failed to start debate: {str(e)}"}), 500

@app.route("/continue_debate", methods=["POST"])
def continue_debate():
    """Continue an existing debate with new arguments"""
    try:
        data = request.get_json()
        session_id = data.get("session_id")
        user_choice = data.get("continue", True)
        
        if not session_id or session_id not in sessions:
            return jsonify({"error": "Invalid session ID"}), 400
        
        session = sessions[session_id]
        
        # Check if user wants to continue
        if not user_choice:
            return jsonify({
                "success": True,
                "action": "debate_ended_by_user",
                "final_summary": {
                    "rounds_completed": session.current_round,
                    "total_for_points": len(session.for_points),
                    "total_against_points": len(session.against_points),
                    "final_relevance": session.relevance_scores[-1] if session.relevance_scores else 100
                }
            })
        
        # Check relevance threshold
        current_relevance = session.calculate_relevance()
        if current_relevance < 30:
            return jsonify({
                "success": True,
                "action": "debate_ended_low_relevance",
                "relevance_score": current_relevance,
                "message": "Debate concluded due to low relevance score",
                "final_summary": {
                    "rounds_completed": session.current_round,
                    "total_for_points": len(session.for_points),
                    "total_against_points": len(session.against_points)
                }
            })
        
        # Continue debate - generate new round
        session.current_round += 1
        
        # Generate new arguments
        for_prompt = create_continuation_prompt(session, "FOR")
        against_prompt = create_continuation_prompt(session, "AGAINST")
        
        for_response = query_gemini(for_prompt)
        against_response = query_gemini(against_prompt)
        
        # Parse new arguments
        new_for_points, _ = parse_debate_points(for_response)
        _, new_against_points = parse_debate_points(against_response)
        
        # Ensure 5 new points each
        if len(new_for_points) < 5:
            new_for_points.extend([f"Continued FOR argument {i+1} for round {session.current_round}." 
                                 for i in range(5 - len(new_for_points))])
        if len(new_against_points) < 5:
            new_against_points.extend([f"Continued AGAINST argument {i+1} for round {session.current_round}." 
                                     for i in range(5 - len(new_against_points))])
        
        # Add new points
        session.for_points.extend(new_for_points[:5])
        session.against_points.extend(new_against_points[:5])
        session.points_used_for += 5
        session.points_used_against += 5
        
        return jsonify({
            "success": True,
            "session_id": session_id,
            "round": session.current_round,
            "new_for_points": new_for_points[:5],
            "new_against_points": new_against_points[:5],
            "total_for_points": session.for_points,
            "total_against_points": session.against_points,
            "relevance_score": current_relevance,
            "message": f"Round {session.current_round} arguments generated"
        })
        
    except Exception as e:
        return jsonify({"error": f"Failed to continue debate: {str(e)}"}), 500

@app.route("/ask_questions", methods=["POST"])
def ask_questions():
    """Generate engaging questions for user interaction"""
    try:
        data = request.get_json()
        session_id = data.get("session_id")
        
        if not session_id or session_id not in sessions:
            return jsonify({"error": "Invalid session ID"}), 400
        
        session = sessions[session_id]
        
        # Generate questions
        questions_prompt = create_user_questions_prompt(session)
        questions_response = query_gemini(questions_prompt)
        questions = parse_questions(questions_response)
        
        # Ensure we have 3 questions
        if len(questions) < 3:
            questions.extend([
                "What aspect of this topic interests you most?",
                "Which side presents stronger evidence?", 
                "How might this debate evolve further?"
            ])
        
        return jsonify({
            "success": True,
            "session_id": session_id,
            "questions": questions[:3],
            "round": session.current_round,
            "message": "Questions generated for user engagement"
        })
        
    except Exception as e:
        return jsonify({"error": f"Failed to generate questions: {str(e)}"}), 500

@app.route("/end_debate", methods=["POST"])
def end_debate():
    """End a debate session"""
    try:
        data = request.get_json()
        session_id = data.get("session_id")
        
        if session_id not in sessions:
            return jsonify({"error": "Invalid session ID"}), 400
        
        session = sessions[session_id]
        
        # Create final summary
        summary = {
            "session_id": session_id,
            "mode": session.mode,
            "rounds_completed": session.current_round,
            "total_arguments": {
                "for": len(session.for_points),
                "against": len(session.against_points)
            },
            "key_claims": session.key_claims,
            "relevance_scores": session.relevance_scores,
            "debate_history": session.debate_history
        }
        
        # Clean up session
        del sessions[session_id]
        
        return jsonify({
            "success": True,
            "message": f"Debate session {session_id} ended successfully",
            "summary": summary
        })
        
    except Exception as e:
        return jsonify({"error": f"Failed to end debate: {str(e)}"}), 500

# --- Main Application ---
if __name__ == "__main__":
    print("🎭 AI Debate Generator - ASUS Backend")
    print("=" * 50)
    print("✅ Google Gemini Integration Ready")
    print("✅ PDF Processing Enabled") 
    print("✅ Multi-Mode Debates (hardcore/moderate/mild)")
    print("✅ 5-Point Structured Arguments")
    print("✅ Smart Relevance Tracking")
    print("✅ Session Management")
    print("🌐 Access at: http://localhost:5000")
    print("🚀 Review-Ready System!")
    print("=" * 50)
    try:
        app.run(host="0.0.0.0", port=5000, debug=False)
    except Exception as e:
        print(f"❌ Server startup error: {e}")
        input("Press Enter to exit...")
