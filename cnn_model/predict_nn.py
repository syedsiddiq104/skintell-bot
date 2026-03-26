# # !/usr/bin/env python3
# """
# predict_nn_top1_only.py

# Behavior:
#  - Compute similarity-based predictions for all images in TEST_DIR.
#  - Sort by confidence (vote score).
#  - Keep the Top-1 prediction (generate heatmap for it if possible).
#  - Force every other image to: prediction="unknown", confidence=0.0, heatmap=None.
#  - Save CSV with Top-1 first (then the unknowns).
# """

# #!/usr/bin/env python3
# """
# predict_nn_threshold_unknown.py

# Behavior:
#  - Compute similarity-based predictions for all images in TEST_DIR.
#  - For each image: if pred_score < UNKNOWN_THRESHOLD -> final_label = "unknown"
#    otherwise keep predicted label.
#  - Generate heatmaps only for images that are NOT "unknown" (and if classifier is available).
#  - Save CSV with all images included and print summary.
# """

# #!/usr/bin/env python3
# """
# predict_nn_simthreshold.py

# Behavior:
#  - Compute similarity-based predictions for all images in TEST_DIR.
#  - Use the top-K neighbors to vote for a label (as before).
#  - If best_match_sim (the highest neighbor similarity, in [0,1]) >= SIM_THRESHOLD:
#        final_label = predicted label
#    else:
#        final_label = "unknown"
#  - Generate heatmaps only for final_label != "unknown" (and if classifier is present).
#  - Save CSV with all images included and print summary.
# """

# import os
# import csv
# import numpy as np
# from pathlib import Path
# from tensorflow.keras.preprocessing import image
# from tensorflow.keras.layers import GlobalAveragePooling2D
# from tensorflow.keras.models import Model, load_model
# from tensorflow.keras.applications import efficientnet_v2

# # optional: import your gradcam helper (must be available)
# from utils_heatmap import gradcam

# # ---------------------------
# # Uploaded screenshot (local path; your system will convert to a URL)
# # ---------------------------
# UPLOADED_SCREENSHOT_PATH = "/mnt/data/Screenshot 2025-11-24 202513.png"

# # ---------------------------
# # Config / paths (adjust as needed)
# # ---------------------------
# BASE_DIR = "/Users/syedsiddiq/FINAL_YEAR_PROJECT/skin_datasets"
# DB_PATH = os.path.join(BASE_DIR, "code", "feature_db.npz")
# TEST_DIR = os.path.join(BASE_DIR, "test")
# HEATMAP_DIR = os.path.join(BASE_DIR, "code", "heatmaps")
# OUT_CSV = os.path.join(BASE_DIR, "code", "predictions_simthreshold.csv")

# os.makedirs(HEATMAP_DIR, exist_ok=True)
# os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)

# # Parameters
# K = 5                       # number of neighbors for voting
# SIM_THRESHOLD = 0.70        # best_match_sim threshold to keep as known
# TARGET_SIZE = (224, 224)

# # ---------------------------
# # Load DB (features, labels, src)
# # ---------------------------
# if not os.path.exists(DB_PATH):
#     raise FileNotFoundError(f"Feature DB not found: {DB_PATH}")

# db = np.load(DB_PATH, allow_pickle=True)
# features = db['features'].astype("float32")   # shape: (N, feat_dim)
# labels = db['labels']
# srcs = db['src']
# print("DB loaded:", features.shape)

# # ---------------------------
# # Prepare feature extractor
# # ---------------------------
# base = efficientnet_v2.EfficientNetV2S(include_top=False, weights='imagenet', input_shape=(224,224,3))
# feat_model = Model(inputs=base.input, outputs=GlobalAveragePooling2D()(base.output))
# preprocess = efficientnet_v2.preprocess_input

