"""
Plotra ML Event Classifier
XGBoost-based deforestation event classification with calibrated probabilities.
Bootstrapped with synthetic domain-knowledge data; refines as real observations accumulate.
Falls back to rule-based classification transparently when XGBoost is unavailable.
"""
import os
import math
import random
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Label registry ────────────────────────────────────────────────────────────
CLASSES = [
    "DEFORESTATION",
    "VEGETATION_LOSS",
    "DROUGHT_STRESS",
    "CANOPY_DISTURBANCE",
    "SEASONAL_DIP",
    "REGROWTH",
    "NO_CHANGE",
]
CLASS_IDX = {c: i for i, c in enumerate(CLASSES)}
IDX_CLASS  = {i: c for i, c in enumerate(CLASSES)}

MODEL_PATH = os.environ.get("XGB_MODEL_PATH", "/tmp/plotra_xgb_classifier.json")

_model = None   # module-level singleton


# ── Feature schema ────────────────────────────────────────────────────────────
# Keep in sync with build_feature_vector() below.
FEATURE_NAMES = [
    # Current index values
    "ndvi", "evi", "savi", "ndmi", "rvi", "fusion_score",
    # Quarter-over-quarter deltas
    "ndvi_delta", "evi_delta", "savi_delta", "ndmi_delta", "rvi_delta", "fusion_delta",
    # Pixel-level spatial heterogeneity
    "ndvi_std", "ndvi_cv", "ndvi_pct_below_035",
    # Weather
    "drought_flag", "water_deficit_mm", "rainfall_mm", "temp_max_avg_c",
    # CUSUM change detection
    "cusum_score", "is_breakpoint",
    # Context
    "prev_ndvi", "prev_fusion", "cloud_cover_pct",
]


def build_feature_vector(
    prev: Dict, curr: Dict, wx: Dict,
    cusum_score: float = 0.0,
    is_breakpoint: bool = False,
) -> List[float]:
    """Build a fixed-length numeric feature vector for a quarter transition."""
    def g(d: Dict, k: str, default: float = 0.0) -> float:
        v = d.get(k)
        return float(v) if v is not None else default

    ndvi   = g(curr, "ndvi",         0.0)
    evi    = g(curr, "evi",          0.0)
    savi   = g(curr, "savi",         0.0)
    ndmi   = g(curr, "ndmi",         0.0)
    rvi    = g(curr, "rvi",          0.0)
    fusion = g(curr, "fusion_score", 0.0)

    p_ndvi   = g(prev, "ndvi",         ndvi)
    p_evi    = g(prev, "evi",          evi)
    p_savi   = g(prev, "savi",         savi)
    p_ndmi   = g(prev, "ndmi",         ndmi)
    p_rvi    = g(prev, "rvi",          rvi)
    p_fusion = g(prev, "fusion_score", fusion)

    ndvi_std  = g(curr, "ndvi_std", 0.0)
    ndvi_cv   = ndvi_std / max(abs(ndvi), 0.01)
    pct_below = g(curr, "ndvi_pct_below_035", 0.0)

    return [
        ndvi, evi, savi, ndmi, rvi, fusion,
        ndvi - p_ndvi, evi - p_evi, savi - p_savi,
        ndmi - p_ndmi, rvi - p_rvi, fusion - p_fusion,
        ndvi_std, ndvi_cv, pct_below,
        float(bool(wx.get("drought_flag"))),
        g(wx, "water_deficit_mm", 0.0),
        g(wx, "rainfall_mm",      0.0),
        g(wx, "temp_max_avg_c",  25.0),
        float(cusum_score),
        float(is_breakpoint),
        p_ndvi, p_fusion,
        g(curr, "cloud_cover_pct", 0.0),
    ]


# ── Synthetic training data ───────────────────────────────────────────────────

