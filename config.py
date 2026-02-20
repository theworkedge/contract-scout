"""
config.py — Central configuration for Contract Scout.

Supports two solo business models in a single daily run:

  DME Resale    — equipment resale, 35-40% net margin
  Consulting    — Dan's process improvement / Agile / automation work, 80% net margin

NAICS codes signal to SAM.gov what TYPE of seller the agency wants.
Using the wrong codes returns contracts we cannot qualify for.
"""

# ---------------------------------------------------------------------------
# DME NAICS codes — dealer/wholesaler only (NOT manufacturer)
# ---------------------------------------------------------------------------

DME_NAICS_CODES = [
    # PRIMARY — Core DME resale model.
    # Government uses this when buying wheelchairs, scooters, beds, and other
    # DME FROM A DEALER OR WHOLESALER, not a factory.
    "423450",  # Medical, Dental & Hospital Equipment Merchant Wholesalers

    # SECONDARY — Rental/lease contracts; recurring revenue, lower competition.
    # VA and federal prisons often rent hospital beds and lifts rather than buy.
    "532283",  # Home Health Equipment Rental

    # TERTIARY — Retail DME to government facilities directly.
    "446199",  # All Other Health & Personal Care Stores

    # SUPPLEMENTAL — Catches mobility aids classified under ophthalmic goods.
    "423460",  # Ophthalmic Goods Merchant Wholesalers
]

# Excluded manufacturing codes — do NOT add back.
# 339113 (Surgical Appliance Manufacturing) and 339112 (Surgical Instrument Mfg)
# require the offeror to BE the manufacturer with FDA clearance. A reseller cannot qualify.

# ---------------------------------------------------------------------------
# Consulting NAICS codes — Dan's solo services
# ---------------------------------------------------------------------------

CONSULTING_NAICS_CODES = [
    # PRIMARY — Broad management consulting; covers process improvement, strategic planning.
    "541611",  # Administrative Management and General Management Consulting

    # Process optimization, operational excellence, Lean/Six Sigma engagements.
    "541618",  # Other Management Consulting Services

    # Agile transformation, Scrum coaching, leadership and project management training.
    "611430",  # Professional and Management Development Training

    # Low-code automation design, system integration, digital transformation.
    "541512",  # Computer Systems Design Services

    # General technical consulting; catches hybrid IT/business advisory work.
    "541519",  # Other Computer Related Services

    # Scientific/technical advisory; covers research-backed consulting engagements.
    "541690",  # Other Scientific and Technical Consulting Services
]

# ---------------------------------------------------------------------------
# Combined — used for the SAM.gov search call
# ---------------------------------------------------------------------------

ALL_NAICS_CODES = DME_NAICS_CODES + CONSULTING_NAICS_CODES

# Comma-joined string for the SAM.gov API "naics" parameter.
NAICS_CODES = ",".join(ALL_NAICS_CODES)

# ---------------------------------------------------------------------------
# DME keywords — products a DME dealer/reseller can supply
# ---------------------------------------------------------------------------

DME_KEYWORDS = [
    "wheelchair", "power wheelchair", "manual wheelchair", "transport chair",
    "electric wheelchair", "motorized wheelchair", "power chair",
    "jazzy", "quantum", "permobil",
    "mobility scooter", "scooter", "power scooter", "go-go",
    "hospital bed", "medical bed", "adjustable bed", "bariatric bed",
    "patient bed", "electric bed", "semi-electric bed",
    "patient lift", "hoyer", "ceiling lift", "floor lift",
    "transfer lift", "sit-to-stand",
    "walker", "rollator", "walking aid", "gait trainer", "crutch",
    "grab bar", "shower chair", "commode", "raised toilet seat",
    "bath safety", "bathroom safety",
    "durable medical equipment", "DME", "home medical equipment", "HME",
    "medical supply", "medical equipment dealer",
]

# ---------------------------------------------------------------------------
# Consulting keywords — Dan's expertise areas
# ---------------------------------------------------------------------------

CONSULTING_KEYWORDS = {
    # Process improvement
    "process improvement", "process optimization", "workflow improvement",
    "lean", "six sigma", "continuous improvement", "kaizen",
    "business process", "operational excellence", "efficiency improvement",
    # Agile & project management
    "agile", "scrum", "agile transformation", "agile coaching",
    "project management", "program management", "PMO",
    "change management", "organizational change",
    # Automation & digital transformation
    "automation", "process automation", "workflow automation",
    "low-code", "no-code", "digital transformation",
    "RPA", "robotic process automation",
    # Training & coaching
    "training", "coaching", "facilitation", "workshop",
    "agile training", "scrum training", "leadership development",
    # Strategy & management
    "strategic planning", "management consulting", "business consulting",
    "organizational development", "performance improvement",
}

# Contracts matching these are NOT a fit for Dan's consulting practice.
CONSULTING_EXCLUDE_KEYWORDS = {
    # Staffing / body shop
    "staff augmentation", "body shop", "permanent placement",
    # Technical roles not matching Dan's expertise
    "software development", "coding", "programming",
    "cybersecurity implementation", "penetration testing",
    "data science", "machine learning", "AI development",
    # Physical work / construction
    "construction", "installation", "renovation", "repair", "maintenance",
    "manufacturing", "fabrication", "production",
    "building improvement", "facility improvement",
    # Procurement / supply / equipment
    "supply", "procurement", "materials",
    "equipment rental", "equipment purchase", "equipment sales",
    "hardware", "machinery",
    # Facility services
    "janitorial", "custodial", "grounds maintenance", "facility maintenance",
    "security services", "guard services", "protective services",
    "food service", "catering", "meal preparation",
    # Medical / clinical (not process consulting)
    "medical services", "clinical services", "patient care",
    "nursing", "physician", "healthcare provider",
}