# # ---------------------------
# # Load classifier (for gradcam) if available
# # ---------------------------
# CLF_PATH = os.path.join(BASE_DIR, "model", "efficientnetv2_skin_model.h5")
# clf = None
# if os.path.exists(CLF_PATH):
#     try:
#         clf = load_model(CLF_PATH, compile=False)
#         print("Classifier loaded:", CLF_PATH)
#     except Exception as e:
#         print("[WARN] Failed to load classifier for heatmaps:", e)
#         clf = None
# else:
#     print("[INFO] No classifier found at", CLF_PATH, "- heatmaps will not be generated.")

# # ---------------------------
# # Helpers
# # ---------------------------
# def normalize(v):
#     return v / (np.linalg.norm(v) + 1e-10)

# # ---------------------------
# # Process test images
# # ---------------------------
# results = []  # rows: file, final_label, pred_score, heatmap_path, best_match_label, best_match_sim

# test_paths = sorted([p for p in Path(TEST_DIR).glob("*") if p.is_file()])
# print(f"Found {len(test_paths)} test images in {TEST_DIR}")

# for p in test_paths:
#     try:
#         img = image.load_img(p, target_size=TARGET_SIZE)
#     except Exception as e:
#         print("skip", p, e)
#         continue
#     arr = image.img_to_array(img)[None]
#     arr_pre = preprocess(arr)
#     feat = feat_model.predict(arr_pre, verbose=0)[0].astype("float32")
#     feat = normalize(feat)

#     # compute cosine similarity (dot because features are normalized)
#     sims = features.dot(feat)               # in [-1, 1]
#     sims_norm = (sims + 1.0) / 2.0         # map to [0, 1]

#     topk_idx = sims_norm.argsort()[-K:][::-1]
#     topk_sims = sims_norm[topk_idx]
#     topk_labels = labels[topk_idx]

#     # voting weighted by similarity
#     votes = {}
#     for lbl, w in zip(topk_labels, topk_sims):
#         votes[lbl] = votes.get(lbl, 0.0) + float(w)
#     # pick label with highest vote
#     pred_label = max(votes.items(), key=lambda x: x[1])[0]
#     pred_score = votes[pred_label] / (topk_sims.sum() + 1e-12)

#     # Best-match similarity (highest neighbor similarity)
#     best_match_sim = float(topk_sims[0])
#     best_match_label = str(topk_labels[0])

#     # Determine final label based on best_match_sim threshold
#     if best_match_sim >= SIM_THRESHOLD:
#         final_label = str(pred_label)
#         heatmap_path = None
#         if clf is not None:
#             try:
#                 heatmap_path = os.path.join(HEATMAP_DIR, f"{p.stem}_heatmap.png")
#                 gradcam(clf, str(p), heatmap_path, None)
#             except Exception as e:
#                 print(f"[WARN] heatmap failed for {p}: {e}")
#                 heatmap_path = None
#     else:
#         final_label = "unknown"
#         heatmap_path = None

#     results.append([
#         str(p),
#         final_label,
#         float(pred_score),            # keep numeric score (vote-based) for info
#         heatmap_path,
#         best_match_label,
#         best_match_sim
#     ])

#     print(f"{p.name} -> {final_label} (pred_score={pred_score:.3f}, best_match_sim={best_match_sim:.3f}) best_src={best_match_label}")

# # ---------------------------
# # Write CSV with all results (original order)
# # ---------------------------
# with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
#     w = csv.writer(f)
#     w.writerow(["file", "prediction", "confidence", "heatmap", "best_match_label", "best_match_sim"])
#     for r in results:
#         w.writerow([
#             r[0],
#             r[1],
#             r[2],
#             r[3] if r[3] is not None else "",
#             r[4],
#             r[5]
#         ])

# print("Saved predictions ->", OUT_CSV)

# # ---------------------------
# # Summary counts
# # ---------------------------
# total = len(results)
# unknown_count = sum(1 for r in results if r[1] == "unknown")
# print(f"Summary: total={total}, unknown={unknown_count}, known={total - unknown_count}")

