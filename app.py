from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
import re
from pathlib import Path
import numpy as np
from tensorflow.keras.preprocessing import image
from tensorflow.keras.layers import GlobalAveragePooling2D
from tensorflow.keras.models import Model, load_model
from tensorflow.keras.applications import efficientnet_v2
import sys

# Add CNN utilities
sys.path.append("/Users/syedsiddiq/FINAL_YEAR_PROJECT/SKIN_INTEL_BOT/cnn_model")
from utils_heatmap import gradcam

# ---------------------------
# Flask Setup
# ---------------------------
app = Flask(__name__)
CORS(app)

# ---------------------------
# Paths
# ---------------------------
BASE_DIR = "/Users/syedsiddiq/FINAL_YEAR_PROJECT/skin_datasets"
DISEASES_PATH = "/Users/syedsiddiq/FINAL_YEAR_PROJECT/SKIN_INTEL_BOT/diseases.json"
DB_PATH = os.path.join(BASE_DIR, "code", "feature_db.npz")
HEATMAP_DIR = os.path.join(BASE_DIR, "code", "heatmaps")
CLF_PATH = os.path.join(BASE_DIR, "model", "efficientnetv2_skin_model.h5")

os.makedirs(HEATMAP_DIR, exist_ok=True)

# ---------------------------
# Load disease DB
# ---------------------------
with open(DISEASES_PATH, "r") as f:
    DISEASES = json.load(f)

# ---------------------------
# Load Feature DB
# ---------------------------
db = np.load(DB_PATH, allow_pickle=True)
FEATURES = db['features'].astype("float32")
LABELS = db['labels']
SRCS = db['src']
FEATURES = np.array([f / (np.linalg.norm(f)+1e-10) for f in FEATURES])

# ---------------------------
# CNN Feature Extractor
# ---------------------------
base = efficientnet_v2.EfficientNetV2S(
    include_top=False,
    weights='imagenet',
    input_shape=(224, 224, 3)
)
FEAT_MODEL = Model(inputs=base.input,
                   outputs=GlobalAveragePooling2D()(base.output))
PREPROCESS = efficientnet_v2.preprocess_input

# ---------------------------
# Load classifier for Grad-CAM
# ---------------------------
CLF = None
if os.path.exists(CLF_PATH):
    try:
        CLF = load_model(CLF_PATH, compile=False)
        print("Classifier loaded.")
    except Exception as e:
        print("[WARN] Failed to load classifier:", e)

# ---------------------------
# LLM (Ollama)
# ---------------------------
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "phi3")
SYSTEM_PROMPT = (
    "You are Skin Intel Bot — a friendly skincare assistant. "
    "Respond concisely. Markdown only. "
    "Keep answers short unless the user asks for details."
)
OLLAMA_OPTIONS = {"num_ctx": 2048, "num_predict": 300}

# ---------------------------
# Synonyms
# ---------------------------
DISEASE_SYNONYMS = {
    "acne": ["pimples", "zits", "breakouts"],
    "eczema": ["dry skin", "itchy skin", "dermatitis"],
    "sunburn": ["sun damage", "burnt skin", "tanning burn"],
    "rash": ["skin irritation", "spots", "redness"],
    "psoriasis": ["scaly skin", "plaques", "flaky skin"],
    "blackheads": ["clogged pores", "whiteheads"],
    "shingles": ["herpes zoster", "blistering rash"]
}

# ============================================================
# Helper Functions
# ============================================================


def call_local_llm(prompt: str) -> str:
    import requests
    try:
        r = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "options": OLLAMA_OPTIONS,
                "stream": False
            },
            timeout=90
        )
        data = r.json()
        return data.get("message", {}).get("content", "").strip()
    except:
        return "The LLM is not responding right now."


def match_disease_with_synonyms(message: str):
    msg = message.lower()
    for entry in DISEASES:
        name = entry["disease"].lower()
        if name in msg:
            return entry
        for term in DISEASE_SYNONYMS.get(name, []):
            if term in msg:
                return entry
    return None


# def user_wants_location(message: str):
#     msg = message.lower()
#     keywords = ["hospital", "clinic", "doctor", "dermatologist", "near me"]
#     return any(k in msg for k in keywords)

# ============================================================
# CHAT ROUTE
# ============================================================


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json() or {}
    msg = (data.get("message") or "").strip().lower()

    if not msg:
        return jsonify({
            "reply": {
                "format": "markdown",
                "source": "none",
                "content": "Please type something 😄"
            }
        })

    # 1️⃣ Greeting
    if msg in ["hi", "hello", "hey", "yo"]:
        return jsonify({
            "reply": {
                "format": "markdown",
                "source": "local_rule",
                "content": "Hey! 👋 How can I help your skin today?"
            }
        })

    # 2️⃣ “How are you”
    if msg in ["how are you", "how r u", "how are u"]:
        return jsonify({
            "reply": {
                "format": "markdown",
                "source": "local_rule",
                "content": "Operational and moisturized 😄 How are *you* doing?"
            }
        })

    # 3️⃣ Disease match from local DB
    entry = match_disease_with_synonyms(msg)
    if entry:
        llm = call_local_llm(
            f"""
    You are a skin-care assistant. Provide a clean, simple **Markdown** response about **{entry['disease']}**.

    Follow this EXACT structure:
    - One short explanation (2–3 lines)
    - A bullet list of 3–5 practical tips
    - Do NOT include headings or titles
    - Do NOT add phrases like "Markdown Format"
    - Do NOT add dramatic or poetic lines
    - Keep tone friendly, normal, and clear
    - Fully complete your last sentence before stopping
    - Never end with an unfinished line

    Description: {entry['description']}
    Suggestions: {', '.join(entry.get('suggestions', []))}
    """
        )

        return jsonify({
            "reply": {
                "format": "markdown",
                "source": "local_database + global_llm",
                "content": llm
            }
        })

    # 4️⃣ Hospital / Location queries
    # if user_wants_location(msg):
    #     llm = call_local_llm(
    #         f"""
    #         User asked: {msg}.
    #         Give **exactly 3** short dermatologist/skin clinic suggestions (city only, no full addresses).
    #         Keep the response in plain bullet points.
    #         No headings. No extra text.
    #         """
    #     )

    #     return jsonify({
    #         "reply": {
    #             "format": "markdown",
    #             "source": "global_llm",
    #             "content": llm,
    #             "map_url": "https://www.google.com/maps/search/dermatologist+near+me"
    #         }
    #     })

    # 5️⃣ Normal non-disease question → short response
    llm = call_local_llm(
        f"""
        User said: '{msg}'.
        Give a short 2–3 line reply.
        Do NOT use headings.
        Keep it friendly and simple.
        Markdown allowed but keep it minimal.
        """
    )

    return jsonify({
        "reply": {
            "format": "markdown",
            "source": "global_llm",
            "content": llm
        }
    })

