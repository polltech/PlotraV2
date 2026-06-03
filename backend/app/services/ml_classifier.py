"""
Plotra ML Event Classifier
XGBoost-based deforestation event classification with calibrated probabilities.
Features: NDVI, EVI, SAVI, NDMI, RVI, BSI, NBR + fusion score + weather + CUSUM.
Bootstrapped with synthetic domain-knowledge data; refines as confirmed real
observations accumulate via the admin labelling API.
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
# 32 features total — keep in sync with build_feature_vector() below.
FEATURE_NAMES = [
    # Current index values (7)
    "ndvi", "evi", "savi", "ndmi", "rvi", "bsi", "nbr",
    # Weighted fusion score
    "fusion_score",
    # Quarter-over-quarter deltas (7)
    "ndvi_delta", "evi_delta", "savi_delta", "ndmi_delta",
    "rvi_delta", "bsi_delta", "nbr_delta",
    # Fusion delta
    "fusion_delta",
    # Pixel-level spatial heterogeneity (3)
    "ndvi_std", "ndvi_cv", "ndvi_pct_below_035",
    # Weather (4)
    "drought_flag", "water_deficit_mm", "rainfall_mm", "temp_max_avg_c",
    # CUSUM change detection (2)
    "cusum_score", "is_breakpoint",
    # Context (3)
    "prev_ndvi", "prev_fusion", "cloud_cover_pct",
    # BSI/NBR interaction features (3)
    "bsi_nbr_ratio",    # BSI / max(NBR, 0.01) — high when land is bare AND forest damaged
    "bsi_ndvi_ratio",   # BSI / max(NDVI, 0.01) — high when bare soil dominates green signal
    "nbr_drop_flag",    # 1 if NBR < 0.35 (severe forest disturbance zone)
]


def build_feature_vector(
    prev: Dict, curr: Dict, wx: Dict,
    cusum_score: float = 0.0,
    is_breakpoint: bool = False,
) -> List[float]:
    """Build a fixed-length 32-feature numeric vector for a quarter transition."""
    def g(d: Dict, k: str, default: float = 0.0) -> float:
        v = d.get(k)
        return float(v) if v is not None else default

    ndvi   = g(curr, "ndvi",         0.0)
    evi    = g(curr, "evi",          0.0)
    savi   = g(curr, "savi",         0.0)
    ndmi   = g(curr, "ndmi",         0.0)
    rvi    = g(curr, "rvi",          0.0)
    bsi    = g(curr, "bsi",          0.0)
    nbr    = g(curr, "nbr",          0.0)
    fusion = g(curr, "fusion_score", 0.0)

    p_ndvi   = g(prev, "ndvi",         ndvi)
    p_evi    = g(prev, "evi",          evi)
    p_savi   = g(prev, "savi",         savi)
    p_ndmi   = g(prev, "ndmi",         ndmi)
    p_rvi    = g(prev, "rvi",          rvi)
    p_bsi    = g(prev, "bsi",          bsi)
    p_nbr    = g(prev, "nbr",          nbr)
    p_fusion = g(prev, "fusion_score", fusion)

    ndvi_std  = g(curr, "ndvi_std", 0.0)
    ndvi_cv   = ndvi_std / max(abs(ndvi), 0.01)
    pct_below = g(curr, "ndvi_pct_below_035", 0.0)

    # Interaction features — capture cross-index patterns
    bsi_nbr_ratio  = bsi / max(abs(nbr), 0.01)
    bsi_ndvi_ratio = bsi / max(abs(ndvi), 0.01)
    nbr_drop_flag  = 1.0 if nbr < 0.35 else 0.0

    return [
        # Current values
        ndvi, evi, savi, ndmi, rvi, bsi, nbr, fusion,
        # Deltas
        ndvi - p_ndvi, evi - p_evi, savi - p_savi,
        ndmi - p_ndmi, rvi - p_rvi, bsi - p_bsi, nbr - p_nbr,
        fusion - p_fusion,
        # Spatial
        ndvi_std, ndvi_cv, pct_below,
        # Weather
        float(bool(wx.get("drought_flag"))),
        g(wx, "water_deficit_mm", 0.0),
        g(wx, "rainfall_mm",      0.0),
        g(wx, "temp_max_avg_c",  25.0),
        # CUSUM
        float(cusum_score),
        float(is_breakpoint),
        # Context
        p_ndvi, p_fusion,
        g(curr, "cloud_cover_pct", 0.0),
        # Interactions
        bsi_nbr_ratio, bsi_ndvi_ratio, nbr_drop_flag,
    ]


# ── Synthetic training data ───────────────────────────────────────────────────

def _generate_training_data(n: int = 4200) -> Tuple[List[List[float]], List[int]]:
    """
    Generate synthetic labelled training data from domain-knowledge exemplars.
    Gaussian noise creates decision-boundary diversity without real labelled data.
    Each class gets n//7 samples (600 each with n=4200).

    Feature layout (32 values):
    [ndvi, evi, savi, ndmi, rvi, bsi, nbr, fusion,
     Δndvi, Δevi, Δsavi, Δndmi, Δrvi, Δbsi, Δnbr, Δfusion,
     ndvi_std, ndvi_cv, pct_below_035,
     drought_flag, water_deficit, rainfall, temp,
     cusum_score, is_breakpoint,
     prev_ndvi, prev_fusion, cloud_pct,
     bsi_nbr_ratio, bsi_ndvi_ratio, nbr_drop_flag]
    """
    random.seed(42)
    X: List[List[float]] = []
    y: List[int] = []

    def noisy(base: List[float], label: int, count: int, sigma: float = 0.035) -> None:
        for _ in range(count):
            feat = [
                max(-0.6, min(1.2, v + random.gauss(0, sigma))) if i < 16 else v
                for i, v in enumerate(base)
            ]
            X.append(feat)
            y.append(label)

    per = n // 7

    # ── DEFORESTATION ─────────────────────────────────────────────────────────
    # All vegetation collapses. BSI spikes (bare soil exposed). NBR crashes.
    # Pattern: massive multi-index drop + BSI spike + NBR crash + no recovery.
    noisy([
        0.16, 0.13, 0.11, -0.06, 0.14, 0.26, 0.12, 0.14,   # current values (ndvi...fusion)
        -0.38, -0.32, -0.29, -0.22, -0.18, +0.22, -0.38, -0.33,  # deltas
        0.09, 0.56, 0.78,                                    # spatial
        0.0, -15.0, 130.0, 28.0,                            # weather
        3.8, 1.0,                                           # cusum
        0.54, 0.47, 5.0,                                    # context
        2.17, 1.63, 1.0,                                    # interactions (bsi/nbr, bsi/ndvi, nbr_drop)
    ], CLASS_IDX["DEFORESTATION"], per, 0.04)

    # ── VEGETATION_LOSS ───────────────────────────────────────────────────────
    # Moderate decline persisting. BSI rises moderately. NBR drops partially.
    noisy([
        0.27, 0.21, 0.19, 0.04, 0.24, 0.12, 0.31, 0.24,
        -0.19, -0.16, -0.14, -0.11, -0.10, +0.10, -0.19, -0.17,
        0.06, 0.22, 0.46,
        0.0, -8.0, 155.0, 27.0,
        2.1, 0.0,
        0.46, 0.41, 5.0,
        0.39, 0.44, 1.0,
    ], CLASS_IDX["VEGETATION_LOSS"], per, 0.04)

    # ── DROUGHT_STRESS ────────────────────────────────────────────────────────
    # NDMI drops sharply (water loss). BSI low (soil not exposed — just dry plants).
    # NBR stays moderate (canopy structure intact despite dryness).
    noisy([
        0.44, 0.37, 0.35, -0.22, 0.41, 0.03, 0.48, 0.37,
        -0.09, -0.04, -0.07, -0.28, -0.14, +0.02, -0.08, -0.11,
        0.04, 0.09, 0.18,
        1.0, -130.0, 18.0, 35.0,
        1.6, 0.0,
        0.53, 0.48, 5.0,
        0.06, 0.07, 0.0,
    ], CLASS_IDX["DROUGHT_STRESS"], per, 0.05)

    # ── CANOPY_DISTURBANCE ────────────────────────────────────────────────────
    # NDVI dips (ground cover affected) but EVI stable (canopy intact).
    # BSI near zero (no soil exposure). NBR moderate-high (forest structure ok).
    noisy([
        0.34, 0.41, 0.29, 0.09, 0.37, 0.02, 0.52, 0.33,
        -0.14, -0.04, -0.11, -0.07, -0.05, +0.01, -0.06, -0.09,
        0.07, 0.21, 0.28,
        0.0, -12.0, 135.0, 26.0,
        1.0, 0.0,
        0.48, 0.42, 5.0,
        0.04, 0.06, 0.0,
    ], CLASS_IDX["CANOPY_DISTURBANCE"], per, 0.04)

    # ── SEASONAL_DIP ──────────────────────────────────────────────────────────
    # Moderate NDVI drop but recovers. BSI very low. NBR healthy. Normal crop cycle.
    noisy([
        0.51, 0.43, 0.41, 0.16, 0.49, -0.02, 0.61, 0.45,
        -0.07, -0.05, -0.06, -0.04, -0.04, -0.01, -0.03, -0.06,
        0.03, 0.06, 0.09,
        0.0, 35.0, 205.0, 25.0,
        0.3, 0.0,
        0.58, 0.51, 5.0,
        -0.03, -0.04, 0.0,
    ], CLASS_IDX["SEASONAL_DIP"], per, 0.04)

    # ── REGROWTH ──────────────────────────────────────────────────────────────
    # Rising indices. BSI declining (soil being covered). NBR recovering upward.
    noisy([
        0.56, 0.49, 0.46, 0.21, 0.53, -0.04, 0.66, 0.49,
        +0.21, +0.19, +0.17, +0.16, +0.15, -0.08, +0.18, +0.19,
        0.04, 0.07, 0.07,
        0.0, 45.0, 225.0, 24.0,
        0.4, 0.0,
        0.35, 0.30, 5.0,
        -0.06, -0.07, 0.0,
    ], CLASS_IDX["REGROWTH"], per, 0.04)

    # ── NO_CHANGE ─────────────────────────────────────────────────────────────
    # All indices stable. BSI very low. NBR high (healthy forest/farmland).
    noisy([
        0.61, 0.53, 0.51, 0.23, 0.59, -0.03, 0.72, 0.53,
        +0.02, +0.01, +0.01, +0.02, +0.01, +0.00, +0.01, +0.01,
        0.02, 0.03, 0.04,
        0.0, 55.0, 255.0, 24.0,
        0.1, 0.0,
        0.59, 0.52, 3.0,
        -0.04, -0.05, 0.0,
    ], CLASS_IDX["NO_CHANGE"], per, 0.03)

    return X, y


# ── Model lifecycle ───────────────────────────────────────────────────────────

def load_or_train_model(force_retrain: bool = False):
    """Return a trained XGBClassifier, loading from disk or training from scratch."""
    global _model
    if _model is not None and not force_retrain:
        return _model

    try:
        import xgboost as xgb  # pyright: ignore[reportMissingImports]
    except ImportError:
        logger.warning("[XGB] xgboost not installed — rule-based fallback active")
        return None

    # Try cached model (unless forced retrain)
    if not force_retrain and os.path.exists(MODEL_PATH):
        try:
            clf = xgb.XGBClassifier()
            clf.load_model(MODEL_PATH)
            _model = clf
            logger.info(f"[XGB] Loaded model from {MODEL_PATH} ({len(FEATURE_NAMES)} features)")
            return _model
        except Exception as e:
            logger.warning(f"[XGB] Cached model load failed ({e}) — retraining")

    logger.info(f"[XGB] Training on synthetic data — {len(FEATURE_NAMES)} features, 4200 samples…")
    X, y = _generate_training_data(4200)

    clf = xgb.XGBClassifier(
        n_estimators=400,
        max_depth=6,
        learning_rate=0.07,
        subsample=0.85,
        colsample_bytree=0.85,
        min_child_weight=3,
        gamma=0.1,
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


def delete_cached_model():
    """Remove the saved model file so next load forces a retrain."""
    global _model
    _model = None
    if os.path.exists(MODEL_PATH):
        os.remove(MODEL_PATH)
        logger.info(f"[XGB] Cached model deleted: {MODEL_PATH}")


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


def retrain_with_real_observations(observations: List[Dict]) -> Dict:
    """
    Retrain blending 1400 synthetic samples + confirmed real observations.
    observations: list of {features: List[float], label: str}
    Returns {success, real_samples, synthetic_samples, total_samples}
    """
    global _model
    try:
        import xgboost as xgb  # pyright: ignore[reportMissingImports]
        import numpy as np
    except ImportError:
        return {"success": False, "error": "xgboost not installed"}

    X_s, y_s = _generate_training_data(1400)
    X_r = [o["features"] for o in observations if o.get("label") in CLASS_IDX]
    y_r = [CLASS_IDX[o["label"]] for o in observations if o.get("label") in CLASS_IDX]

    if not X_r:
        # No real data — retrain on pure synthetic (refreshes model with new BSI/NBR features)
        X = np.array(X_s)
        y = np.array(y_s)
        real_count = 0
    else:
        X = np.array(X_s + X_r)
        y = np.array(y_s + y_r)
        real_count = len(X_r)

    clf = xgb.XGBClassifier(
        n_estimators=400, max_depth=6, learning_rate=0.07,
        subsample=0.85, colsample_bytree=0.85,
        min_child_weight=3, gamma=0.1,
        eval_metric="mlogloss", random_state=42, n_jobs=-1,
    )
    clf.fit(X, y)

    try:
        clf.save_model(MODEL_PATH)
    except Exception as e:
        logger.warning(f"[XGB] Could not save retrained model: {e}")

    _model = clf
    logger.info(f"[XGB] Retrained: {real_count} real + {len(X_s)} synthetic = {len(X)} total samples")
    return {
        "success":          True,
        "real_samples":     real_count,
        "synthetic_samples": len(X_s),
        "total_samples":    len(X),
        "features":         len(FEATURE_NAMES),
        "classes":          CLASSES,
    }


def get_feature_importance() -> Optional[Dict]:
    """Return feature importances from the trained model, sorted descending."""
    model = load_or_train_model()
    if model is None:
        return None
    try:
        import numpy as np
        scores = model.feature_importances_
        ranked = sorted(zip(FEATURE_NAMES, scores), key=lambda x: x[1], reverse=True)
        return {name: round(float(score), 4) for name, score in ranked}
    except Exception as e:
        logger.warning(f"[XGB] Feature importance failed: {e}")
        return None