# # ---------------------------
# # Importable API (like original)
# # ---------------------------
# def load_model_for_server():
#     global feat_model, preprocess, clf, features, labels
#     return {
#         "feat_model": feat_model,
#         "preprocess": preprocess,
#         "clf": clf,
#         "features": features,
#         "labels": labels
#     }

# def predict_from_path_server(model_bundle, image_path):
#     from tensorflow.keras.preprocessing import image
#     import numpy as np

#     feat_model = model_bundle["feat_model"]
#     preprocess = model_bundle["preprocess"]
#     clf = model_bundle["clf"]
#     features = model_bundle["features"]
#     labels = model_bundle["labels"]

#     img = image.load_img(image_path, target_size=(224,224))
#     arr = image.img_to_array(img)[None]
#     arr_pre = preprocess(arr)

#     feat = feat_model.predict(arr_pre, verbose=0)[0].astype("float32")
#     feat = feat / (np.linalg.norm(feat) + 1e-10)

#     sims = features.dot(feat)
#     sims_norm = (sims + 1) / 2.0

#     top_idx = sims_norm.argmax()
#     best_label = labels[top_idx]
#     best_sim = float(sims_norm[top_idx])

#     return {
#         "label": best_label,
#         "similarity": best_sim
#     }

# if __name__ == "__main__":
#     pass


# """
# predict_nn.py

# Nearest-neighbour prediction script using EfficientNetV2S features and optional Grad-CAM overlays.

# Fixes & improvements included:
# - Adds missing imports (numpy).
# - Normalizes DB features on load (prevents similarity scaling issues).
# - Decodes labels if stored as bytes.
# - Avoids running from __pycache__ (run the .py source).
# - Adds DEBUG mode to print top-K sims / votes for first N images.
# - Gracefully handles missing classification model (skips Grad-CAM).
# - Provides importable API functions for server use.
# """


# import os
# import csv
# import numpy as np
# from pathlib import Path
# from tensorflow.keras.preprocessing import image
# from tensorflow.keras.layers import GlobalAveragePooling2D
# from tensorflow.keras.models import Model, load_model
# from tensorflow.keras.applications import efficientnet_v2

# # optional: import your gradcam helper (must be available)
# from utils_heatmap import gradcam

# # ---------------------------
# # Uploaded screenshot (local path; your system will convert to a URL)
# # ---------------------------
# UPLOADED_SCREENSHOT_PATH = "/mnt/data/Screenshot 2025-11-24 202513.png"

# # ---------------------------
# # Config / paths (adjust as needed)
# # ---------------------------
# BASE_DIR = r"D:\skin_datasets"
# DB_PATH = os.path.join(BASE_DIR, "code", "feature_db.npz")
# TEST_DIR = os.path.join(BASE_DIR, "test")
# HEATMAP_DIR = os.path.join(BASE_DIR, "code", "heatmaps")
# OUT_CSV = os.path.join(BASE_DIR, "code", "predictions_simthreshold.csv")

# os.makedirs(HEATMAP_DIR, exist_ok=True)
# os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)

# # Parameters
# K = 5                       # number of neighbors for voting
# SIM_THRESHOLD = 0.70        # best_match_sim threshold to keep as known
# TARGET_SIZE = (224, 224)

# # ---------------------------
# # Load DB (features, labels, src)
# # ---------------------------
# if not os.path.exists(DB_PATH):
#     raise FileNotFoundError(f"Feature DB not found: {DB_PATH}")

# db = np.load(DB_PATH, allow_pickle=True)
# features = db['features'].astype("float32")   # shape: (N, feat_dim)
# labels = db['labels']
# srcs = db['src']
# print("DB loaded:", features.shape)

# # ---------------------------
# # Prepare feature extractor
# # ---------------------------
# base = efficientnet_v2.EfficientNetV2S(include_top=False, weights='imagenet', input_shape=(224,224,3))
# feat_model = Model(inputs=base.input, outputs=GlobalAveragePooling2D()(base.output))
# preprocess = efficientnet_v2.preprocess_input

