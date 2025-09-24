# backend_debate.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import nltk
from nltk.corpus import stopwords
import string

# ------------------------
# NLTK Setup
# ------------------------
nltk.download("punkt")
nltk.download("averaged_perceptron_tagger")
nltk.download("stopwords")
stop_words = set(stopwords.words("english"))

# ------------------------
# FastAPI App
# ------------------------
app = FastAPI(
    title="Article → Live Debate API",
    description="Turns any passage into a live debate with Pro/Con arguments.",
    version="1.0.0"
)

# ------------------------
# Request/Response Models
# ------------------------
class DebateRequest(BaseModel):
    text: str
    max_points: int = 15   # default 15, can go up to 20 or more

class DebateResponse(BaseModel):
    key_points: list[str]
    debate: list[dict]

# ------------------------
# Determine if a point is debatable
# ------------------------
def is_debatable(point: str) -> bool:
    """
    Returns True if a point is debatable, False if factual.
    """
    debatable_keywords = ["should", "might", "complex", "issue", "problem", "benefit", "impact"]

    # Numeric facts are not debatable
    if any(char.isdigit() for char in point):
        return False

    # Debatable if keyword present
    for kw in debatable_keywords:
        if kw in point.lower():
            return True

    # Short noun phrases are usually factual
    if len(point.split()) <= 3:
        return False

    return True

# ------------------------
# Extract Key Points Logic (Improved Readability)
# ------------------------
def extract_key_points(text: str, max_points: int = 20):
    """
    Extract key points from text with improved readability:
    - Prioritize nouns & proper nouns
    - Merge short factual points with surrounding context
    - Skip stopwords/punctuation
    - Fallback to full sentence if needed
    """
    sentences = nltk.sent_tokenize(text)
    key_points = []

    for sent in sentences:
        words = nltk.word_tokenize(sent)
        tagged = nltk.pos_tag(words)

        nouns = [
            word for word, pos in tagged
            if pos.startswith("NN") and word.lower() not in stop_words and word not in string.punctuation
        ]

        if nouns:
            point = " ".join(nouns)
            # Improve readability for short factual points
            if len(point.split()) <= 3 and not is_debatable(point):
                # Grab first 6-8 words from sentence for context
                point = " ".join(words[:8])
            key_points.append(point)
        else:
            trimmed = sent.strip()
            if trimmed:
                key_points.append(trimmed)

    # Remove duplicates while keeping order
    seen = set()
    unique_points = []
    for point in key_points:
        if point not in seen:
            seen.add(point)
            unique_points.append(point)

    return unique_points[:max_points] if unique_points else ["General discussion point"]

# ------------------------
# Debate Generator
# ------------------------
def debate_on_points(points):
    debate = []
    for point in points:
        if is_debatable(point):
            pro = f"✅ Pro: The point '{point}' has arguments in its favor."
            con = f"❌ Con: The point '{point}' can be challenged or analyzed differently."
            debate.append({"point": point, "pro": pro, "con": con})
        else:
            debate.append({"point": point, "pro": "ℹ️ Fact: Not debatable", "con": "ℹ️ Fact: Not debatable"})
    return debate

# ------------------------
# Routes
# ------------------------
@app.get("/status")
async def status():
    return {"status": "ok", "message": "Live Debate backend is running 🚀"}

@app.post("/debate", response_model=DebateResponse)
async def debate(request: DebateRequest):
    if not request.text.strip():
        return JSONResponse(
            status_code=400,
            content={"error": "No text provided. Please send valid text."}
        )

    key_points = extract_key_points(request.text, request.max_points)
    debate_result = debate_on_points(key_points)

    return DebateResponse(key_points=key_points, debate=debate_result)
