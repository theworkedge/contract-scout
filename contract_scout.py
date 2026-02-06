#!/usr/bin/env python3
"""
Contract Scout - Automated government contract opportunity finder.

Searches SAM.gov for contract opportunities, analyzes them with Claude AI,
emails top matches, and logs everything to CSV.
"""

import csv
import json
import logging
import os
import smtplib
import sys
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import anthropic
import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv()

SAM_API_KEY = os.getenv("SAM_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "")
RECIPIENT_NAME = os.getenv("RECIPIENT_NAME", "User")

SAM_API_URL = "https://api.sam.gov/opportunities/v2/search"
NAICS_CODES = "541611,541990,611430,541519,541720"
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"
CSV_FILE = Path("opportunities_log.csv")
MIN_SCORE = 7

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
    """Query SAM.gov for recent solicitation opportunities."""
    posted_from = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%m/%d/%Y")
    posted_to = datetime.now(timezone.utc).strftime("%m/%d/%Y")

    params = {
        "api_key": SAM_API_KEY,
        "postedFrom": posted_from,
        "postedTo": posted_to,
        "ptype": "o,k",
        "naics": NAICS_CODES,
        "limit": 100,
    }

    log.info("Searching SAM.gov  postedFrom=%s  postedTo=%s", posted_from, posted_to)

    resp = requests.get(SAM_API_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    opportunities = data.get("opportunitiesData", [])
    log.info("SAM.gov returned %d opportunities", len(opportunities))
    return opportunities


# ---------------------------------------------------------------------------
# Claude analysis
# ---------------------------------------------------------------------------

ANALYSIS_PROMPT = """\
You are a government contracting analyst. Evaluate each opportunity below and \
score it 1-10 for fit with a small consulting firm that specializes in:
- Deliverables-based work (consulting, training, research, assessments)
- Contract value sweet-spot: $75K-$250K
- Deadline at least 10 days away
- Keywords that boost score: process improvement, Agile, consulting, \
assessment, recommendations, training, facilitation, strategic planning

Red flags that lower the score:
- Staff augmentation or body-shop contracts
- Full-time on-site requirements
- Security clearance requirements
- Very large or very small dollar values outside the sweet-spot

For each opportunity return a JSON object with:
- noticeId (string)
- score (integer 1-10)
- reasoning (string, 1-2 sentences)
- key_requirements (string, brief summary of what the government wants)

Return ONLY a JSON array of objects — no markdown fences, no commentary.

Opportunities:
{opportunities_json}
"""


def analyze_with_claude(opportunities: list[dict]) -> list[dict]:
    """Send opportunities to Claude for scoring and analysis."""
    if not opportunities:
        return []

    # Build a slim payload so we stay well within context limits.
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
                "uiLink": opp.get("uiLink", ""),
            }
        )

    prompt = ANALYSIS_PROMPT.format(opportunities_json=json.dumps(slim, indent=2))

    log.info("Sending %d opportunities to Claude for analysis", len(slim))

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()

    scored: list[dict] = json.loads(raw)
    log.info("Claude returned scores for %d opportunities", len(scored))
    return scored


# ---------------------------------------------------------------------------
# Merge results
# ---------------------------------------------------------------------------


def merge_results(
    opportunities: list[dict], scores: list[dict]
) -> list[dict]:
    """Combine SAM.gov data with Claude scores."""
    score_map = {s["noticeId"]: s for s in scores}
    merged = []
    for opp in opportunities:
        nid = opp.get("noticeId", "")
        if nid in score_map:
            entry = {
                "noticeId": nid,
                "title": opp.get("title", ""),
                "solicitationNumber": opp.get("solicitationNumber", ""),
                "naicsCode": opp.get("naicsCode", ""),
                "agency": opp.get(
                    "fullParentPathName", opp.get("departmentName", "")
                ),
                "postedDate": opp.get("postedDate", ""),
                "responseDeadLine": opp.get("responseDeadLine", ""),
                "uiLink": opp.get("uiLink", ""),
                "score": score_map[nid].get("score", 0),
                "reasoning": score_map[nid].get("reasoning", ""),
                "key_requirements": score_map[nid].get("key_requirements", ""),
            }
            merged.append(entry)
    merged.sort(key=lambda x: x["score"], reverse=True)
    return merged


# ---------------------------------------------------------------------------
# CSV logging
# ---------------------------------------------------------------------------

CSV_COLUMNS = [
    "date_found",
    "title",
    "solicitation_id",
    "naics",
    "agency",
    "estimated_value",
    "deadline",
    "score",
    "reasoning",
    "sam_url",
    "status",
]