# # ---------------------------
# # Load classifier (for gradcam) if available
# # ---------------------------
# CLF_PATH = os.path.join(BASE_DIR, "model", "efficientnetv2_skin_model.h5")
# clf = None
# if os.path.exists(CLF_PATH):
#     try:
#         clf = load_model(CLF_PATH, compile=False)
#         print("Classifier loaded:", CLF_PATH)
#     except Exception as e:
#         print("[WARN] Failed to load classifier for heatmaps:", e)
#         clf = None
# else:
#     print("[INFO] No classifier found at", CLF_PATH, "- heatmaps will not be generated.")

# # ---------------------------
# # Helpers
# # ---------------------------
# def normalize(v):
#     return v / (np.linalg.norm(v) + 1e-10)

# # ---------------------------
# # Process test images
# # ---------------------------
# results = []  # rows: file, final_label, pred_score, heatmap_path, best_match_label, best_match_sim

# test_paths = sorted([p for p in Path(TEST_DIR).glob("*") if p.is_file()])
# print(f"Found {len(test_paths)} test images in {TEST_DIR}")

# for p in test_paths:
#     try:
#         img = image.load_img(p, target_size=TARGET_SIZE)
#     except Exception as e:
#         print("skip", p, e)
#         continue
#     arr = image.img_to_array(img)[None]
#     arr_pre = preprocess(arr)
#     feat = feat_model.predict(arr_pre, verbose=0)[0].astype("float32")
#     feat = normalize(feat)

#     # compute cosine similarity (dot because features are normalized)
#     sims = features.dot(feat)               # in [-1, 1]
#     sims_norm = (sims + 1.0) / 2.0         # map to [0, 1]

#     topk_idx = sims_norm.argsort()[-K:][::-1]
#     topk_sims = sims_norm[topk_idx]
#     topk_labels = labels[topk_idx]

#     # voting weighted by similarity
#     votes = {}
#     for lbl, w in zip(topk_labels, topk_sims):
#         votes[lbl] = votes.get(lbl, 0.0) + float(w)
#     # pick label with highest vote
#     pred_label = max(votes.items(), key=lambda x: x[1])[0]
#     pred_score = votes[pred_label] / (topk_sims.sum() + 1e-12)

#     # Best-match similarity (highest neighbor similarity)
#     best_match_sim = float(topk_sims[0])
#     best_match_label = str(topk_labels[0])

#     # Determine final label based on best_match_sim threshold
#     if best_match_sim >= SIM_THRESHOLD:
#         final_label = str(pred_label)
#         heatmap_path = None
#         if clf is not None:
#             try:
#                 heatmap_path = os.path.join(HEATMAP_DIR, f"{p.stem}_heatmap.png")
#                 gradcam(clf, str(p), heatmap_path, None)
#             except Exception as e:
#                 print(f"[WARN] heatmap failed for {p}: {e}")
#                 heatmap_path = None
#     else:
#         final_label = "unknown"
#         heatmap_path = None

#     results.append([
#         str(p),
#         final_label,
#         float(pred_score),            # keep numeric score (vote-based) for info
#         heatmap_path,
#         best_match_label,
#         best_match_sim
#     ])

#     print(f"{p.name} -> {final_label} (pred_score={pred_score:.3f}, best_match_sim={best_match_sim:.3f}) best_src={best_match_label}")

# # ---------------------------
# # Write CSV with all results (original order)
# # ---------------------------
# with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
#     w = csv.writer(f)
#     w.writerow(["file", "prediction", "confidence", "heatmap", "best_match_label", "best_match_sim"])
#     for r in results:
#         w.writerow([
#             r[0],
#             r[1],
#             r[2],
#             r[3] if r[3] is not None else "",
#             r[4],
#             r[5]
#         ])

