#!/usr/bin/env python3
"""
DME Analyzer — Claude AI scoring engine for Durable Medical Equipment contracts.

Scores DME resale opportunities for Dan Perez as a solo contractor.
Net margin model: 35-40% of contract value (after wholesale product cost + delivery).
"""

import json
import logging
import re

import anthropic

log = logging.getLogger(__name__)

# Keywords that identify each product category. Checked in priority order.
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Wheelchairs - Power": [
        "power wheelchair", "electric wheelchair", "motorized wheelchair",
        "jazzy", "quantum", "permobil", "power chair", "powerchair",
    ],
    "Wheelchairs - Manual": [
        "manual wheelchair", "transport chair", "standard wheelchair",
        "lightweight wheelchair", "folding wheelchair",
    ],
    "Mobility Scooters": [
        "mobility scooter", "go-go", "travel scooter", "power scooter",
        "electric scooter", "scooter",
    ],
    "Hospital Beds": [
        "hospital bed", "medical bed", "adjustable bed", "bariatric bed",
        "patient bed", "exam table", "electric bed", "semi-electric bed",
    ],
    "Patient Lifts": [
        "patient lift", "hoyer", "ceiling lift", "transfer lift",
        "lifting equipment", "patient transfer", "sit-to-stand", "floor lift",
    ],
    "Walkers and Mobility Aids": [
        "walker", "rollator", "walking aid", "gait trainer",
        "forearm crutch", "crutch", " cane",
    ],
    "Bathroom Safety": [
        "grab bar", "shower chair", "shower bench", "toilet safety",
        "raised toilet seat", "commode", "bath seat", "bath safety",
        "tub transfer", "bathroom safety",
    ],
}


_CONSULTING_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Process Improvement": [
        "process improvement", "process optimization", "workflow improvement",
        "lean", "six sigma", "continuous improvement", "kaizen",
        "operational excellence", "efficiency improvement", "business process",
    ],
    "Agile & Project Management": [
        "agile", "scrum", "agile transformation", "agile coaching",
        "project management", "program management", "pmo",
        "change management", "organizational change", "sprint",
    ],
    "Automation & Digital": [
        "automation", "process automation", "workflow automation",
        "low-code", "no-code", "digital transformation",
        "rpa", "robotic process automation", "system integration",
    ],
    "Training & Development": [
        "training", "coaching", "facilitation", "workshop",
        "agile training", "scrum training", "leadership development",
        "organizational development", "capability development",
    ],
    "Management Consulting": [
        "strategic planning", "management consulting", "business consulting",
        "performance improvement", "advisory", "assessment", "recommendation",
        "strategic", "consulting services",
    ],
}


