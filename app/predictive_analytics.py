"""
Predictive Analytics for Late Payments
Analyzes tenant payment history to predict late payment risk
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple

try:
    import pandas as pd
    import numpy as np
except ImportError:
    pd = None
    np = None

try:
    from sklearn.preprocessing import StandardScaler
    from sklearn.ensemble import RandomForestClassifier
except ImportError:
    StandardScaler = None
    RandomForestClassifier = None


class PaymentRiskPredictor:
    """Predictive model for late payment risk assessment"""
    
    def __init__(self):
        self.model = None
        self.scaler = None
        self.feature_names = [
            "avg_days_late",
            "late_payment_frequency",
            "payment_consistency",
            "months_active",
            "recent_payment_trend",
        ]
    
    def calculate_payment_features(self, payments: List[Dict]) -> Dict:
        """
        Calculate features from payment history.
        Returns dict of calculated features.
        """
        if not payments:
            return {
                "avg_days_late": 0,
                "late_payment_frequency": 0,
                "payment_consistency": 1.0,
                "months_active": 0,
                "recent_payment_trend": 0,
            }
        
        # Sort payments by date
        sorted_payments = sorted(payments, key=lambda x: x.get("paid_at", ""))
        
        # Calculate days late for each payment
        days_late_list = []
        for payment in sorted_payments:
            paid_at = payment.get("paid_at")
            is_late = payment.get("is_late", False)
            
            if is_late and paid_at:
                # Calculate days late (assuming 5th of month is due date)
                try:
                    paid_date = datetime.strptime(paid_at, "%Y-%m-%d %H:%M:%S")
                    due_date = paid_date.replace(day=5)
                    days_late = (paid_date - due_date).days
                    days_late_list.append(max(0, days_late))
                except:
                    days_late_list.append(15)  # Default late days
            else:
                days_late_list.append(0)
        
        # Average days late
        avg_days_late = sum(days_late_list) / len(days_late_list) if days_late_list else 0
        
        # Late payment frequency
        late_count = sum(1 for p in payments if p.get("is_late", False))
        late_frequency = late_count / len(payments) if payments else 0
        
        # Payment consistency (inverse of variance in payment dates)
        if len(payments) >= 2:
            # Calculate variance in days between payments
            payment_dates = []
            for p in sorted_payments:
                try:
                    payment_dates.append(datetime.strptime(p.get("paid_at", ""), "%Y-%m-%d %H:%M:%S"))
                except:
                    continue
            
            if len(payment_dates) >= 2:
                intervals = [(payment_dates[i] - payment_dates[i-1]).days for i in range(1, len(payment_dates))]
                if intervals:
                    avg_interval = sum(intervals) / len(intervals)
                    variance = sum((x - avg_interval) ** 2 for x in intervals) / len(intervals)
                    consistency = 1.0 / (1.0 + variance / 100)  # Normalize to 0-1
                else:
                    consistency = 1.0
            else:
                consistency = 1.0
        else:
            consistency = 1.0
        
        # Months active
        if sorted_payments:
            first_payment = sorted_payments[0].get("paid_at", "")
            try:
                first_date = datetime.strptime(first_payment, "%Y-%m-%d %H:%M:%S")
                months_active = (datetime.now() - first_date).days / 30
            except:
                months_active = len(payments)
        else:
            months_active = 0
        
        # Recent payment trend (last 3 payments)
        if len(sorted_payments) >= 3:
            recent_payments = sorted_payments[-3:]
            recent_late_count = sum(1 for p in recent_payments if p.get("is_late", False))
            recent_trend = recent_late_count / 3
        else:
            recent_trend = late_frequency
        
        return {
            "avg_days_late": avg_days_late,
            "late_payment_frequency": late_frequency,
            "payment_consistency": consistency,
            "months_active": months_active,
            "recent_payment_trend": recent_trend,
        }
    
    def predict_risk(self, features: Dict) -> Tuple[str, float]:
        """
        Predict payment risk based on features.
        Returns (risk_level, prediction_score)
        """
        # Rule-based prediction (fallback if ML not available)
        if not RandomForestClassifier:
            return self._predict_risk_rule_based(features)
        
        # ML-based prediction would go here
        # For now, use rule-based approach
        return self._predict_risk_rule_based(features)
    
    def _predict_risk_rule_based(self, features: Dict) -> Tuple[str, float]:
        """Rule-based risk prediction"""
        score = 0.0
        
        # Weight factors
        score += features["late_payment_frequency"] * 0.4  # 40% weight
        score += features["recent_payment_trend"] * 0.3  # 30% weight
        score += (features["avg_days_late"] / 30) * 0.15  # 15% weight
        score += (1 - features["payment_consistency"]) * 0.15  # 15% weight
        
        # Normalize to 0-1
        score = min(max(score, 0), 1)
        
        # Determine risk level
        if score < 0.3:
            risk_level = "low"
        elif score < 0.6:
            risk_level = "medium"
        else:
            risk_level = "high"
        
        return risk_level, score
    
    def analyze_tenant_payment_history(self, tenant_payments: List[Dict]) -> Dict:
        """
        Analyze tenant payment history and generate risk assessment.
        Returns comprehensive analysis.
        """
        features = self.calculate_payment_features(tenant_payments)
        risk_level, prediction_score = self.predict_risk(features)
        
        # Generate behavior history JSON
        behavior_history = {
            "total_payments": len(tenant_payments),
            "late_payments": sum(1 for p in tenant_payments if p.get("is_late", False)),
            "on_time_payments": sum(1 for p in tenant_payments if not p.get("is_late", False)),
            "features": features,
            "analyzed_at": datetime.now().isoformat(),
        }
        
        return {
            "risk_level": risk_level,
            "prediction_score": prediction_score,
            "features": features,
            "behavior_history": json.dumps(behavior_history),
            "recommendation": self._get_recommendation(risk_level, features),
        }
    
    def _get_recommendation(self, risk_level: str, features: Dict) -> str:
        """Get recommendation based on risk level"""
        if risk_level == "low":
            return "Tenant has good payment history. Standard monitoring sufficient."
        elif risk_level == "medium":
            return "Tenant shows some late payment patterns. Consider early reminders."
        else:
            return "High risk of late payments. Recommend proactive outreach and stricter payment terms."


def update_tenant_risk_profile(tenant_profile, payments: List[Dict]) -> Dict:
    """
    Update tenant profile with predictive analytics data.
    Returns analysis result.
    """
    predictor = PaymentRiskPredictor()
    analysis = predictor.analyze_tenant_payment_history(payments)
    
    # Update tenant profile
    if hasattr(tenant_profile, 'payment_risk_level'):
        tenant_profile.payment_risk_level = analysis["risk_level"]
    
    if hasattr(tenant_profile, 'prediction_score'):
        tenant_profile.prediction_score = analysis["prediction_score"]
    
    if hasattr(tenant_profile, 'payment_behavior_history'):
        tenant_profile.payment_behavior_history = analysis["behavior_history"]
    
    return analysis


def get_risk_level_from_score(score: float) -> str:
    """Convert prediction score to risk level"""
    if score < 0.3:
        return "low"
    elif score < 0.6:
        return "medium"
    else:
        return "high"


def calculate_payment_risk_for_all_tenants(tenant_profiles: List, payment_data: Dict) -> Dict:
    """
    Calculate payment risk for all tenants.
    Returns dict of tenant_id -> risk_analysis.
    """
    results = {}
    predictor = PaymentRiskPredictor()
    
    for tenant in tenant_profiles:
        tenant_id = tenant.id
        payments = payment_data.get(tenant_id, [])
        
        analysis = predictor.analyze_tenant_payment_history(payments)
        results[tenant_id] = analysis
    
    return results
