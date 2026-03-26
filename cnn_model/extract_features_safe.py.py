# extract_features_safe.py
import os, sys, traceback
import numpy as np
from pathlib import Path
from tensorflow.keras.preprocessing import image
from tensorflow.keras.layers import GlobalAveragePooling2D
from tensorflow.keras.models import Model
from tensorflow.keras.applications import efficientnet_v2

BASE_DIR = "/Users/syedsiddiq/FINAL_YEAR_PROJECT/skin_datasets"
TRAIN_DIR = os.path.join(BASE_DIR, "train")
OUT_BASE = os.path.join(BASE_DIR, "features_labelwise")
TARGET_SIZE = (224, 224)

os.makedirs(OUT_BASE, exist_ok=True)
from tensorflow.keras.applications import EfficientNetV2S
from tensorflow.keras.applications.efficientnet_v2 import preprocess_input

base = EfficientNetV2S(include_top=False, weights="imagenet", input_shape=(224,224,3))
feat_model = Model(inputs=base.input, outputs=GlobalAveragePooling2D()(base.output))

def extract_feature(img_path):
    img = image.load_img(img_path, target_size=TARGET_SIZE)
    arr = image.img_to_array(img)[None]
    arr = preprocess_input(arr)
    feat = feat_model.predict(arr, verbose=0)[0].astype("float32")
    feat = feat / (np.linalg.norm(feat) + 1e-10)
    return feat

if not os.path.isdir(TRAIN_DIR):
    print("[ERROR] TRAIN_DIR not found:", TRAIN_DIR)
    sys.exit(1)
for label in sorted(os.listdir(TRAIN_DIR)):
    label_dir = os.path.join(TRAIN_DIR, label)
    if not os.path.isdir(label_dir): continue
    print(f"[INFO] Processing label: {label}")
    out_dir = os.path.join(OUT_BASE, label)
    os.makedirs(out_dir, exist_ok=True)
    for fname in sorted(os.listdir(label_dir)):
        if not fname.lower().endswith((".jpg", ".jpeg", ".png")): continue
        img_path = os.path.join(label_dir, fname)
        out_feat = os.path.join(out_dir, Path(fname).stem + "_feat.npy")
        if os.path.exists(out_feat): continue
        try:
            feat = extract_feature(img_path)
            np.save(out_feat, feat)
        except Exception as e:
            print("[ERROR] failed:", img_path)
            traceback.print_exc()
print("[DONE] Extraction finished. Features saved to:", OUT_BASE)