# print("Saved predictions ->", OUT_CSV)

# # ---------------------------
# # Summary counts
# # ---------------------------
# total = len(results)
# unknown_count = sum(1 for r in results if r[1] == "unknown")
# print(f"Summary: total={total}, unknown={unknown_count}, known={total - unknown_count}")

# # ---------------------------
# # Importable API (like original)
# # ---------------------------
# def load_model_for_server():
#     global feat_model, preprocess, clf, features, labels
#     return {
#         "feat_model": feat_model,
#         "preprocess": preprocess,
#         "clf": clf,
#         "features": features,
#         "labels": labels
#     }

# def predict_from_path_server(model_bundle, image_path):
#     from tensorflow.keras.preprocessing import image
#     import numpy as np

#     feat_model = model_bundle["feat_model"]
#     preprocess = model_bundle["preprocess"]
#     clf = model_bundle["clf"]
#     features = model_bundle["features"]
#     labels = model_bundle["labels"]

#     img = image.load_img(image_path, target_size=(224,224))
#     arr = image.img_to_array(img)[None]
#     arr_pre = preprocess(arr)

#     feat = feat_model.predict(arr_pre, verbose=0)[0].astype("float32")
#     feat = feat / (np.linalg.norm(feat) + 1e-10)

#     sims = features.dot(feat)
#     sims_norm = (sims + 1) / 2.0

#     top_idx = sims_norm.argmax()
#     best_label = labels[top_idx]
#     best_sim = float(sims_norm[top_idx])

#     return {
#         "label": best_label,
#         "similarity": best_sim
#     }

# if __name__ == "__main__":
#     pass

# 1========================================================

# import os
# import numpy as np
# from pathlib import Path
# from tensorflow.keras.preprocessing import image
# from tensorflow.keras.layers import GlobalAveragePooling2D
# from tensorflow.keras.models import Model, load_model
# from tensorflow.keras.applications import efficientnet_v2

# from utils_heatmap import gradcam     # optional

# # ------------------------------------
# # CONFIG
# # ------------------------------------
# BASE_DIR = r"D:\skin_datasets"
# DB_PATH = os.path.join(BASE_DIR, "code", "feature_db.npz")
# TEST_DIR = os.path.join(BASE_DIR, "test")
# HEATMAP_DIR = os.path.join(BASE_DIR, "code", "heatmaps")

# os.makedirs(HEATMAP_DIR, exist_ok=True)

# K = 5
# PRED_SCORE_THRESHOLD = 0.60     # decision threshold based on vote score
# TARGET_SIZE = (224, 224)

# # ------------------------------------
# # LOAD FEATURE DB
# # ------------------------------------
# if not os.path.exists(DB_PATH):
#     raise FileNotFoundError(f"Feature DB missing: {DB_PATH}")

# db = np.load(DB_PATH, allow_pickle=True)
# features = db["features"].astype("float32")
# labels = db["labels"]

# # normalize db features (required for cosine similarity)
# features = features / (np.linalg.norm(features, axis=1, keepdims=True) + 1e-10)

# print("DB loaded:", features.shape)

# # ------------------------------------
# # LOAD FEATURE EXTRACTOR
# # ------------------------------------
# base = efficientnet_v2.EfficientNetV2S(include_top=False, weights="imagenet",
#                                        input_shape=(224,224,3))
# feat_model = Model(inputs=base.input, outputs=GlobalAveragePooling2D()(base.output))
# preprocess = efficientnet_v2.preprocess_input

# # ------------------------------------
# # OPTIONAL: Load classifier for heatmaps
# # ------------------------------------
# CLF_PATH = os.path.join(BASE_DIR, "model", "efficientnetv2_skin_model.h5")
# clf = None
# if os.path.exists(CLF_PATH):
#     try:
#         clf = load_model(CLF_PATH, compile=False)
#         print("Classifier loaded.")
#     except:
#         print("Classifier failed to load.")

