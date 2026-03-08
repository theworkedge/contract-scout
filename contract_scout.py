#!/usr/bin/env python3
"""
Contract Scout - Automated Government Contract Opportunity Finder

Searches SAM.gov for relevant contract opportunities, analyzes them
with Claude AI, and sends email notifications for high-scoring matches.
"""

import csv
import json
import logging
import os
import smtplib
import sys
from datetime import datetime, timedelta
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

REQUIRED_ENV_VARS = [
    "SAM_API_KEY",
    "ANTHROPIC_API_KEY",
    "EMAIL_ADDRESS",
    "EMAIL_APP_PASSWORD",
    "RECIPIENT_EMAIL",
    "RECIPIENT_NAME",
]

SAM_SEARCH_URL = "https://api.sam.gov/opportunities/v2/search"
NAICS_CODES = "541611,541990,611430,541519,541720"
SEARCH_DAYS = 2
RESULT_LIMIT = 100
POST_TYPES = "o,k"

CLAUDE_MODEL = "claude-sonnet-4-5-20250929"
CLAUDE_MAX_TOKENS = 4000
MIN_SCORE_EMAIL = 7
MIN_SCORE_INCLUDE = 6

CSV_FILE = Path("opportunities_log.csv")
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

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("contract_scout")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def validate_env() -> dict[str, str]:
    """Validate that all required environment variables are set."""
    log.info("Validating environment variables...")
    env = {}
    missing = []
    for var in REQUIRED_ENV_VARS:
        val = os.getenv(var)
        if not val:
            missing.append(var)
        else:
            env[var] = val
    if missing:
        log.error("Missing required environment variables: %s", ", ".join(missing))
        sys.exit(1)
    log.info("All environment variables present.")
    return env


# ---------------------------------------------------------------------------
# 1. Search SAM.gov
# ---------------------------------------------------------------------------