def _generate_training_data(n: int = 2800) -> Tuple[List[List[float]], List[int]]:
    """
    Generate synthetic labeled training data from domain knowledge exemplars.
    Gaussian noise creates decision-boundary diversity without real labeled data.
    Each class gets n//7 samples (≈400 each with n=2800).
    """
    random.seed(42)
    X: List[List[float]] = []
    y: List[int] = []

    def noisy(base: List[float], label: int, count: int, sigma: float = 0.035) -> None:
        # Feature indices 0-14 are index values/deltas (clip to [-0.5, 1.0])
        # Indices 15-23 are flags/weather/context (no clipping needed)
        for _ in range(count):
            feat = [
                max(-0.5, min(1.0, v + random.gauss(0, sigma))) if i < 15 else v
                for i, v in enumerate(base)
            ]
            X.append(feat)
            y.append(label)

    per = n // 7

    # Feature layout (24 values):
    # [ndvi, evi, savi, ndmi, rvi, fusion,
    #  Δndvi, Δevi, Δsavi, Δndmi, Δrvi, Δfusion,
    #  ndvi_std, ndvi_cv, pct_below_035,
    #  drought_flag, water_deficit, rainfall, temp,
    #  cusum_score, is_breakpoint,
    #  prev_ndvi, prev_fusion, cloud_pct]

    noisy([0.16, 0.13, 0.11, -0.06, 0.14, 0.14,
           -0.38, -0.32, -0.29, -0.22, -0.18, -0.33,
           0.09, 0.56, 0.78,
           0.0, -15.0, 130.0, 28.0,
           3.8, 1.0, 0.54, 0.47, 5.0],
          CLASS_IDX["DEFORESTATION"], per, 0.04)

    noisy([0.27, 0.21, 0.19, 0.04, 0.24, 0.24,
           -0.19, -0.16, -0.14, -0.11, -0.10, -0.17,
           0.06, 0.22, 0.46,
           0.0, -8.0, 155.0, 27.0,
           2.1, 0.0, 0.46, 0.41, 5.0],
          CLASS_IDX["VEGETATION_LOSS"], per, 0.04)

    noisy([0.44, 0.37, 0.35, -0.22, 0.41, 0.37,
           -0.09, -0.04, -0.07, -0.28, -0.14, -0.11,
           0.04, 0.09, 0.18,
           1.0, -130.0, 18.0, 35.0,
           1.6, 0.0, 0.53, 0.48, 5.0],
          CLASS_IDX["DROUGHT_STRESS"], per, 0.05)

    noisy([0.34, 0.41, 0.29, 0.09, 0.37, 0.33,
           -0.14, -0.04, -0.11, -0.07, -0.05, -0.09,
           0.07, 0.21, 0.28,
           0.0, -12.0, 135.0, 26.0,
           1.0, 0.0, 0.48, 0.42, 5.0],
          CLASS_IDX["CANOPY_DISTURBANCE"], per, 0.04)

    noisy([0.51, 0.43, 0.41, 0.16, 0.49, 0.45,
           -0.07, -0.05, -0.06, -0.04, -0.04, -0.06,
           0.03, 0.06, 0.09,
           0.0, 35.0, 205.0, 25.0,
           0.3, 0.0, 0.58, 0.51, 5.0],
          CLASS_IDX["SEASONAL_DIP"], per, 0.04)

    noisy([0.56, 0.49, 0.46, 0.21, 0.53, 0.49,
           0.21, 0.19, 0.17, 0.16, 0.15, 0.19,
           0.04, 0.07, 0.07,
           0.0, 45.0, 225.0, 24.0,
           0.4, 0.0, 0.35, 0.30, 5.0],
          CLASS_IDX["REGROWTH"], per, 0.04)

    noisy([0.61, 0.53, 0.51, 0.23, 0.59, 0.53,
           0.02, 0.01, 0.01, 0.02, 0.01, 0.01,
           0.02, 0.03, 0.04,
           0.0, 55.0, 255.0, 24.0,
           0.1, 0.0, 0.59, 0.52, 3.0],
          CLASS_IDX["NO_CHANGE"], per, 0.03)

    return X, y


# ── Model lifecycle ───────────────────────────────────────────────────────────

def load_or_train_model():
    """Return a trained XGBClassifier, loading from disk or training from scratch."""
    global _model
    if _model is not None:
        return _model

    try:
        import xgboost as xgb
    except ImportError:
        logger.warning("[XGB] xgboost not installed — rule-based fallback active")
        return None

    # Try cached model
    if os.path.exists(MODEL_PATH):
        try:
            clf = xgb.XGBClassifier()
            clf.load_model(MODEL_PATH)
            _model = clf
            logger.info(f"[XGB] Loaded model from {MODEL_PATH}")
            return _model
        except Exception as e:
            logger.warning(f"[XGB] Cached model load failed ({e}) — retraining")

    logger.info("[XGB] Training on synthetic domain data…")
    X, y = _generate_training_data(2800)

    clf = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.08,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="mlogloss",
        random_state=42,
        n_jobs=-1,
    )
    clf.fit(X, y)

    try:
        clf.save_model(MODEL_PATH)
        logger.info(f"[XGB] Model saved → {MODEL_PATH}")
    except Exception as e:
        logger.warning(f"[XGB] Could not save model: {e}")

    _model = clf
    return _model


def classify_event(
    prev: Dict, curr: Dict, wx: Dict,
    cusum_score: float = 0.0,
    is_breakpoint: bool = False,
) -> Optional[Dict]:
    """
    Classify a quarter transition.
    Returns {event_type, confidence, probabilities} or None if unavailable.
    """
    model = load_or_train_model()
    if model is None:
        return None

    try:
        import numpy as np
        feats = build_feature_vector(prev, curr, wx, cusum_score, is_breakpoint)
        proba = model.predict_proba([feats])[0]
        idx   = int(np.argmax(proba))
        return {
            "event_type":    IDX_CLASS[idx],
            "confidence":    round(float(proba[idx]), 3),
            "probabilities": {CLASSES[i]: round(float(p), 3) for i, p in enumerate(proba)},
        }
    except Exception as e:
        logger.warning(f"[XGB] Inference failed: {e}")
        return None


def retrain_with_real_observations(observations: List[Dict]) -> bool:
    """
    Retrain blending 1000 synthetic samples + confirmed real observations.
    observations: list of {features: List[float], label: str}
    """
    global _model
    try:
        import xgboost as xgb
        import numpy as np
    except ImportError:
        return False

    X_s, y_s = _generate_training_data(1000)
    X_r = [o["features"] for o in observations if o.get("label") in CLASS_IDX]
    y_r = [CLASS_IDX[o["label"]] for o in observations if o.get("label") in CLASS_IDX]

    if not X_r:
        return False

    X = np.array(X_s + X_r)
    y = np.array(y_s + y_r)

    clf = xgb.XGBClassifier(
        n_estimators=400, max_depth=6, learning_rate=0.07,
        subsample=0.8, colsample_bytree=0.8,
        eval_metric="mlogloss", random_state=42, n_jobs=-1,
    )
    clf.fit(X, y)
    clf.save_model(MODEL_PATH)
    _model = clf
    logger.info(f"[XGB] Retrained: {len(X_r)} real + {len(X_s)} synthetic samples")
    return True