class DMEAnalyzer:
    """Analyzes SAM.gov opportunities for DME suitability using Claude AI."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5-20250929"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def analyze(self, opportunities: list[dict]) -> list[dict]:
        """Score a list of SAM.gov opportunities for DME fit.

        Each returned dict includes a ``category`` field assigned by
        :meth:`_detect_category` so downstream email rendering can group
        results without a second Claude call.
        """
        if not opportunities:
            return []

        # Build a lookup so we can attach categories after Claude responds.
        lookup: dict[str, dict] = {
            opp.get("noticeId", ""): opp for opp in opportunities
        }

        prompt = self._build_analysis_prompt(opportunities)
        log.info("Sending %d opportunities to Claude for DME analysis", len(opportunities))

        message = self.client.messages.create(
            model=self.model,
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()

        results: list[dict] = json.loads(raw)

        # Tag each result with a category and surface it in highlights.
        for result in results:
            nid = result.get("noticeId", "")
            opp = lookup.get(nid, {})
            title = opp.get("title", "")
            description = opp.get("description", "")
            category = self._detect_category(title, description)
            result["category"] = category
            # Prepend a category highlight so the email shows product-line context.
            cat_note = f"Category: {category}"
            highlights = result.get("opportunity_highlights", [])
            if cat_note not in highlights:
                result["opportunity_highlights"] = [cat_note] + highlights

        log.info("Claude returned DME scores for %d opportunities", len(results))
        return results

    # ------------------------------------------------------------------
    # Category detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_category(title: str, description: str) -> str:
        """Return a product category string based on keywords in title/description.

        Title keywords take priority: if the title matches any category, only
        title matches are used. If the title has no match, the full combined
        text is checked.

        Returns "Mixed DME" only when 3 or more distinct categories are detected.
        When exactly 2 match, the highest-priority category (first in
        _CATEGORY_KEYWORDS) is returned. Returns "Other Medical Equipment" when
        nothing matches.
        """
        def _scan(text: str) -> list[str]:
            found = []
            for category, keywords in _CATEGORY_KEYWORDS.items():
                for kw in keywords:
                    if re.search(r"\b" + re.escape(kw.strip()) + r"\b", text):
                        found.append(category)
                        break
            # Power wheelchair always beats manual when both present
            if "Wheelchairs - Manual" in found and "Wheelchairs - Power" in found:
                found.remove("Wheelchairs - Manual")
            return found

        title_lower = title.lower()
        matched = _scan(title_lower)

        # If title gave no result, expand to full combined text
        if not matched:
            matched = _scan((title_lower + " " + description.lower()))

        if len(matched) >= 3:
            return "Mixed DME"
        if matched:
            return matched[0]  # Highest-priority match (dict insertion order)
        return "Other Medical Equipment"

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _build_analysis_prompt(self, opportunities: list[dict]) -> str:
        """Build the Claude analysis prompt for DME resale opportunities (solo model)."""
        slim = []
        for opp in opportunities:
            slim.append(
                {
                    "noticeId": opp.get("noticeId", ""),
                    "title": opp.get("title", ""),
                    "description": opp.get("description", ""),
                    "naicsCode": opp.get("naicsCode", ""),
                    "agency": opp.get("fullParentPathName", opp.get("departmentName", "")),
                    "postedDate": opp.get("postedDate", ""),
                    "responseDeadLine": opp.get("responseDeadLine", ""),
                    "type": opp.get("type", ""),
                    "solicitationNumber": opp.get("solicitationNumber", ""),
                    "setAside": opp.get("typeOfSetAsideDescription", ""),
                    "placeOfPerformance": opp.get("placeOfPerformance", {}),
                    "uiLink": opp.get("uiLink", ""),
                }
            )

        opportunities_json = json.dumps(slim, indent=2)

        return f"""\
You are a federal contracting analyst specializing in Durable Medical Equipment (DME).
Evaluate each opportunity for a Miami-based solo DME reseller.

=== CONTRACTOR PROFILE ===
- Product lines: manual/power wheelchairs, mobility scooters, hospital beds
  (manual/electric/bariatric), patient lifts (portable and ceiling), walkers,
  rollators, bathroom safety equipment
- Authorized dealer for: Pride Mobility, Golden Technologies, Drive Medical, Invacare
- White-glove delivery, setup, and patient training
- Service area: Florida (Miami-based); nationwide delivery available at higher freight cost
- First-time federal contractor — NO past federal contracting history

=== BASE SCORING ===
Start each opportunity at 5/10. Apply bonuses and deductions below.
The final score may exceed 10 if bonuses stack; cap reported score at 10.

=== BONUS CRITERIA ===

1. PRODUCT MATCH (+3 points)
   Award +3 if the contract clearly calls for products the contractor carries:
   - Manual or power wheelchairs
   - Mobility scooters / power-operated vehicles (POVs)
   - Hospital beds (manual, semi-electric, full-electric, bariatric)
   - Patient lifts (Hoyer-style, ceiling track, sit-to-stand)
   - Walkers, rollators, transport chairs
   - Bathroom safety equipment (grab bars, shower chairs, commodes)
   - Named brands: Pride, Golden Technologies, Drive Medical, Invacare
   Award +1 (not +3) if the description is vague but could plausibly include these products.
   Award 0 if the contract is for highly specialized medical devices, custom manufacturing,
   prosthetics, orthotics, or imaging equipment.