def log_to_csv(results: list[dict]) -> None:
    """Append scored opportunities to the CSV log file."""
    write_header = not CSV_FILE.exists()

    with open(CSV_FILE, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        if write_header:
            writer.writeheader()
        for r in results:
            writer.writerow(
                {
                    "date_found": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    "title": r.get("title", ""),
                    "solicitation_id": r.get("solicitationNumber", ""),
                    "naics": r.get("naicsCode", ""),
                    "agency": r.get("agency", ""),
                    "estimated_value": "",
                    "deadline": r.get("responseDeadLine", ""),
                    "score": r.get("score", ""),
                    "reasoning": r.get("reasoning", ""),
                    "sam_url": r.get("uiLink", ""),
                    "status": "new",
                }
            )
    log.info("Logged %d opportunities to %s", len(results), CSV_FILE)


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------


def build_html(top: list[dict]) -> str:
    """Build an HTML email body for the top opportunities."""
    rows = ""
    for r in top:
        rows += f"""
        <tr style="border-bottom:1px solid #ddd;">
            <td style="padding:12px;vertical-align:top;">
                <strong>{r['title']}</strong><br>
                <span style="color:#555;">Agency:</span> {r['agency']}<br>
                <span style="color:#555;">Solicitation:</span> {r.get('solicitationNumber', 'N/A')}<br>
                <span style="color:#555;">NAICS:</span> {r.get('naicsCode', 'N/A')}<br>
                <span style="color:#555;">Deadline:</span> {r.get('responseDeadLine', 'N/A')}
            </td>
            <td style="padding:12px;text-align:center;vertical-align:top;font-size:24px;font-weight:bold;color:#2a7ae2;">
                {r['score']}/10
            </td>
            <td style="padding:12px;vertical-align:top;">
                <em>{r['reasoning']}</em><br><br>
                <strong>Key requirements:</strong> {r.get('key_requirements', 'N/A')}
            </td>
            <td style="padding:12px;vertical-align:top;text-align:center;">
                <a href="{r.get('uiLink', '#')}" style="background:#2a7ae2;color:#fff;padding:8px 14px;border-radius:4px;text-decoration:none;">View on SAM.gov</a>
            </td>
        </tr>"""

    return f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;">
    <h2 style="color:#2a7ae2;">Contract Scout — Top Opportunities</h2>
    <p>Found <strong>{len(top)}</strong> opportunities scoring {MIN_SCORE}+ out of 10.</p>
    <table style="width:100%;border-collapse:collapse;">
        <tr style="background:#f4f4f4;">
            <th style="padding:10px;text-align:left;">Opportunity</th>
            <th style="padding:10px;">Score</th>
            <th style="padding:10px;text-align:left;">Analysis</th>
            <th style="padding:10px;">Link</th>
        </tr>
        {rows}
    </table>
    <p style="margin-top:20px;font-size:12px;color:#999;">
        Generated by Contract Scout on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
    </p>
    </body></html>"""


def send_email(html_body: str) -> None:
    """Send the opportunity report via Gmail SMTP."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = (
        f"Contract Scout Report — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
    )
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(html_body, "html"))

    log.info("Sending email to %s via Gmail SMTP", RECIPIENT_EMAIL)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, RECIPIENT_EMAIL, msg.as_string())

    log.info("Email sent successfully")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    log.info("=== Contract Scout starting ===")

    # Validate required env vars
    missing = []
    for var in ("SAM_API_KEY", "ANTHROPIC_API_KEY"):
        if not os.getenv(var):
            missing.append(var)
    if missing:
        log.error("Missing required environment variables: %s", ", ".join(missing))
        sys.exit(1)

    # 1. Search SAM.gov
    opportunities = search_sam_gov()
    if not opportunities:
        log.info("No opportunities found. Exiting.")
        return

    # 2. Analyze with Claude
    scores = analyze_with_claude(opportunities)

    # 3. Merge and filter
    results = merge_results(opportunities, scores)
    top = [r for r in results if r["score"] >= MIN_SCORE]
    log.info(
        "%d opportunities scored, %d meet threshold (%d+)",
        len(results),
        len(top),
        MIN_SCORE,
    )

    # 4. Log everything to CSV
    log_to_csv(results)

    # 5. Email top opportunities
    if top:
        email_vars = ("GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "RECIPIENT_EMAIL")
        if all(os.getenv(v) for v in email_vars):
            html = build_html(top)
            send_email(html)
        else:
            log.warning(
                "Email credentials not configured — skipping email. "
                "Set GMAIL_ADDRESS, GMAIL_APP_PASSWORD, and RECIPIENT_EMAIL."
            )
    else:
        log.info("No opportunities scored %d+. No email sent.", MIN_SCORE)

    log.info("=== Contract Scout finished ===")


if __name__ == "__main__":
    main()
