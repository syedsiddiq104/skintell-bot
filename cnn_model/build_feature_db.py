# build_feature_db.py
import os, numpy as np
from pathlib import Path

BASE_DIR = "/Users/syedsiddiq/FINAL_YEAR_PROJECT/skin_datasets"
FEATURE_DIR = os.path.join(BASE_DIR, "features_labelwise")
OUT_DB = os.path.join(BASE_DIR, "code", "feature_db.npz")
os.makedirs(os.path.dirname(OUT_DB), exist_ok=True)

feat_paths = list(Path(FEATURE_DIR).rglob("*_feat.npy"))
feat_list = []; label_list = []; src_list = []
for fp in sorted(feat_paths):
    arr = np.load(fp).astype("float32")
    if arr.ndim == 2 and arr.shape[0] == 1:
        arr = arr.reshape(-1)
    arr = arr / (np.linalg.norm(arr) + 1e-10)
    feat_list.append(arr)
    label_list.append(fp.parent.name)
    src_list.append(str(fp))
features = np.stack(feat_list, axis=0)
labels = np.array(label_list, dtype=object)
srcs = np.array(src_list, dtype=object)
print("DB built:", features.shape)
np.savez_compressed(OUT_DB, features=features, labels=labels, src=srcs)
print("Saved DB ->", OUT_DB)