2. CONTRACT SIZE (+2 points)
   Evaluate the estimated contract value:
   - IDEAL ($75k–$150k): +2 — perfect size for a first federal contract
   - GOOD ($50k–$75k or $150k–$250k): +1
   - TOO SMALL (<$50k): 0
   - TOO LARGE (>$500k): 0 (risk outweighs reward for a first-time contractor)
   If no dollar value is stated, award +1 and note it in risks.

3. DELIVERY FEASIBILITY (+2 points)
   Evaluate the required delivery timeline:
   - IDEAL (30–90 days): +2
   - ACCEPTABLE (15–30 days or 90–120 days): +1
   - TOO RUSHED (<15 days): 0, flag as red flag
   - TOO LONG (>120 days): 0 (cash-flow concern)
   If no delivery timeline is stated, award +1 and note uncertainty in risks.

4. GEOGRAPHIC ADVANTAGE (+2 points)
   Evaluate the place of performance:
   - BEST (Florida): +2 — local delivery advantage, reduced freight
   - GOOD (Southeast: GA, AL, SC, NC, TN): +1
   - NEUTRAL (other US states): 0
   Note: distant deliveries add $500–$2,000 freight per pallet; flag for large orders.

5. SET-ASIDE ADVANTAGE (+1 point)
   Evaluate the contract set-aside type:
   - BEST (SDVOSB, 8(a)): +1 — less competition
   - GOOD (WOSB, HUBZone, Small Business): +1
   - NEUTRAL (Unrestricted or no set-aside): 0

6. RECURRING POTENTIAL (+1 point)
   Award +1 if the contract has strong repeat-business characteristics:
   - IDIQ, BPA, indefinite-delivery vehicles with option years
   - Annual or recurring requirements (e.g., "as needed", "fiscal year requirements")
   - Rental or maintenance components

7. PREFERRED CUSTOMERS (+1 point)
   Award +1 if the purchasing agency is:
   - VA hospital or VA medical center
   - Military base / DoD facility (MWR, health clinic)
   - Indian Health Service or Tribal health program
   - Federal Bureau of Prisons (ADA compliance upgrades)

=== PAST PERFORMANCE ASSESSMENT ===
Contractor has NO federal past performance. Assess realistically:
- Under $100k: Past performance almost never required — low risk.
- $100k–$250k: May be mentioned but often waived for small business set-asides — moderate risk.
- Over $250k: Usually requires 3 references — high risk, flag clearly.
Look for disqualifying language: "provide 3 references", "past performance evaluation factor",
"prior federal contracts required", "offerors without past performance will receive lowest rating".

=== RED FLAGS (subtract points) ===
Apply deductions for each red flag present:
- Requires FDA approval or manufacturer status: -3
- Requires on-site warehouse at delivery location: -2
- Incumbent contractor is named or implied: -2
- Complex installation beyond basic setup (electrical, plumbing, structural): -2
- Proposal due in fewer than 7 days from posting: -1
- Requires 3 or more federal contract references: -2
- Custom manufacturing or custom fabrication required: -2

=== COST ESTIMATION GUIDE ===
Use these wholesale pricing ranges when products are identifiable:

  Product                      Wholesale range
  -------                      ---------------
  Manual wheelchair            $300–$800 each
  Power wheelchair             $1,500–$3,500 each
  Mobility scooter             $800–$2,500 each
  Hospital bed (manual)        $1,000–$2,000 each
  Hospital bed (electric)      $2,000–$4,000 each
  Bariatric bed                $3,000–$5,000 each
  Patient lift (portable)      $500–$1,500 each
  Patient lift (ceiling track) $3,000–$8,000 each
  Walker / rollator            $50–$300 each
  Bathroom safety item         $20–$200 each

