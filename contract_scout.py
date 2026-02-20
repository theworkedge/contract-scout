#!/usr/bin/env python3
"""
Contract Scout - Automated government contract opportunity finder.

Searches SAM.gov for two solo business models in a single daily run:
  1. DME Resale    — equipment resale, 35-40% net margin
  2. Consulting    — Dan's process improvement / Agile / automation work, 80% net margin
"""

import csv
import logging
import os
import smtplib
import sys
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests
from dotenv import load_dotenv

from config import ALL_NAICS_CODES, DME_NAICS_CODES, NAICS_CODES
from dme_analyzer import DMEAnalyzer
from email_templates import create_opportunity_email

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv()

SAM_API_KEY = os.getenv("SAM_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD", "")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "")
RECIPIENT_NAME = os.getenv("RECIPIENT_NAME", "User")

SAM_API_URL = "https://api.sam.gov/opportunities/v2/search"
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"
CSV_FILE = Path("opportunities_log.csv")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("contract_scout.log"),
    ],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SAM.gov search
# ---------------------------------------------------------------------------


def search_sam_gov() -> list[dict]:
    """Query SAM.gov for recent solicitation opportunities across all NAICS codes."""
    posted_from = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%m/%d/%Y")
    posted_to = datetime.now(timezone.utc).strftime("%m/%d/%Y")

    params = {
        "api_key": SAM_API_KEY,
        "postedFrom": posted_from,
        "postedTo": posted_to,
        "ptype": "o,k",
        "naics": NAICS_CODES,
        "limit": 25,
    }

    log.info("Searching SAM.gov  postedFrom=%s  postedTo=%s", posted_from, posted_to)

    resp = requests.get(SAM_API_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    opportunities = data.get("opportunitiesData", [])
    log.info("SAM.gov returned %d opportunities", len(opportunities))
    return opportunities


# ---------------------------------------------------------------------------
# Business model classification
# ---------------------------------------------------------------------------


def classify_opportunities(opportunities: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split opportunities into DME and consulting groups by NAICS code.

    Returns (dme_opps, consulting_opps).
    """
    dme_set = set(DME_NAICS_CODES)
    dme, consulting = [], []
    for opp in opportunities:
        naics = opp.get("naicsCode", "")
        if naics in dme_set:
            opp["business_model"] = "DME Resale"
            dme.append(opp)
        else:
            opp["business_model"] = "Solo Consulting"
            consulting.append(opp)

    log.info(
        "Classified: %d DME opportunities, %d consulting opportunities",
        len(dme), len(consulting),
    )
    return dme, consulting


# ---------------------------------------------------------------------------
# Merge SAM.gov fields with analyzer scores
# ---------------------------------------------------------------------------


def merge_results(opportunities: list[dict], scores: list[dict]) -> list[dict]:
    """Attach SAM.gov metadata to analyzer score objects and sort by score."""
    sam_map = {opp.get("noticeId", ""): opp for opp in opportunities}
    merged = []

    for score_data in scores:
        nid = score_data.get("noticeId", "")
        opp = sam_map.get(nid, {})
        entry = {
            # SAM.gov fields
            "noticeId": nid,
            "title": opp.get("title", ""),
            "solicitationNumber": opp.get("solicitationNumber", ""),
            "naicsCode": opp.get("naicsCode", ""),
            "agency": opp.get("fullParentPathName", opp.get("departmentName", "")),
            "postedDate": opp.get("postedDate", ""),
            "responseDeadLine": opp.get("responseDeadLine", ""),
            "uiLink": opp.get("uiLink", ""),
            "setAside": opp.get("typeOfSetAsideDescription", ""),
            "placeOfPerformance": str(opp.get("placeOfPerformance", "")),
            "business_model": opp.get("business_model", ""),
            # All analyzer score fields (spread in)
            **score_data,
        }
        merged.append(entry)

    merged.sort(key=lambda x: x.get("score", 0), reverse=True)
    return merged


# ---------------------------------------------------------------------------
# CSV logging
# ---------------------------------------------------------------------------

CSV_COLUMNS = [
    "Business Model",
    "Est Net Margin",
    "Category",
    "Group",
    "Rank",
    "Score",
    "Title",
    "Agency",
    "Value",
    "Set-Aside",
    "Location",
    "Deadline",
    "Days Until Deadline",
    "Estimated Cost",
    "Gross Profit",
    "Your Net Profit",
    "Products / Services",
    "Past Performance Details",
    "Bid Recommendation",
    "Reason",
    "Solicitation Number",
    "SAM.gov URL",
]


def _days_until_deadline(deadline_str: str) -> str:
    if not deadline_str:
        return ""
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(deadline_str[:19], fmt[:len(deadline_str[:19])])
            return str((dt.date() - datetime.now(timezone.utc).date()).days)
        except ValueError:
            continue
    return ""


def log_to_csv(dme_results: list[dict], consulting_results: list[dict]) -> None:
    """Append all scored opportunities to the CSV log file."""
    write_header = not CSV_FILE.exists()

    with open(CSV_FILE, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        if write_header:
            writer.writeheader()

        for model_label, margin_label, results in [
            ("DME Resale", "35-40%", dme_results),
            ("Consulting Services", "80%", consulting_results),
        ]:
            no_pp = [r for r in results if not r.get("requires_past_performance", True)]
            needs_pp = [r for r in results if r.get("requires_past_performance", True)]

            for group_label, group in [
                ("No Past Performance Required", no_pp),
                ("Needs Past Performance", needs_pp),
            ]:
                for rank, r in enumerate(group, start=1):
                    profit = r.get("estimated_profit", {})
                    costs = r.get("estimated_costs", {})
                    deadline = r.get("responseDeadLine", "")

                    # Both DME and consulting now use net_profit
                    your_net_profit = profit.get("net_profit", "")

                    # Products vs services
                    products = r.get("products_needed", r.get("services_needed", []))

                    writer.writerow({
                        "Business Model": model_label,
                        "Est Net Margin": margin_label,
                        "Category": r.get("category", ""),
                        "Group": group_label,
                        "Rank": rank,
                        "Score": r.get("score", ""),
                        "Title": r.get("title", ""),
                        "Agency": r.get("agency", ""),
                        "Value": "",
                        "Set-Aside": r.get("setAside", ""),
                        "Location": r.get("placeOfPerformance", ""),
                        "Deadline": deadline,
                        "Days Until Deadline": _days_until_deadline(deadline),
                        "Estimated Cost": costs.get("total", ""),
                        "Gross Profit": profit.get("gross_profit", ""),
                        "Your Net Profit": your_net_profit,
                        "Products / Services": "; ".join(products),
                        "Past Performance Details": r.get("past_performance_details", ""),
                        "Bid Recommendation": r.get("bid_recommendation", ""),
                        "Reason": r.get("recommendation_reason", ""),
                        "Solicitation Number": r.get("solicitationNumber", ""),
                        "SAM.gov URL": r.get("uiLink", ""),
                    })

    log.info(
        "Logged %d DME + %d consulting opportunities to %s",
        len(dme_results), len(consulting_results), CSV_FILE,
    )


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------


def send_email(html_body: str, plain_body: str, subject: str) -> None:
    """Send the opportunity report via SMTP (multipart: HTML + plain text)."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = RECIPIENT_EMAIL

    # Attach plain text first (fallback), then HTML (preferred)
    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    log.info("Sending email to %s", RECIPIENT_EMAIL)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, RECIPIENT_EMAIL, msg.as_string())

    log.info("Email sent successfully")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    log.info("=== Contract Scout starting ===")

    # Validate required env vars
    missing = [v for v in ("SAM_API_KEY", "ANTHROPIC_API_KEY") if not os.getenv(v)]
    if missing:
        log.error("Missing required environment variables: %s", ", ".join(missing))
        sys.exit(1)

    # 1. Search SAM.gov across all NAICS codes
    all_opportunities = search_sam_gov()
    if not all_opportunities:
        log.info("No opportunities found. Exiting.")
        return

    # 2. Classify by business model
    dme_opps, consulting_opps = classify_opportunities(all_opportunities)

    # 3. Analyze each group with appropriate scoring criteria
    analyzer = DMEAnalyzer(api_key=ANTHROPIC_API_KEY, model=CLAUDE_MODEL)
    dme_scores = analyzer.analyze(dme_opps) if dme_opps else []
    consulting_scores = analyzer.analyze_consulting(consulting_opps) if consulting_opps else []

    # 4. Merge SAM.gov metadata with scores
    dme_results = merge_results(dme_opps, dme_scores)
    consulting_results = merge_results(consulting_opps, consulting_scores)

    log.info(
        "Results: %d DME, %d consulting",
        len(dme_results), len(consulting_results),
    )

    # 5. Log everything to CSV
    log_to_csv(dme_results, consulting_results)

    # 6. Build and send email
    dme_count = len(dme_results)
    consulting_count = len(consulting_results)

    if dme_results or consulting_results:
        email_vars = ("EMAIL_ADDRESS", "EMAIL_APP_PASSWORD", "RECIPIENT_EMAIL")
        if all(os.getenv(v) for v in email_vars):
            html, plain = create_opportunity_email(dme_results, consulting_results)
            subject = (
                f"Contract Scout: {dme_count} DME + {consulting_count} Consulting "
                f"Opportunities — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
            )
            send_email(html, plain, subject)
        else:
            log.warning(
                "Email credentials not configured — skipping email. "
                "Set EMAIL_ADDRESS, EMAIL_APP_PASSWORD, and RECIPIENT_EMAIL."
            )
    else:
        log.info("No opportunities found. No email sent.")

    log.info("=== Contract Scout finished ===")


if __name__ == "__main__":
    main()
