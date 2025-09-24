# active-knowlegde-dq

Our project turns any article into a live debate! Our webpage extracts key points, creates two AI personas arguing for and against the ideas, and lets the user join in. It makes reading active by letting you interact, challenge, and think critically about the content. Making the boring task of learning an active process.

## Enhanced Debate System

The enhanced debate system now features:

### 🎯 Core Features
- **5-Point Generation**: LLM generates exactly 5 strong points FOR and 5 points AGAINST any article topic
- **3-Question Engagement**: System asks users 3 thought-provoking questions to gauge interest
- **Intelligent Continuation**: Based on user responses, the system continues with additional 5-point rounds
- **Relevance Scoring**: Each argument point is scored for relevance (1-100%)
- **Graceful Exit**: System automatically ends when average relevance drops below 40%

### 🖥️ Files Structure
- `backend_debate.py` - Enhanced Flask backend with new endpoints
- `enhanced_debate.html` - Complete frontend with interactive debate interface
- `backend_debate_mock.py` - Mock version for testing without Ollama
- `requirements.txt` - Python dependencies

### 🚀 Quick Start
1. Install dependencies: `pip install -r requirements.txt`
2. Start the backend: `python backend_debate.py` (requires Ollama) or `python backend_debate_mock.py` (for testing)
3. Open `enhanced_debate.html` in a browser
4. Paste an article and start debating!

### 📊 API Endpoints
- `POST /start_debate` - Initialize debate with 5 FOR/AGAINST points
- `POST /generate_questions` - Get 3 engagement questions
- `POST /continue_debate` - Continue with additional 5 points based on user responses
- `GET /get_session` - Retrieve current debate session state

### 🎮 User Flow
1. User pastes article text
2. System generates initial 5 FOR and 5 AGAINST points
3. System presents 3 engagement questions
4. User answers questions and selects debate side (FOR/AGAINST)
5. If user shows interest (yes responses), system generates 5 additional points
6. Process repeats until relevance drops below 40% threshold
7. System gracefully exits with final summary

The system creates an engaging, interactive debate experience that adapts to user interest and maintains high-quality argumentation through relevance scoring.