Delivery & setup labor: $75/hour, 2 technicians:
  - Small order  (<10 units):  1 day   = $1,200
  - Medium order (10–50 units): 2–3 days = $2,400–$3,600
  - Large order  (50+ units):  3–5 days = $3,600–$6,000

Costs include: wholesale products (60-65% of revenue) + delivery/setup (5-10% of revenue).
Net profit: use 35% of revenue as the conservative estimate (range 35-40%).

If product quantities or types are not specified, provide a conservative estimate
based on the contract value and note the assumption.

=== OUTPUT FORMAT ===
Return ONLY a valid JSON array — no markdown fences, no commentary.
Each element must be an object with exactly these fields:

{{
  "noticeId": "<string>",
  "score": <integer 1–10>,
  "score_reason": "<one sentence explaining the final score>",
  "opportunity_highlights": ["<bullet 1>", "<bullet 2>", "<bullet 3>"],
  "risks": ["<risk 1>", "<risk 2>"],
  "estimated_costs": {{
    "products_wholesale": <number>,
    "delivery_setup": <number>,
    "total": <number>
  }},
  "estimated_profit": {{
    "revenue": <number>,
    "cost": <number>,
    "gross_profit": <number>,
    "net_profit": <number>
  }},
  "products_needed": ["<product 1>", "<product 2>"],
  "requires_past_performance": <true|false>,
  "past_performance_details": "<string — what the solicitation says or implies>",
  "bid_recommendation": "<BID or NO-BID>",
  "recommendation_reason": "<one sentence>"
}}