# # ------------------------------------
# # PROCESS TEST IMAGES
# # ------------------------------------
# confident_predictions = []

# test_paths = sorted([p for p in Path(TEST_DIR).glob("*") if p.is_file()])
# print(f"Found {len(test_paths)} test images")

# for p in test_paths:
#     # load
#     try:
#         img = image.load_img(p, target_size=TARGET_SIZE)
#     except:
#         print("Skipping:", p)
#         continue

#     arr = image.img_to_array(img)[None]
#     arr_pre = preprocess(arr)

#     # extract feature
#     feat = feat_model.predict(arr_pre, verbose=0)[0]
#     feat = feat / (np.linalg.norm(feat) + 1e-10)

#     # cosine similarity via dot
#     sims = features.dot(feat)
#     sims_norm = (sims + 1) / 2

#     # top-K neighbors
#     topk_idx = sims_norm.argsort()[-K:][::-1]
#     topk_sims = sims_norm[topk_idx]
#     topk_labels = labels[topk_idx]

#     # weighted vote
#     votes = {}
#     for lbl, w in zip(topk_labels, topk_sims):
#         votes[lbl] = votes.get(lbl, 0.0) + float(w)

#     pred_label = max(votes.items(), key=lambda x: x[1])[0]
#     pred_score = votes[pred_label] / (topk_sims.sum() + 1e-12)

#     # decision based on predicted score
#     if pred_score >= PRED_SCORE_THRESHOLD:
#         final_label = pred_label

#         # create heatmap
#         heatmap_path = None
#         if clf is not None:
#             heatmap_path = os.path.join(HEATMAP_DIR, f"{p.stem}_heatmap.png")
#             try:
#                 gradcam(clf, str(p), heatmap_path, None)
#             except Exception as e:
#                 print("[WARN] heatmap failed:", e)
#                 heatmap_path = None

#         confident_predictions.append((p.name, final_label, pred_score))
#         print(f"{p.name} -> {final_label}  (score={pred_score:.3f}) [CONFIDENT]")

#     else:
#         print(f"{p.name} -> UNKNOWN (score={pred_score:.3f})")

# # ------------------------------------
# # FINAL DISPLAY
# # ------------------------------------
# print("\n---------------------------")
# print("CONFIDENT PREDICTIONS ONLY")
# print("---------------------------")

# if not confident_predictions:
#     print("No confident predictions found.")
# else:
#     for fn, lbl, s in sorted(confident_predictions, key=lambda x: x[2], reverse=True):
#         print(f"{fn} -> {lbl}  (score={s:.3f})")


# /======================================================

import os
import numpy as np
import requests
from pathlib import Path
from tensorflow.keras.preprocessing import image
from tensorflow.keras.layers import GlobalAveragePooling2D
from tensorflow.keras.models import Model, load_model
from tensorflow.keras.applications import efficientnet_v2

from utils_heatmap import gradcam     # optional heatmap

# ------------------------------------
# CONFIG
# ------------------------------------
BASE_DIR = r"D:\skin_datasets"
DB_PATH = os.path.join(BASE_DIR, "code", "feature_db.npz")
TEST_DIR = os.path.join(BASE_DIR, "test")
HEATMAP_DIR = os.path.join(BASE_DIR, "code", "heatmaps")

FLASK_SERVER_URL = "http://127.0.0.1:5000/predict_label"   # 🔥 send label → Flask

os.makedirs(HEATMAP_DIR, exist_ok=True)

K = 5
PRED_SCORE_THRESHOLD = 0.60
TARGET_SIZE = (224, 224)

# ------------------------------------
# LOAD FEATURE DB
# ------------------------------------
if not os.path.exists(DB_PATH):
    raise FileNotFoundError(f"Feature DB missing: {DB_PATH}")

db = np.load(DB_PATH, allow_pickle=True)
features = db["features"].astype("float32")
labels = db["labels"]