# ============================================================
# IMAGE PREDICTION ROUTE
# ============================================================


@app.route("/predict", methods=["POST"])
def predict():
    if "image" not in request.files:
        return jsonify({"error": "No image provided"}), 400

    # --------------------------------------------------
    # SAVE IMAGE
    # --------------------------------------------------
    img_file = request.files["image"]
    img_path = os.path.join("/tmp", img_file.filename)
    img_file.save(img_path)

    # --------------------------------------------------
    # IMAGE → FEATURES
    # --------------------------------------------------
    img = image.load_img(img_path, target_size=(224, 224))
    arr = image.img_to_array(img)[None]
    arr_pre = PREPROCESS(arr)

    feat = FEAT_MODEL.predict(arr_pre, verbose=0)[0]
    feat = feat / (np.linalg.norm(feat) + 1e-10)

    # --------------------------------------------------
    # COSINE SIMILARITY
    # --------------------------------------------------
    sims = FEATURES.dot(feat)
    sims_norm = (sims + 1) / 2

    K = 5
    idx = sims_norm.argsort()[-K:][::-1]
    lbls = LABELS[idx]
    sim_scores = sims_norm[idx]

    votes = {}
    for l, w in zip(lbls, sim_scores):
        votes[l] = votes.get(l, 0) + float(w)

    pred = max(votes.items(), key=lambda x: x[1])[0]
    confidence = min(1.0, votes[pred] / (sum(sim_scores) + 1e-9))

    # --------------------------------------------------
    # IF CONFIDENCE TOO LOW → RETURN UNKNOWN (NO LLM)
    # --------------------------------------------------
    if confidence < 0.60:
        return jsonify({
            "reply": {
                "format": "markdown",
                "source": "image_model",
                "content": "**UNKNOWN**\n\nThe model is not confident enough to identify this condition."
            },
            "disease": "UNKNOWN",
            "confidence": float(confidence)
        })

    # --------------------------------------------------
    # FETCH DISEASE ENTRY (KNOWN CASE)
    # --------------------------------------------------
    entry = next(
        (d for d in DISEASES if d["disease"].lower() == pred.lower()),
        {"disease": pred, "description": "", "suggestions": []}
    )

    # --------------------------------------------------
    # LLM CALL (ONLY FOR KNOWN DISEASES)
    # --------------------------------------------------
    llm_raw = call_local_llm(
f"""
You are a skin-care assistant. Return the output in **pure Markdown**.

⚠️ Follow this EXACT FORMAT — DO NOT modify the structure:

Explanation:
A short 2–3 sentence explanation about the condition. No bullet points.

Causes:
- Clear bullet point 1
- Clear bullet point 2
- Clear bullet point 3
- Clear bullet point 4

Self-care Tips:
- Clear bullet point 1
- Clear bullet point 2
- Clear bullet point 3
- Clear bullet point 4

STRICT RULES:
- Only these three section titles.
- Titles MUST NOT be changed.
- Add one blank line after each title.
- Bullets must start with "- ".
- No extra headings.
- No introductions or summaries.
- No unfinished sentences.
- Markdown only.

Description: {entry['description']}
Suggestions: {', '.join(entry.get('suggestions', []))}
"""
    )

    # --------------------------------------------------
    # POST FORMATTING: BULLETS + SPACING FIX
    # --------------------------------------------------
    def fix_markdown(md):
        if not md:
            return "Formatting error: empty response."

        md = re.sub(r"\bExplanation\s*:\s*", "Explanation:\n\n", md, flags=re.I)
        md = re.sub(r"\bCauses\s*:\s*", "\n\nCauses:\n\n", md, flags=re.I)
        md = re.sub(r"\bSelf-care Tips\s*:\s*", "\n\nSelf-care Tips:\n\n", md, flags=re.I)

        md = re.sub(r"\n-\s*", "\n- ", md)
        md = re.sub(r"([a-zA-Z0-9]) - ", r"\1\n- ", md)

        md = re.sub(r"\n{3,}", "\n\n", md)

        return md.strip()

    llm = fix_markdown(llm_raw)

    # --------------------------------------------------
    # FINAL RESPONSE (KNOWN DISEASE)
    # --------------------------------------------------
    return jsonify({
        "reply": {
            "format": "markdown",
            "source": "image_model + global_llm",
            "content": llm
        },
        "disease": pred,
        "confidence": float(confidence)
    })



# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