def search_sam_gov(api_key: str) -> list[dict]:
    """Query the SAM.gov opportunities API for recent solicitations."""
    today = datetime.now()
    posted_from = (today - timedelta(days=SEARCH_DAYS)).strftime("%m/%d/%Y")
    posted_to = today.strftime("%m/%d/%Y")

    params = {
        "api_key": api_key,
        "postedFrom": posted_from,
        "postedTo": posted_to,
        "ncode": NAICS_CODES,
        "ptype": POST_TYPES,
        "limit": RESULT_LIMIT,
    }

    log.info(
        "Searching SAM.gov  |  NAICS: %s  |  Date range: %s – %s",
        NAICS_CODES,
        posted_from,
        posted_to,
    )

    try:
        resp = requests.get(SAM_SEARCH_URL, params=params, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.error("SAM.gov API request failed: %s", exc)
        return []

    data = resp.json()
    opportunities = data.get("opportunitiesData", [])
    log.info("SAM.gov returned %d opportunities.", len(opportunities))
    return opportunities


# ---------------------------------------------------------------------------
# 2. Analyze with Claude AI
# ---------------------------------------------------------------------------

ANALYSIS_PROMPT = """\
You are a government contracting analyst for a small consulting firm that specializes in:
- Management consulting & process improvement
- Agile coaching & training
- Digital transformation & automation
- Research & analysis
- Strategic planning & roadmaps

Analyze the following government contract opportunities and score each one from 1–10 \
based on how well it fits our firm's capabilities.

SCORING CRITERIA

GOOD SIGNS (higher score):
- Deliverables-based work: consulting, assessment, recommendations, roadmap, report
- Keywords: process improvement, Agile, training, automation, research, digital transformation
- Clear scope with defined deliverables
- Deadline 10+ days from today ({today})
- Small business set-aside
- Estimated value $75K–$250K

BAD SIGNS (lower score):
- Staff augmentation or full-time on-site requirement
- Security clearance required
- Deadline less than 7 days from today ({today})
- Manufacturing, hardware, or construction focus
- Incumbent contractor mentioned

Return ONLY valid JSON in this exact format (no markdown fences):
{{
  "opportunities": [
    {{
      "index": 0,
      "title": "exact title from input",
      "score": 8,
      "reasoning": "short explanation of why it fits",
      "key_requirements": ["req1", "req2", "req3"],
      "estimated_value": "$XXX,XXX or Unknown",
      "deadline": "date or Unknown",
      "red_flags": "concerns or None"
    }}
  ]
}}

Only include opportunities with score >= {min_score}. Sort by score descending.

--- OPPORTUNITIES ---
{opportunities_text}
"""


def format_opportunity_for_analysis(idx: int, opp: dict) -> str:
    """Format a single SAM.gov opportunity for the Claude prompt."""
    lines = [
        f"[{idx}] Title: {opp.get('title', 'N/A')}",
        f"    Solicitation #: {opp.get('solicitationNumber', 'N/A')}",
        f"    Notice ID: {opp.get('noticeId', 'N/A')}",
        f"    Agency: {opp.get('fullParentPathName', opp.get('departmentName', 'N/A'))}",
        f"    NAICS: {opp.get('naicsCode', 'N/A')}",
        f"    Type: {opp.get('type', 'N/A')}",
        f"    Set-Aside: {opp.get('typeOfSetAsideDescription', 'None')}",
        f"    Posted: {opp.get('postedDate', 'N/A')}",
        f"    Response Deadline: {opp.get('responseDeadLine', 'N/A')}",
        f"    Description: {(opp.get('description') or 'N/A')[:1500]}",
    ]
    return "\n".join(lines)


def analyze_opportunities(opportunities: list[dict], api_key: str) -> list[dict]:
    """Send opportunities to Claude for scoring and analysis."""
    if not opportunities:
        log.info("No opportunities to analyze.")
        return []

    log.info("Preparing %d opportunities for Claude analysis...", len(opportunities))

    opp_texts = [
        format_opportunity_for_analysis(i, opp) for i, opp in enumerate(opportunities)
    ]
    opportunities_text = "\n\n".join(opp_texts)
    today_str = datetime.now().strftime("%Y-%m-%d")

    prompt = ANALYSIS_PROMPT.format(
        today=today_str,
        min_score=MIN_SCORE_INCLUDE,
        opportunities_text=opportunities_text,
    )

    log.info("Sending to Claude (%s) for analysis...", CLAUDE_MODEL)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=CLAUDE_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIError as exc:
        log.error("Claude API request failed: %s", exc)
        return []

    raw = message.content[0].text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        log.error("Failed to parse Claude response as JSON. Raw response:\n%s", raw)
        return []

    scored = result.get("opportunities", [])
    log.info("Claude returned %d scored opportunities (score >= %d).", len(scored), MIN_SCORE_INCLUDE)
    return scored


# ---------------------------------------------------------------------------
# 3. Send Email Notification
# ---------------------------------------------------------------------------


def build_email_html(scored: list[dict], opportunities: list[dict]) -> str:
    """Build an HTML email body for scored opportunities."""
    today_str = datetime.now().strftime("%B %d, %Y")
    rows_html = ""

    for item in scored:
        idx = item.get("index", 0)
        opp = opportunities[idx] if idx < len(opportunities) else {}
        notice_id = opp.get("noticeId", "")
        sam_url = f"https://sam.gov/opp/{notice_id}/view" if notice_id else "#"
        score = item.get("score", 0)

        if score >= 8:
            badge_color = "#22c55e"
            badge_label = "Strong Match"
        else:
            badge_color = "#eab308"
            badge_label = "Potential Match"

        reqs_html = "".join(
            f"<li>{r}</li>" for r in item.get("key_requirements", [])
        )

        red_flags = item.get("red_flags", "None")
        red_flags_html = ""
        if red_flags and red_flags.lower() != "none":
            red_flags_html = f"""
            <div style="margin-top:8px;padding:8px 12px;background:#fef2f2;border-left:3px solid #ef4444;border-radius:4px;font-size:13px;color:#991b1b;">
                <strong>Red Flags:</strong> {red_flags}
            </div>"""

        rows_html += f"""
        <div style="border:1px solid #e5e7eb;border-radius:8px;padding:20px;margin-bottom:16px;background:#fff;">
            <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:8px;">
                <h3 style="margin:0;font-size:16px;color:#111827;">
                    <a href="{sam_url}" style="color:#2563eb;text-decoration:none;">{item.get('title', 'Untitled')}</a>
                </h3>
                <span style="background:{badge_color};color:#fff;padding:4px 10px;border-radius:12px;font-size:12px;font-weight:600;white-space:nowrap;margin-left:12px;">
                    Score {score}/10 &ndash; {badge_label}
                </span>
            </div>
            <p style="margin:4px 0 12px;font-size:14px;color:#374151;"><strong>Why it's a good fit:</strong> {item.get('reasoning', 'N/A')}</p>
            <table style="font-size:13px;color:#4b5563;margin-bottom:8px;" cellpadding="0" cellspacing="0">
                <tr><td style="padding-right:12px;font-weight:600;">Estimated Value:</td><td>{item.get('estimated_value', 'Unknown')}</td></tr>
                <tr><td style="padding-right:12px;font-weight:600;">Deadline:</td><td>{item.get('deadline', 'Unknown')}</td></tr>
            </table>
            <div style="margin-bottom:12px;">
                <strong style="font-size:13px;color:#374151;">Key Requirements:</strong>
                <ul style="margin:4px 0 0 20px;padding:0;font-size:13px;color:#4b5563;">{reqs_html}</ul>
            </div>
            {red_flags_html}
            <div style="margin-top:14px;">
                <a href="{sam_url}" style="display:inline-block;padding:10px 20px;background:#2563eb;color:#fff;text-decoration:none;border-radius:6px;font-size:13px;font-weight:600;">VIEW ON SAM.GOV</a>
            </div>
        </div>"""

    return f"""\
    <html>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f3f4f6;padding:20px;margin:0;">
        <div style="max-width:680px;margin:0 auto;">
            <div style="background:#1e3a5f;color:#fff;padding:24px;border-radius:8px 8px 0 0;text-align:center;">
                <h1 style="margin:0;font-size:22px;">Contract Scout Report</h1>
                <p style="margin:6px 0 0;opacity:0.85;font-size:14px;">{today_str}</p>
            </div>
            <div style="background:#f9fafb;padding:20px;border-radius:0 0 8px 8px;">
                <p style="font-size:14px;color:#374151;margin-top:0;">
                    Found <strong>{len(scored)}</strong> opportunities scoring 7+ out of today's scan.
                </p>
                {rows_html}
                <p style="font-size:12px;color:#9ca3af;text-align:center;margin-top:20px;">
                    Generated by Contract Scout &bull; Scores are AI-estimated and should be verified manually.
                </p>
            </div>
        </div>
    </body>
    </html>"""


def send_email(scored: list[dict], opportunities: list[dict], env: dict[str, str]) -> None:
    """Send HTML email with scored opportunities."""
    email_worthy = [s for s in scored if s.get("score", 0) >= MIN_SCORE_EMAIL]
    if not email_worthy:
        log.info("No opportunities scored %d+. Skipping email.", MIN_SCORE_EMAIL)
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    subject = f"\U0001f3af {len(email_worthy)} Contract Opportunities for {today_str}"

    html = build_email_html(email_worthy, opportunities)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = env["GMAIL_ADDRESS"]
    msg["To"] = env["RECIPIENT_EMAIL"]
    msg.attach(MIMEText(html, "html"))

    log.info("Sending email to %s (%d opportunities)...", env["RECIPIENT_EMAIL"], len(email_worthy))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(env["GMAIL_ADDRESS"], env["GMAIL_APP_PASSWORD"])
            server.sendmail(env["GMAIL_ADDRESS"], env["RECIPIENT_EMAIL"], msg.as_string())
        log.info("Email sent successfully.")
    except smtplib.SMTPException as exc:
        log.error("Failed to send email: %s", exc)


# ---------------------------------------------------------------------------
# 4. Log to CSV
# ---------------------------------------------------------------------------


def log_to_csv(scored: list[dict], opportunities: list[dict]) -> None:
    """Append scored opportunities to the CSV log."""
    file_exists = CSV_FILE.exists()
    today_str = datetime.now().strftime("%Y-%m-%d")

    log.info("Writing %d opportunities to %s...", len(scored), CSV_FILE)

    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        if not file_exists:
            writer.writeheader()

        for item in scored:
            idx = item.get("index", 0)
            opp = opportunities[idx] if idx < len(opportunities) else {}
            notice_id = opp.get("noticeId", "")
            sam_url = f"https://sam.gov/opp/{notice_id}/view" if notice_id else ""

            writer.writerow(
                {
                    "date_found": today_str,
                    "title": item.get("title", ""),
                    "solicitation_id": opp.get("solicitationNumber", ""),
                    "naics": opp.get("naicsCode", ""),
                    "agency": opp.get(
                        "fullParentPathName", opp.get("departmentName", "")
                    ),
                    "estimated_value": item.get("estimated_value", "Unknown"),
                    "deadline": item.get("deadline", "Unknown"),
                    "score": item.get("score", 0),
                    "reasoning": item.get("reasoning", ""),
                    "sam_url": sam_url,
                    "status": "NEW",
                }
            )

    log.info("CSV log updated.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    log.info("=" * 60)
    log.info("CONTRACT SCOUT - Starting scan")
    log.info("=" * 60)

    # Validate environment
    env = validate_env()

    # Step 1 - Search SAM.gov
    opportunities = search_sam_gov(env["SAM_API_KEY"])
    if not opportunities:
        log.info("No opportunities found. Exiting.")
        return

    # Step 2 - Analyze with Claude
    scored = analyze_opportunities(opportunities, env["ANTHROPIC_API_KEY"])
    if not scored:
        log.info("No opportunities met the minimum score threshold. Exiting.")
        return

    log.info(
        "Top opportunity: \"%s\" (score %s)",
        scored[0].get("title", "?"),
        scored[0].get("score", "?"),
    )

    # Step 3 - Log to CSV
    log_to_csv(scored, opportunities)

    # Step 4 - Send email notification
    send_email(scored, opportunities, env)

    log.info("=" * 60)
    log.info("CONTRACT SCOUT - Scan complete (%d opportunities logged)", len(scored))
    log.info("=" * 60)


if __name__ == "__main__":
    main()
