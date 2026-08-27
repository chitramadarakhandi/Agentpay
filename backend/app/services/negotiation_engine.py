"""Negotiation Engine — bounded AI negotiation with policy enforcement & collusion detection.

All discount proposals are validated against merchant policy.
The engine BLOCKS any proposal exceeding merchant limits and stops automated boundary-probing attacks.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from app.policies.collusion_detector import collusion_detector


@dataclass
class NegotiationResult:
    """Result of a negotiation attempt."""
    approved: bool
    original_price: float
    requested_discount_percent: float
    approved_discount_percent: float
    discount_amount: float
    final_price: float
    merchant_message: str
    policy_validation: dict
    negotiation_steps: list[dict]
    collusion_detected: bool = False
    anomaly_reason: Optional[str] = None


class NegotiationEngine:
    """Deterministic negotiation engine with policy boundaries and multi-agent anomaly detection.
    
    Flow:
    1. Check for multi-agent collusion / automated boundary probing
    2. Check if negotiation is enabled
    3. Validate discount against merchant policy
    4. If within limits: approve
    5. If exceeds limits: BLOCK and counter-offer max allowed
    6. All steps logged
    """

    def negotiate(
        self,
        original_price: float,
        requested_discount_percent: Optional[float],
        merchant_policy: dict,
        merchant_name: str,
        session_id: str = "default_session",
        quote_id: str = "default_quote",
    ) -> NegotiationResult:
        """Process a negotiation request."""
        max_discount = merchant_policy.get("max_discount_percent", 0)
        auto_discount = merchant_policy.get("auto_discount_percent", 0)
        negotiation_enabled = merchant_policy.get("negotiation_enabled", False)
        
        steps = []
        
        # Step 1: Check for Multi-Agent Boundary Probing / Collusion Attack
        req_disc = requested_discount_percent if requested_discount_percent is not None else (auto_discount + 2.0)
        is_suspicious, anomaly_reason = collusion_detector.evaluate_negotiation_attempt(
            session_id=session_id,
            quote_id=quote_id,
            requested_discount=req_disc,
        )

        if is_suspicious:
            steps.append({
                "step": "security_anomaly_check",
                "actor": "Collusion Detection Guard",
                "message": f"🚨 {anomaly_reason}",
                "status": "security_violation",
            })
            return NegotiationResult(
                approved=False,
                original_price=original_price,
                requested_discount_percent=req_disc,
                approved_discount_percent=0.0,
                discount_amount=0.0,
                final_price=original_price,
                merchant_message=f"Negotiation locked: {anomaly_reason}",
                policy_validation={
                    "blocked": True,
                    "collusion_detected": True,
                    "security_alert": anomaly_reason,
                },
                negotiation_steps=steps,
                collusion_detected=True,
                anomaly_reason=anomaly_reason,
            )

        # Step 2: Check if negotiation is enabled
        if not negotiation_enabled:
            steps.append({
                "step": "negotiation_check",
                "actor": f"{merchant_name} Agent",
                "message": "Negotiation is not available for this merchant.",
                "status": "blocked",
            })
            # Still offer auto discount if available
            discount_pct = auto_discount
            discount_amt = round(original_price * discount_pct / 100, 2)
            final = round(original_price - discount_amt, 2)
            
            return NegotiationResult(
                approved=auto_discount > 0,
                original_price=original_price,
                requested_discount_percent=requested_discount_percent or 0,
                approved_discount_percent=auto_discount,
                discount_amount=discount_amt,
                final_price=final,
                merchant_message=f"Negotiation not available. {'Auto discount of ' + str(auto_discount) + '% applied.' if auto_discount > 0 else 'No discount available.'}",
                policy_validation={"negotiation_enabled": False, "auto_discount_applied": auto_discount > 0},
                negotiation_steps=steps,
            )

        # Step 3: Determine discount to request
        if requested_discount_percent is None:
            # AI proposes a reasonable discount
            requested_discount_percent = min(auto_discount + 2.0, max_discount)
        
        steps.append({
            "step": "buyer_request",
            "actor": "Buyer Agent",
            "message": f"Can you offer a better price? Requesting {requested_discount_percent}% discount.",
            "status": "proposed",
        })

        # Step 4: Validate against policy
        if requested_discount_percent > max_discount:
            # BLOCKED — exceeds merchant policy
            steps.append({
                "step": "policy_check",
                "actor": "Trust Engine",
                "message": f"❌ Requested {requested_discount_percent}% exceeds merchant maximum {max_discount}%",
                "status": "blocked",
            })
            
            # Counter-offer with max allowed
            counter_pct = max_discount
            counter_amt = round(original_price * counter_pct / 100, 2)
            counter_final = round(original_price - counter_amt, 2)
            
            steps.append({
                "step": "counter_offer",
                "actor": f"{merchant_name} Agent",
                "message": f"Maximum discount available is {max_discount}%. Counter-offer: ₹{counter_final:,.0f}",
                "status": "counter",
            })

            steps.append({
                "step": "policy_validation",
                "actor": "Trust Engine",
                "message": f"✓ Counter-offer {max_discount}% is within merchant policy",
                "status": "passed",
            })
            
            return NegotiationResult(
                approved=True,  # Counter-offer is approved
                original_price=original_price,
                requested_discount_percent=requested_discount_percent,
                approved_discount_percent=counter_pct,
                discount_amount=counter_amt,
                final_price=counter_final,
                merchant_message=f"Requested discount exceeds policy. Best offer: {counter_pct}% discount (₹{counter_amt:,.0f} off)",
                policy_validation={
                    "requested": requested_discount_percent,
                    "max_allowed": max_discount,
                    "blocked": True,
                    "counter_offered": True,
                },
                negotiation_steps=steps,
            )
        
        # Step 5: Approved — within policy
        steps.append({
            "step": "policy_check",
            "actor": "Trust Engine",
            "message": f"✓ Discount {requested_discount_percent}% is within merchant policy ({max_discount}% max)",
            "status": "passed",
        })

        discount_amt = round(original_price * requested_discount_percent / 100, 2)
        final_price = round(original_price - discount_amt, 2)

        steps.append({
            "step": "merchant_approval",
            "actor": f"{merchant_name} Agent",
            "message": f"{requested_discount_percent}% discount approved. Final price: ₹{final_price:,.0f}",
            "status": "approved",
        })

        steps.append({
            "step": "buyer_acceptance",
            "actor": "Buyer Agent",
            "message": "Offer accepted.",
            "status": "accepted",
        })

        return NegotiationResult(
            approved=True,
            original_price=original_price,
            requested_discount_percent=requested_discount_percent,
            approved_discount_percent=requested_discount_percent,
            discount_amount=discount_amt,
            final_price=final_price,
            merchant_message=f"Discount of {requested_discount_percent}% approved! You save ₹{discount_amt:,.0f}",
            policy_validation={
                "requested": requested_discount_percent,
                "max_allowed": max_discount,
                "blocked": False,
            },
            negotiation_steps=steps,
        )