# normalize (cosine similarity requirement)
features = features / (np.linalg.norm(features, axis=1, keepdims=True) + 1e-10)

print("Feature DB loaded:", features.shape)

# ------------------------------------
# LOAD FEATURE EXTRACTOR
# ------------------------------------
base = efficientnet_v2.EfficientNetV2S(
    include_top=False, weights="imagenet", input_shape=(224,224,3)
)

feat_model = Model(
    inputs=base.input,
    outputs=GlobalAveragePooling2D()(base.output)
)

preprocess = efficientnet_v2.preprocess_input

# ------------------------------------
# OPTIONAL CLASSIFIER (heatmaps)
# ------------------------------------
CLF_PATH = os.path.join(BASE_DIR, "model", "efficientnetv2_skin_model.h5")
clf = None

if os.path.exists(CLF_PATH):
    try:
        clf = load_model(CLF_PATH, compile=False)
        print("Classifier loaded.")
    except:
        print("[WARN] Failed to load classifier.")

# ------------------------------------
# SEND TO FLASK
# ------------------------------------
def send_to_flask(label, score):
    try:
        payload = {"label": label, "confidence": float(score)}
        r = requests.post(FLASK_SERVER_URL, json=payload)

        print("\n----- Flask Response -----")
        print(r.json())
        print("--------------------------\n")

    except Exception as e:
        print("[ERROR] Could not connect to Flask server:", e)

# ------------------------------------
# PROCESS TEST IMAGES
# ------------------------------------
confident_predictions = []

test_paths = sorted([p for p in Path(TEST_DIR).glob("*") if p.is_file()])
print(f"\nFound {len(test_paths)} test images.\n")

for p in test_paths:

    # load image
    try:
        img = image.load_img(p, target_size=TARGET_SIZE)
    except Exception:
        print("Skipping invalid image:", p)
        continue

    arr = image.img_to_array(img)[None]
    arr_pre = preprocess(arr)

    # extract features
    feat = feat_model.predict(arr_pre, verbose=0)[0]
    feat = feat / (np.linalg.norm(feat) + 1e-10)

    # cosine similarities
    sims = features.dot(feat)
    sims_norm = (sims + 1) / 2

    # top-K
    topk_idx = sims_norm.argsort()[-K:][::-1]
    topk_sims = sims_norm[topk_idx]
    topk_labels = labels[topk_idx]

    # weighted vote
    votes = {}
    for lbl, w in zip(topk_labels, topk_sims):
        votes[lbl] = votes.get(lbl, 0.0) + float(w)

    pred_label = max(votes.items(), key=lambda x: x[1])[0]
    pred_score = votes[pred_label] / (topk_sims.sum() + 1e-12)

    # decision threshold
    if pred_score >= PRED_SCORE_THRESHOLD:
        print(f"{p.name} -> {pred_label}  (score={pred_score:.3f})  [CONFIDENT]")

        # optional: create heatmap
        if clf is not None:
            heatmap_path = os.path.join(HEATMAP_DIR, f"{p.stem}_heatmap.png")
            try:
                gradcam(clf, str(p), heatmap_path)
            except Exception as e:
                print("[WARN] Heatmap failed:", e)

        confident_predictions.append((p.name, pred_label, pred_score))

        # ------------------------------------
        # SEND LABEL TO FLASK SERVER
        # ------------------------------------
        send_to_flask(pred_label, pred_score)

    else:
        print(f"{p.name} -> UNKNOWN  (score={pred_score:.3f})")

# ------------------------------------
# FINAL PRINT
# ------------------------------------
print("\n-------------------------------")
print("CONFIDENT PREDICTIONS SUMMARY")
print("-------------------------------")

if not confident_predictions:
    print("No confident predictions found.")
else:
    for fn, lbl, s in confident_predictions:
        print(f"{fn} -> {lbl}  (score={s:.3f})")
