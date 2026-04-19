"""
EUDR Risk Assessment Utilities
Official EU risk assessment implementation per EUDR requirements
"""
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum


class EUDRRiskLevel(str, Enum):
    """EUDR Risk categories"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EUDRRiskTrigger(str, Enum):
    """Risk trigger codes for audit logging"""
    TREES_CLEARED = "trees_cleared_5_years"
    DEFORESTATION_DETECTED = "deforestation_detected"
    PARCEL_AFTER_2020 = "parcel_established_after_2020"
    FOREST_OVERLAP = "parcel_overlaps_forest"
    CANOPY_DROP = "canopy_cover_drop"
    NO_CONSENT = "no_satellite_consent"
    COMMUNAL_NO_REG = "communal_land_no_registration"
    VIOLATION_HISTORY = "previous_violations"
    HIGH_RISK_COUNTRY = "high_risk_country"
    HIGH_RISK_COMMODITY = "high_risk_commodity"
    NO_GEOLOCATION = "no_geolocation_data"
    INSUFFICIENT_DOCUMENTATION = "insufficient_documentation"


# Official EU EUDR Risk Assessment Matrices
# Based on EUDR Annex I (Country Risk) and Annex II (Commodity Risk)

COUNTRY_RISK_LEVELS = {
    # High Risk Countries (Annex I)
    "Brazil": "high",
    "Bolivia": "high",
    "Colombia": "high",
    "Ecuador": "high",
    "Peru": "high",
    "Venezuela": "high",
    "Guyana": "high",
    "Suriname": "high",
    "Indonesia": "high",
    "Malaysia": "high",

    # Standard Risk Countries (most others)
    "Kenya": "standard",
    "Uganda": "standard",
    "Ethiopia": "standard",
    "Tanzania": "standard",
    "Vietnam": "standard",
    "India": "standard",
    "Côte d'Ivoire": "standard",
    "Ghana": "standard",
    "Cameroon": "standard",
    "Nigeria": "standard",

    # Low Risk Countries (Annex I)
    "Norway": "low",
    "Switzerland": "low",
    "Iceland": "low",
    "United Kingdom": "low",
    "Japan": "low",
    "Canada": "low",
    "Australia": "low",
    "New Zealand": "low",
    "Chile": "low",
    "Uruguay": "low",
}

COMMODITY_RISK_LEVELS = {
    # High Risk Commodities (Annex II)
    "Palm Oil": "high",
    "Soy": "high",
    "Beef": "high",
    "Poultry Meat": "high",

    # Medium Risk Commodities
    "Cocoa": "medium",
    "Coffee": "medium",
    "Wood": "medium",
    "Rubber": "medium",

    # Low Risk Commodities
    "Tea": "low",
    "Cotton": "low",
    "Coconut": "low",
    "Sugarcane": "low",
}


def assess_eudr_risk(country: str, commodity: str, parcel: Optional[Dict] = None) -> Dict:
    """
    Assess EUDR risk level according to official EU requirements.
    Uses Annex I (country risk) and Annex II (commodity risk) matrices.

    EUDR Risk Assessment Rules:
    1. Country Risk Level (from Annex I)
    2. Commodity Risk Level (from Annex II)
    3. Combined Risk Level (higher of country/commodity)
    4. Parcel-specific risk factors
    """
    triggers: List[str] = []
    risk_score: float = 0.0

    # 1. Country Risk Assessment (Annex I)
    country_risk = COUNTRY_RISK_LEVELS.get(country, "standard")
    if country_risk == "high":
        triggers.append(EUDRRiskTrigger.HIGH_RISK_COUNTRY.value)
        risk_score += 40.0
    elif country_risk == "standard":
        risk_score += 20.0
    # Low risk countries get no additional score

    # 2. Commodity Risk Assessment (Annex II)
    commodity_risk = COMMODITY_RISK_LEVELS.get(commodity, "medium")
    if commodity_risk == "high":
        triggers.append(EUDRRiskTrigger.HIGH_RISK_COMMODITY.value)
        risk_score += 35.0
    elif commodity_risk == "medium":
        risk_score += 15.0
    # Low risk commodities get no additional score

    # 3. Parcel-specific risk factors (if parcel data provided)
    if parcel:
        get_val = lambda k, default=None: getattr(parcel, k, None) if hasattr(parcel, k) else parcel.get(k, default)

        # Geolocation requirement (MANDATORY for EUDR)
        boundary = get_val('boundary_geojson')
        centroid_lat = get_val('centroid_lat') or get_val('latitude')
        centroid_lon = get_val('centroid_lon') or get_val('longitude')

        if not boundary and not (centroid_lat and centroid_lon):
            triggers.append(EUDRRiskTrigger.NO_GEOLOCATION.value)
            risk_score += 50.0  # Critical - blocks submission

        # Trees cleared in last 5 years = HIGH RISK
        trees_cleared = get_val('trees_cleared_last_5_years', 0)
        if trees_cleared == 1:
            triggers.append(EUDRRiskTrigger.TREES_CLEARED.value)
            risk_score += 30.0

        # Farm established after Dec 31, 2020 (EUDR baseline)
        year_planted = get_val('year_coffee_first_planted')
        if year_planted and year_planted > 2020:
            triggers.append(EUDRRiskTrigger.PARCEL_AFTER_2020.value)
            risk_score += 25.0

        # No satellite monitoring consent = block submission
        consent = get_val('consent_satellite_monitoring', 0)
        if consent != 1:
            triggers.append(EUDRRiskTrigger.NO_CONSENT.value)
            risk_score += 30.0

        # Communal land with no registration = flag for docs
        ownership = get_val('ownership_type')
        reg_number = get_val('land_registration_number')
        if ownership == 'community' and not reg_number:
            triggers.append(EUDRRiskTrigger.COMMUNAL_NO_REG.value)
            risk_score += 15.0

        # Previously flagged for violations
        flagged = get_val('previously_flagged', 0)
        if flagged == 1:
            triggers.append(EUDRRiskTrigger.VIOLATION_HISTORY.value)
            risk_score += 20.0

    # Calculate final risk level based on EUDR rules
    if risk_score >= 70:
        risk_level = EUDRRiskLevel.CRITICAL
    elif risk_score >= 50:
        risk_level = EUDRRiskLevel.HIGH
    elif risk_score >= 25:
        risk_level = EUDRRiskLevel.MEDIUM
    else:
        risk_level = EUDRRiskLevel.LOW

    # Determine requirements based on risk level
    requires_satellite_review = risk_level in [EUDRRiskLevel.HIGH, EUDRRiskLevel.CRITICAL]
    block_submission = risk_level == EUDRRiskLevel.CRITICAL or EUDRRiskTrigger.NO_GEOLOCATION.value in triggers
    requires_additional_docs = risk_level in [EUDRRiskLevel.MEDIUM, EUDRRiskLevel.HIGH, EUDRRiskLevel.CRITICAL]

    return {
        "risk_level": risk_level.value,
        "risk_score": min(risk_score, 100.0),
        "country_risk": country_risk,
        "commodity_risk": commodity_risk,
        "triggers": triggers,
        "requires_satellite_review": requires_satellite_review,
        "block_submission": block_submission,
        "requires_additional_docs": requires_additional_docs,
        "monitoring_frequency": "monthly" if risk_level == EUDRRiskLevel.HIGH else "quarterly"
    }


def assess_parcel_eudr_risk(parcel: Dict) -> Dict:
    """
    Assess EUDR risk level for a land parcel.
    Legacy function - now delegates to the new official assessment.
    """
    # Extract country and commodity from parcel
    country = getattr(parcel, 'country', 'Kenya') if hasattr(parcel, 'country') else parcel.get('country', 'Kenya')
    commodity = getattr(parcel, 'commodity_type', 'Coffee') if hasattr(parcel, 'commodity_type') else parcel.get('commodity_type', 'Coffee')

    # Ensure they're strings
    country = str(country) if country else 'Kenya'
    commodity = str(commodity) if commodity else 'Coffee'

    return assess_eudr_risk(country, commodity, parcel)


def get_required_fields_for_submission(parcel: Dict) -> Dict:
    """
    Get list of required fields for EUDR submission.
    Returns missing fields that need to be filled.
    """
    required = [
        "ownership_type",
        "land_registration_number",  # if not communal
        "coffee_varieties",
        "year_coffee_first_planted",
        "practice_mixed_farming",
        "trees_planted_last_5_years",
        "trees_cleared_last_5_years",
        "consent_satellite_monitoring",
        "consent_historical_imagery",
    ]
    
    missing = []
    get_val = lambda k: getattr(parcel, k, None) if hasattr(parcel, k) else parcel.get(k)
    
    for field in required:
        value = get_val(field)
        if value is None or value == 0:
            # Special handling for fields that default to 0
            if field in ["consent_satellite_monitoring", "consent_historical_imagery"]:
                missing.append(field)
            elif value is None:
                missing.append(field)
    
    return {
        "complete": len(missing) == 0,
        "missing_fields": missing,
        "can_submit": len(missing) == 0
    }


def calculate_coffee_percentage(parcel: Dict) -> Optional[float]:
    """Calculate % of parcel under coffee from areas"""
    total = parcel.get('area_hectares') or parcel.get('total_area_hectares')
    coffee = parcel.get('coffee_area_hectares') or parcel.get('coffee_area_hectares')

    if total and coffee and total > 0:
        return round((coffee / total) * 100, 1)
    return None


def check_2020_deforestation_baseline(parcel: Dict, satellite_data: Optional[Dict] = None) -> Dict:
    """
    Check parcel against 2020 deforestation baseline (EUDR requirement).
    Returns compliance status and deforestation risk.

    EUDR Rule: All parcels must prove they were not deforested after December 31, 2020.
    """
    get_val = lambda k, default=None: getattr(parcel, k, None) if hasattr(parcel, k) else parcel.get(k, default)

    # Get establishment date
    year_planted = get_val('year_coffee_first_planted')
    if year_planted and year_planted > 2020:
        return {
            "compliant": False,
            "reason": "Parcel established after EUDR baseline (2020)",
            "deforestation_detected": True,
            "requires_mitigation": True
        }

    # Check satellite data for post-2020 deforestation
    if satellite_data:
        # Check for deforestation indicators in satellite analysis
        deforestation_detected = satellite_data.get('deforestation_detected', False)
        canopy_change = satellite_data.get('canopy_change_percentage', 0)

        if deforestation_detected or canopy_change < -20:  # >20% canopy loss
            return {
                "compliant": False,
                "reason": "Deforestation detected post-2020",
                "deforestation_detected": True,
                "canopy_change": canopy_change,
                "requires_mitigation": True
            }

    # Check self-declaration
    trees_cleared = get_val('trees_cleared_last_5_years', 0)
    if trees_cleared == 1:
        return {
            "compliant": False,
            "reason": "Trees cleared within last 5 years",
            "deforestation_detected": True,
            "requires_mitigation": True
        }

    return {
        "compliant": True,
        "reason": "No deforestation detected post-2020",
        "deforestation_detected": False,
        "requires_mitigation": False
    }


def validate_eudr_geolocation(parcel: Dict) -> Dict:
    """
    Validate geolocation data meets EUDR requirements.
    EUDR requires precise GPS coordinates for all parcels.
    """
    get_val = lambda k, default=None: getattr(parcel, k, None) if hasattr(parcel, k) else parcel.get(k, default)

    # Must have boundary or centroid coordinates
    boundary = get_val('boundary_geojson')
    centroid_lat = get_val('centroid_lat')
    centroid_lon = get_val('centroid_lon')

    if not boundary and not (centroid_lat and centroid_lon):
        return {
            "valid": False,
            "reason": "Missing geolocation data - GPS coordinates required for EUDR",
            "missing_fields": ["boundary_geojson or centroid_lat/centroid_lon"]
        }

    # Validate coordinate ranges
    if centroid_lat and centroid_lon:
        if not (-90 <= centroid_lat <= 90):
            return {"valid": False, "reason": "Invalid latitude range"}
        if not (-180 <= centroid_lon <= 180):
            return {"valid": False, "reason": "Invalid longitude range"}

    # Validate boundary format if present
    if boundary:
        if not isinstance(boundary, dict) or 'type' not in boundary:
            return {"valid": False, "reason": "Invalid GeoJSON boundary format"}

        if boundary.get('type') != 'Polygon':
            return {"valid": False, "reason": "Boundary must be a Polygon"}

    return {
        "valid": True,
        "has_boundary": bool(boundary),
        "has_centroid": bool(centroid_lat and centroid_lon)
    }


def validate_supply_chain_traceability(batch_data: Dict) -> Dict:
    """
    Validate supply chain traceability for EUDR compliance.
    Must trace from farm parcel to final product.
    """
    # Check for required traceability elements
    required_fields = [
        'farm_id', 'parcel_id', 'cooperative_id', 'batch_id',
        'processing_date', 'quality_checks', 'certifications'
    ]

    missing = []
    for field in required_fields:
        if field not in batch_data or not batch_data[field]:
            missing.append(field)

    return {
        "traceable": len(missing) == 0,
        "missing_fields": missing,
        "traceability_score": ((len(required_fields) - len(missing)) / len(required_fields)) * 100
    }