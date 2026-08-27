"""Product Matching Engine — deterministic filtering and ranking.

Hard constraints are ALWAYS enforced before ranking.
LLM is NEVER allowed to override hard constraints.
Score breakdown is transparent and explainable.
"""

from typing import Optional

from app.schemas.buyer import StructuredRequirements, ProductScore


class MatchingEngine:
    """Deterministic product filtering and ranking engine.
    
    Filtering order:
    1. Hard constraint filtering (price, RAM, storage, stock, delivery, category)
    2. Weighted ranking with transparent score breakdown
    
    Ranking weights:
    - 30% requirement match
    - 20% price value
    - 15% rating
    - 15% specifications
    - 10% delivery
    - 10% discount potential
    """

    WEIGHTS = {
        "requirement_match": 0.30,
        "price_value": 0.20,
        "rating": 0.15,
        "specifications": 0.15,
        "delivery": 0.10,
        "discount_potential": 0.10,
    }

    def filter_products(
        self,
        products: list[dict],
        requirements: StructuredRequirements,
    ) -> tuple[list[dict], dict]:
        """Apply hard constraint filtering. Returns (passing, filter_reasons)."""
        passing = []
        filter_reasons = {
            "over_budget": 0,
            "under_budget": 0,
            "insufficient_ram": 0,
            "insufficient_storage": 0,
            "out_of_stock": 0,
            "delivery_too_slow": 0,
            "category_mismatch": 0,
            "inactive": 0,
        }

        for product in products:
            specs = product.get("specifications", {}) or {}
            
            # Hard constraint: active
            if not product.get("active", True):
                filter_reasons["inactive"] += 1
                continue

            # Hard constraint: in stock
            if product.get("stock", 0) <= 0:
                filter_reasons["out_of_stock"] += 1
                continue

            # Hard constraint: category match
            if requirements.category:
                product_cat = product.get("category", "").lower()
                req_cat = requirements.category.lower()
                if req_cat not in product_cat and product_cat not in req_cat:
                    filter_reasons["category_mismatch"] += 1
                    continue

            # Hard constraint: max budget
            if requirements.budget_max is not None:
                if product.get("price", 0) > requirements.budget_max:
                    filter_reasons["over_budget"] += 1
                    continue

            # Hard constraint: min budget
            if requirements.budget_min is not None:
                if product.get("price", 0) < requirements.budget_min:
                    filter_reasons["under_budget"] += 1
                    continue

            # Hard constraint: minimum RAM
            if requirements.minimum_ram_gb is not None:
                product_ram = specs.get("ram_gb", 0)
                if product_ram < requirements.minimum_ram_gb:
                    filter_reasons["insufficient_ram"] += 1
                    continue

            # Hard constraint: minimum storage
            if requirements.minimum_storage_gb is not None:
                product_storage = specs.get("storage_gb", 0)
                if product_storage < requirements.minimum_storage_gb:
                    filter_reasons["insufficient_storage"] += 1
                    continue

            # Hard constraint: maximum delivery days
            if requirements.maximum_delivery_days is not None:
                if product.get("delivery_days", 99) > requirements.maximum_delivery_days:
                    filter_reasons["delivery_too_slow"] += 1
                    continue

            passing.append(product)

        # Remove zero-count reasons
        filter_reasons = {k: v for k, v in filter_reasons.items() if v > 0}

        return passing, filter_reasons

    def rank_products(
        self,
        products: list[dict],
        requirements: StructuredRequirements,
        merchant_policies: dict[str, dict] = None,
    ) -> list[ProductScore]:
        """Rank products with transparent weighted scoring."""
        if not products:
            return []

        scored = []
        
        # Get ranges for normalization
        prices = [p["price"] for p in products]
        max_price = max(prices) if prices else 1
        min_price = min(prices) if prices else 0
        price_range = max_price - min_price if max_price != min_price else 1

        for product in products:
            specs = product.get("specifications", {}) or {}
            policies = (merchant_policies or {}).get(product.get("merchant_id", ""), {})
            
            # 1. Requirement match (30%) — how well specs exceed minimums
            req_score = self._calc_requirement_match(product, specs, requirements)
            
            # 2. Price value (20%) — lower price = higher score
            price_score = self._calc_price_value(product["price"], min_price, price_range, requirements)
            
            # 3. Rating (15%) — normalized 0-100
            rating_score = min((product.get("rating", 0) / 5.0) * 100, 100)
            
            # 4. Specifications (15%) — extra spec quality
            spec_score = self._calc_spec_quality(specs, requirements)
            
            # 5. Delivery (10%) — faster = higher
            delivery_score = self._calc_delivery_score(product.get("delivery_days", 7), requirements)
            
            # 6. Discount potential (10%)
            discount_score = self._calc_discount_potential(policies)

            # Weighted total
            total = (
                req_score * self.WEIGHTS["requirement_match"]
                + price_score * self.WEIGHTS["price_value"]
                + rating_score * self.WEIGHTS["rating"]
                + spec_score * self.WEIGHTS["specifications"]
                + delivery_score * self.WEIGHTS["delivery"]
                + discount_score * self.WEIGHTS["discount_potential"]
            )

            # Generate recommendation reasons
            reasons = self._generate_reasons(
                product, specs, requirements, req_score, price_score, 
                rating_score, delivery_score, discount_score
            )

            scored.append(ProductScore(
                product_id=product["id"],
                merchant_id=product.get("merchant_id", ""),
                merchant_name=product.get("merchant_name", "Unknown"),
                product_name=product["name"],
                description=product.get("description", ""),
                price=product["price"],
                currency=product.get("currency", "INR"),
                rating=product.get("rating", 0),
                delivery_days=product.get("delivery_days", 7),
                stock=product.get("stock", 0),
                specifications=specs,
                total_score=round(total, 2),
                requirement_match_score=round(req_score, 2),
                price_value_score=round(price_score, 2),
                rating_score=round(rating_score, 2),
                specification_score=round(spec_score, 2),
                delivery_score=round(delivery_score, 2),
                discount_potential_score=round(discount_score, 2),
                meets_all_requirements=True,  # Already filtered
                recommendation_reasons=reasons,
            ))

        # Sort by total score descending
        scored.sort(key=lambda x: x.total_score, reverse=True)
        return scored

    def _calc_requirement_match(
        self, product: dict, specs: dict, req: StructuredRequirements
    ) -> float:
        """Calculate how well a product matches requirements."""
        score = 70.0  # Base: passes all hard constraints

        # Bonus for exceeding minimums
        if req.minimum_ram_gb and specs.get("ram_gb", 0) > req.minimum_ram_gb:
            excess = (specs["ram_gb"] - req.minimum_ram_gb) / req.minimum_ram_gb
            score += min(excess * 15, 15)

        if req.minimum_storage_gb and specs.get("storage_gb", 0) > req.minimum_storage_gb:
            excess = (specs["storage_gb"] - req.minimum_storage_gb) / req.minimum_storage_gb
            score += min(excess * 10, 10)

        # Bonus for purpose match (e.g., GPU for AI/ML)
        if req.purpose and "ai" in req.purpose.lower() or req.purpose and "ml" in req.purpose.lower():
            gpu = specs.get("gpu", "").lower()
            if "rtx" in gpu or "nvidia" in gpu:
                score += 5

        return min(score, 100)

    def _calc_price_value(
        self, price: float, min_price: float, price_range: float, req: StructuredRequirements
    ) -> float:
        """Lower price relative to range = higher score."""
        if price_range == 0:
            return 70.0
        
        # Normalize: cheapest gets 100, most expensive gets 40
        normalized = 1 - ((price - min_price) / price_range)
        score = 40 + (normalized * 60)
        
        # Bonus if significantly under budget
        if req.budget_max:
            savings_pct = (req.budget_max - price) / req.budget_max
            if savings_pct > 0.1:
                score = min(score + savings_pct * 20, 100)
        
        return score

    def _calc_spec_quality(self, specs: dict, req: StructuredRequirements) -> float:
        """Rate overall specification quality."""
        score = 50.0
        
        # RAM quality
        ram = specs.get("ram_gb", 0)
        if ram >= 32:
            score += 20
        elif ram >= 16:
            score += 10
        
        # Storage type
        storage_type = specs.get("storage_type", "").lower()
        if "nvme" in storage_type:
            score += 10
        elif "ssd" in storage_type:
            score += 5
        
        # GPU presence
        gpu = specs.get("gpu", "").lower()
        if "rtx" in gpu:
            score += 15
        elif "nvidia" in gpu or "radeon" in gpu:
            score += 8
        
        # Battery
        battery = specs.get("battery_hours", 0)
        if battery >= 10:
            score += 5
        
        return min(score, 100)

    def _calc_delivery_score(self, delivery_days: int, req: StructuredRequirements) -> float:
        """Faster delivery = higher score."""
        if delivery_days <= 1:
            return 100
        elif delivery_days <= 2:
            return 85
        elif delivery_days <= 3:
            return 70
        elif delivery_days <= 5:
            return 50
        else:
            return 30

    def _calc_discount_potential(self, policy: dict) -> float:
        """Rate merchant's discount potential."""
        if not policy:
            return 50.0
        
        max_discount = policy.get("max_discount_percent", 0)
        auto_discount = policy.get("auto_discount_percent", 0)
        negotiation = policy.get("negotiation_enabled", False)
        
        score = auto_discount * 5  # Each % of auto discount = 5 points
        if negotiation:
            score += 20
        score += max_discount * 2  # Each % of max = 2 points
        
        return min(score, 100)

    def _generate_reasons(
        self, product: dict, specs: dict, req: StructuredRequirements,
        req_score: float, price_score: float, rating_score: float,
        delivery_score: float, discount_score: float,
    ) -> list[str]:
        """Generate human-readable recommendation reasons."""
        reasons = []
        
        if req_score >= 80:
            reasons.append("Exceeds all mandatory requirements")
        else:
            reasons.append("Meets all mandatory requirements")
        
        if price_score >= 80:
            reasons.append(f"Excellent price value at ₹{product['price']:,.0f}")
        elif price_score >= 60:
            reasons.append(f"Good price value at ₹{product['price']:,.0f}")
        
        if req.budget_max and product['price'] < req.budget_max * 0.9:
            savings = req.budget_max - product['price']
            reasons.append(f"₹{savings:,.0f} under budget")
        
        if product.get("rating", 0) >= 4.5:
            reasons.append(f"Highly rated ({product['rating']}★)")
        
        if product.get("delivery_days", 99) <= 2:
            reasons.append(f"{product['delivery_days']}-day delivery")
        
        gpu = specs.get("gpu", "")
        if "RTX" in gpu or "NVIDIA" in gpu:
            reasons.append(f"Dedicated GPU: {gpu}")
        
        ram = specs.get("ram_gb", 0)
        if ram >= 32:
            reasons.append(f"{ram}GB RAM — ideal for heavy workloads")
        
        if discount_score >= 60:
            reasons.append("Good discount potential from merchant")
        
        return reasons[:6]  # Cap at 6 reasons