=== OPPORTUNITIES TO EVALUATE ===
{opportunities_json}
"""

    # ------------------------------------------------------------------
    # Consulting analysis
    # ------------------------------------------------------------------

    def analyze_consulting(self, opportunities: list[dict]) -> list[dict]:
        """Score consulting opportunities for Dan's solo practice."""
        if not opportunities:
            return []

        lookup: dict[str, dict] = {
            opp.get("noticeId", ""): opp for opp in opportunities
        }

        prompt = self._build_consulting_prompt(opportunities)
        log.info("Sending %d consulting opportunities to Claude", len(opportunities))

        message = self.client.messages.create(
            model=self.model,
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()

        results: list[dict] = json.loads(raw)

        for result in results:
            nid = result.get("noticeId", "")
            opp = lookup.get(nid, {})
            category = self._detect_consulting_category(
                opp.get("title", ""), opp.get("description", "")
            )
            result["category"] = category
            result["business_model"] = "Solo Consulting"

        log.info("Claude returned consulting scores for %d opportunities", len(results))
        return results

    @staticmethod
    def _detect_consulting_category(title: str, description: str) -> str:
        """Return a consulting category based on keywords in title/description."""
        def _scan(text: str) -> list[str]:
            found = []
            for cat, keywords in _CONSULTING_CATEGORY_KEYWORDS.items():
                for kw in keywords:
                    if re.search(r"\b" + re.escape(kw.strip()) + r"\b", text):
                        found.append(cat)
                        break
            return found

        title_lower = title.lower()
        matched = _scan(title_lower)
        if not matched:
            matched = _scan(title_lower + " " + description.lower())

        if len(matched) >= 3:
            return "Management Consulting"  # Catch-all for broad scope
        if matched:
            return matched[0]
        return "Other Consulting"

    def _build_consulting_prompt(self, opportunities: list[dict]) -> str:
        """Build the Claude prompt for Dan's solo consulting practice."""
        slim = []
        for opp in opportunities:
            slim.append({
                "noticeId": opp.get("noticeId", ""),
                "title": opp.get("title", ""),
                "description": opp.get("description", ""),
                "naicsCode": opp.get("naicsCode", ""),
                "agency": opp.get("fullParentPathName", opp.get("departmentName", "")),
                "postedDate": opp.get("postedDate", ""),
                "responseDeadLine": opp.get("responseDeadLine", ""),
                "setAside": opp.get("typeOfSetAsideDescription", ""),
                "solicitationNumber": opp.get("solicitationNumber", ""),
                "uiLink": opp.get("uiLink", ""),
            })

        opportunities_json = json.dumps(slim, indent=2)

        return f"""\
You are a federal contracting analyst evaluating opportunities for Dan Perez,
an independent management consultant based in Miami, FL.

=== CONSULTANT PROFILE ===
Dan's expertise:
- Process improvement (Lean, Six Sigma, operational excellence)
- Agile transformation and Scrum coaching
- Low-code automation and digital transformation
- Training, facilitation, and workshop delivery
- Strategic planning and organizational development
Business model: solo practitioner, no staff augmentation

=== BASE SCORING ===
Start at 5/10. Apply bonuses and deductions below.

=== BONUS CRITERIA ===

1. DELIVERABLES FOCUS (+3 points)
   Award +3 when the work is clearly deliverable-based:
   - Reports, process maps, training materials, playbooks, system configuration
   - Specific outcomes: reduce cycle time, implement Agile, build automation
   Award 0 if the description reads like staff augmentation ("embedded", "on-site support").

2. CONTRACT SIZE (+2 points)
   - IDEAL ($75k-$250k): +2
   - GOOD ($50k-$75k or $250k-$400k): +1
   - TOO SMALL (<$50k) or TOO LARGE (>$500k): 0
   If no value stated: +1, flag in risks.

3. EXPERTISE MATCH (+2 points)
   Award +2 for strong keyword alignment: agile, scrum, process improvement,
   automation, workflow, digital transformation, facilitation, lean, six sigma.
   Award +1 for partial match (general consulting, training, organizational development).
   Award 0 for poor match (data science, cybersecurity, software dev).

4. TIMELINE (+2 points)
   - IDEAL (2-6 months): +2
   - ACCEPTABLE (1-2 months or 6-12 months): +1
   - TOO SHORT (<1 month) or TOO LONG (>12 months): 0
   If not stated: +1, note uncertainty.

5. REMOTE WORK (+1 point)
   Award +1 if remote or hybrid delivery is mentioned or implied.
   On-site required outside Florida: -1.

=== RED FLAGS (subtract points) ===
- Staff augmentation / body shop: -3
- Pure software development or coding: -2
- Security clearance required: -2
- Full-time on-site in distant location: -2
- Proposal due <7 days: -1
- Requires 3+ federal contract references: -2

=== COST ESTIMATION ===
Assume $175/hour effective billing rate.
Estimate hours based on contract scope and typical consulting engagements.
Overhead and expenses: 20% of revenue.
Net profit = revenue * 0.80

=== PAST PERFORMANCE ===
Dan has limited federal past performance. Assess realistically:
- Under $100k: almost never required
- $100k-$250k: may be waived for small business set-asides
- Over $250k: usually requires references

=== OUTPUT FORMAT ===
Return ONLY a valid JSON array — no markdown, no commentary.
Each element must have exactly these fields:

{{
  "noticeId": "<string>",
  "score": <integer 1-10>,
  "score_reason": "<one sentence>",
  "opportunity_highlights": ["<bullet 1>", "<bullet 2>", "<bullet 3>"],
  "risks": ["<risk 1>", "<risk 2>"],
  "estimated_costs": {{
    "labor": <number>,
    "expenses": <number>,
    "total": <number>
  }},
  "estimated_profit": {{
    "revenue": <number>,
    "cost": <number>,
    "gross_profit": <number>,
    "net_profit": <number>
  }},
  "services_needed": ["<service 1>", "<service 2>"],
  "requires_past_performance": <true|false>,
  "past_performance_details": "<string>",
  "bid_recommendation": "<BID or NO-BID>",
  "recommendation_reason": "<one sentence>"
}}

=== OPPORTUNITIES TO EVALUATE ===
{opportunities_json}
"""
