#!/usr/bin/env python3
"""
email_templates.py — HTML + plain-text email builder for Contract Scout.

create_opportunity_email() returns (html_str, plain_str) for multipart MIME sending.

Score filters applied before display:
  NO PAST PERF section: show only score >= 5
  NEEDS PAST PERF section: show only score >= 6, max 5 shown
"""

from __future__ import annotations

import html as _html_module
from collections import defaultdict
from datetime import datetime, timezone


CATEGORY_ORDER = [
    "Wheelchairs - Power",
    "Hospital Beds",
    "Wheelchairs - Manual",
    "Mobility Scooters",
    "Patient Lifts",
    "Walkers and Mobility Aids",
    "Bathroom Safety",
    "Mixed DME",
    "Other Medical Equipment",
]

CONSULTING_CATEGORY_ORDER = [
    "Process Improvement & Operational Excellence",
    "Agile Transformation & Project Management",
    "Automation & Digital Transformation",
    "Training & Organizational Development",
    "Management Consulting",
    "Other Consulting",
]

MIN_SCORE_NO_PP = 5
MIN_SCORE_NEEDS_PP = 6
MAX_NEEDS_PP_SHOWN = 5


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def create_opportunity_email(
    dme_opportunities: list[dict],
    consulting_opportunities: list[dict],
) -> tuple[str, str]:
    """Build HTML and plain-text versions of the daily opportunity report.

    Returns:
        (html_body, plain_body) — use both for multipart MIME email.
    """
    html = _build_html_email(dme_opportunities, consulting_opportunities)
    plain = _build_plain_email(dme_opportunities, consulting_opportunities)
    return html, plain


# ---------------------------------------------------------------------------
# HTML email
# ---------------------------------------------------------------------------

_CSS = """
body{font-family:Arial,Helvetica,sans-serif;margin:0;padding:0;background:#f3f4f6;color:#1f2937}
.wrapper{max-width:760px;margin:0 auto;background:#fff}
.hdr{background:#1e40af;color:#fff;padding:22px 28px}
.hdr h1{margin:0 0 6px;font-size:20px;font-weight:700}
.hdr p{margin:0;font-size:13px;opacity:.85}
.summary{background:#eff6ff;border-left:4px solid #3b82f6;padding:16px 24px;margin:20px 24px;border-radius:4px}
.summary h2{margin:0 0 10px;font-size:15px;color:#1e40af}
.stat-grid{display:flex;flex-wrap:wrap;gap:10px 24px}
.stat-item{font-size:13px;color:#374151}
.stat-item b{font-size:18px;color:#1e40af;display:block}
.part-hdr{background:#1f2937;color:#fff;padding:12px 24px;margin-top:24px}
.part-hdr h2{margin:0;font-size:14px;letter-spacing:.03em}
.section{padding:4px 20px 12px}
.sec-label{font-size:11px;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:.06em;padding:14px 4px 6px;border-bottom:1px solid #e5e7eb;margin-bottom:10px}
.card{border:1px solid #e5e7eb;border-radius:6px;margin:10px 0;overflow:hidden}
.card-hdr{padding:10px 14px;display:flex;align-items:center;gap:10px}
.card-hdr.bid{background:#f0fdf4;border-bottom:2px solid #86efac}
.card-hdr.nobid{background:#fff7ed;border-bottom:2px solid#fed7aa}
.score{font-size:22px;font-weight:700;min-width:44px}
.score.bid{color:#16a34a}
.score.nobid{color:#ea580c}
.rec{font-size:10px;font-weight:700;padding:2px 7px;border-radius:3px;white-space:nowrap}
.rec.bid{background:#dcfce7;color:#15803d}
.rec.nobid{background:#ffedd5;color:#c2410c}
.card-title{font-weight:700;font-size:14px;flex:1;line-height:1.3}
.card-body{padding:10px 14px;font-size:13px;line-height:1.5}
.row{margin:3px 0;color:#4b5563}
.row b{color:#111827}
.highlights{background:#f9fafb;border-radius:4px;padding:8px 12px;margin:8px 0;font-size:12px}
.hi{color:#15803d;margin:2px 0}
.ri{color:#b91c1c;margin:2px 0}
.sam-btn{display:inline-block;margin-top:10px;background:#2563eb;color:#fff;padding:7px 16px;border-radius:4px;text-decoration:none;font-size:12px;font-weight:700}
.brief{padding:6px 10px;border-left:3px solid #d1d5db;margin:4px 0;font-size:13px;color:#374151}
.no-opps{color:#9ca3af;font-style:italic;padding:10px 4px;font-size:13px}
.footer{text-align:center;padding:18px;font-size:11px;color:#9ca3af;border-top:1px solid #e5e7eb}
"""


def _h(text: str) -> str:
    """HTML-escape a string."""
    return _html_module.escape(str(text))


def _build_html_email(dme: list[dict], consulting: list[dict]) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    parts = [
        f"<!DOCTYPE html><html><head><meta charset='UTF-8'><style>{_CSS}</style></head>",
        "<body><div class='wrapper'>",
        _html_header(generated_at, dme, consulting),
        _html_summary(dme, consulting),
        _html_part(dme, "PART 1: DME CONTRACTS  (EQUIPMENT RESALE)",
                   "Product Resale  |  Est. Net Margin: 35-40%", is_dme=True),
        _html_part(consulting, "PART 2: CONSULTING CONTRACTS  (PROFESSIONAL SERVICES)",
                   "Solo Work  |  Est. Net Margin: 80%", is_dme=False),
        "<div class='footer'>Contract Scout &mdash; theworkedge.ai</div>",
        "</div></body></html>",
    ]
    return "".join(parts)


def _html_header(generated_at: str, dme: list[dict], consulting: list[dict]) -> str:
    dme_bid = sum(1 for o in dme if o.get("bid_recommendation") == "BID")
    con_bid = sum(1 for o in consulting if o.get("bid_recommendation") == "BID")
    return (
        f"<div class='hdr'>"
        f"<h1>Contract Scout &mdash; Daily Opportunity Report</h1>"
        f"<p>Generated: {_h(generated_at)} &nbsp;|&nbsp; "
        f"DME: {len(dme)} contracts ({dme_bid} BID) &nbsp;|&nbsp; "
        f"Consulting: {len(consulting)} contracts ({con_bid} BID)</p>"
        f"</div>"
    )


def _html_summary(dme: list[dict], consulting: list[dict]) -> str:
    all_opps = dme + consulting
    high_priority = [o for o in all_opps if o.get("score", 0) >= 8
                     and not o.get("requires_past_performance", True)]
    review = [o for o in all_opps if 5 <= o.get("score", 0) <= 7
              and not o.get("requires_past_performance", True)]
    monitor = [o for o in all_opps if o.get("requires_past_performance", True)
               and o.get("score", 0) >= MIN_SCORE_NEEDS_PP]

    dme_profit = sum(
        o.get("estimated_profit", {}).get("net_profit", 0) for o in dme
        if not o.get("requires_past_performance", True) and o.get("score", 0) >= MIN_SCORE_NO_PP
    )
    con_profit = sum(
        o.get("estimated_profit", {}).get("net_profit", 0) for o in consulting
        if not o.get("requires_past_performance", True) and o.get("score", 0) >= MIN_SCORE_NO_PP
    )

    lines = [
        "<div class='summary'>",
        "<h2>&#x1F4CA; Today's Summary</h2>",
        "<div class='stat-grid'>",
        f"<div class='stat-item'><b>{len(high_priority)}</b>High Priority (8-10)</div>",
        f"<div class='stat-item'><b>{len(review)}</b>Review (5-7)</div>",
        f"<div class='stat-item'><b>{len(monitor)}</b>Monitor (needs PP)</div>",
        f"<div class='stat-item'><b>${dme_profit:,.0f}</b>DME Net Potential</div>",
        f"<div class='stat-item'><b>${con_profit:,.0f}</b>Consulting Net Potential</div>",
        "</div>",
        "</div>",
    ]
    return "".join(lines)


def _html_part(opportunities: list[dict], title: str, subtitle: str, is_dme: bool) -> str:
    cat_order = CATEGORY_ORDER if is_dme else CONSULTING_CATEGORY_ORDER
    default_cat = "Other Medical Equipment" if is_dme else "Other Consulting"

    no_pp = sorted(
        [o for o in opportunities if not o.get("requires_past_performance", True)
         and o.get("score", 0) >= MIN_SCORE_NO_PP],
        key=lambda x: x.get("score", 0), reverse=True,
    )
    needs_pp = sorted(
        [o for o in opportunities if o.get("requires_past_performance", True)
         and o.get("score", 0) >= MIN_SCORE_NEEDS_PP],
        key=lambda x: x.get("score", 0), reverse=True,
    )

    parts = [
        f"<div class='part-hdr'><h2>{_h(title)}<br>"
        f"<span style='font-size:11px;opacity:.75;font-weight:400'>{_h(subtitle)}</span></h2></div>",
        "<div class='section'>",
        _html_no_pp_section(no_pp, is_dme, cat_order, default_cat),
        _html_needs_pp_section(needs_pp),
        "</div>",
    ]
    return "".join(parts)


def _html_no_pp_section(opportunities: list[dict], is_dme: bool,
                        cat_order: list[str], default_cat: str) -> str:
    net_potential = sum(o.get("estimated_profit", {}).get("net_profit", 0) for o in opportunities)
    lines = [
        f"<div class='sec-label'>&#x2705; No Past Performance Required &mdash; "
        f"{len(opportunities)} contract{'s' if len(opportunities) != 1 else ''} | "
        f"Net potential: ${net_potential:,.0f}</div>"
    ]

    if not opportunities:
        lines.append("<div class='no-opps'>No viable opportunities found today "
                     f"(all scored below {MIN_SCORE_NO_PP}/10)</div>")
        return "".join(lines)

    by_cat: dict[str, list[dict]] = defaultdict(list)
    for opp in opportunities:
        by_cat[opp.get("category", default_cat)].append(opp)

    ordered_cats = [c for c in cat_order if c in by_cat]
    ordered_cats += [c for c in by_cat if c not in cat_order]

    for cat in ordered_cats:
        cat_opps = sorted(by_cat[cat], key=lambda x: x.get("score", 0), reverse=True)
        cat_profit = sum(o.get("estimated_profit", {}).get("net_profit", 0) for o in cat_opps)
        lines.append(
            f"<div style='font-size:12px;font-weight:700;color:#374151;margin:14px 0 4px;"
            f"text-transform:uppercase;letter-spacing:.04em'>{_h(cat)} &mdash; "
            f"{len(cat_opps)} contract{'s' if len(cat_opps) != 1 else ''} | "
            f"${cat_profit:,.0f} potential</div>"
        )
        for rank, opp in enumerate(cat_opps, start=1):
            lines.append(_html_card(rank, opp, is_dme))

    return "".join(lines)


def _html_needs_pp_section(opportunities: list[dict]) -> str:
    shown = opportunities[:MAX_NEEDS_PP_SHOWN]
    lines = [
        f"<div class='sec-label'>&#x23F3; Needs Past Performance &mdash; "
        f"{len(opportunities)} contract{'s' if len(opportunities) != 1 else ''} "
        f"(monitor for future)</div>"
    ]

    if not opportunities:
        lines.append("<div class='no-opps'>No relevant opportunities requiring "
                     "past performance today.</div>")
        return "".join(lines)

    for opp in shown:
        score = opp.get("score", 0)
        title = opp.get("title", "Untitled")[:70]
        agency = opp.get("agency", "")[:50]
        url = opp.get("uiLink", "")
        link = (f" <a href='{_h(url)}' target='_blank' style='color:#2563eb;font-size:11px'>"
                f"[view]</a>") if url else ""
        lines.append(
            f"<div class='brief'>Score {score}/10 &mdash; {_h(title)} &mdash; "
            f"<em>{_h(agency)}</em>{link}</div>"
        )

    if len(opportunities) > MAX_NEEDS_PP_SHOWN:
        lines.append(
            f"<div style='font-size:12px;color:#6b7280;padding:4px 4px'>...and "
            f"{len(opportunities) - MAX_NEEDS_PP_SHOWN} more (see CSV log for full list)</div>"
        )

    return "".join(lines)


def _html_card(rank: int, opp: dict, is_dme: bool) -> str:
    score = opp.get("score", 0)
    rec = opp.get("bid_recommendation", "NO-BID")
    is_bid = rec == "BID"
    card_cls = "bid" if is_bid else "nobid"
    score_cls = "bid" if is_bid else "nobid"

    title = opp.get("title", "Untitled")
    agency = opp.get("agency", "Unknown Agency")
    sol = opp.get("solicitationNumber", "N/A")
    url = opp.get("uiLink", "")
    deadline = opp.get("responseDeadLine", "")
    posted = opp.get("postedDate", "")

    profit = opp.get("estimated_profit", {})
    net_profit = profit.get("net_profit", 0)
    revenue = profit.get("revenue", 0)
    gross = profit.get("gross_profit", 0)
    costs = opp.get("estimated_costs", {})
    total_cost = costs.get("total", 0)

    items_key = "products_needed" if is_dme else "services_needed"
    items = opp.get(items_key, [])
    items_str = ", ".join(items[:3]) if items else ""
    items_label = "Products" if is_dme else "Services"

    highlights = opp.get("opportunity_highlights", [])[:3]
    risks = opp.get("risks", [])[:2]
    reason = opp.get("recommendation_reason", "")
    pp_details = opp.get("past_performance_details", "")

    deadline_str = _fmt_deadline(deadline)
    margin_label = "35-40%" if is_dme else "80%"

    lines = [
        f"<div class='card'>",
        f"<div class='card-hdr {card_cls}'>",
        f"<div class='score {score_cls}'>#{rank}</div>",
        f"<span class='score {score_cls}' style='font-size:18px'>{score}/10</span>",
        f"<span class='rec {card_cls}'>{_h(rec)}</span>",
        f"<span class='card-title'>{_h(title)}</span>",
        f"</div>",
        f"<div class='card-body'>",
        f"<div class='row'><b>Agency:</b> {_h(agency)}</div>",
        f"<div class='row'><b>Sol #:</b> {_h(sol)} &nbsp;|&nbsp; <b>Posted:</b> "
        f"{_h(posted[:10] if posted else 'N/A')}</div>",
        f"<div class='row'><b>Deadline:</b> {deadline_str}</div>",
    ]

    if items_str:
        lines.append(f"<div class='row'><b>{items_label}:</b> {_h(items_str)}</div>")

    # Cost / profit line
    if is_dme:
        lines.append(
            f"<div class='row'><b>Est. Cost:</b> ${total_cost:,.0f} &nbsp;|&nbsp; "
            f"<b>Gross:</b> ${gross:,.0f} &nbsp;|&nbsp; "
            f"<b>Your net ({margin_label}):</b> <strong>${net_profit:,.0f}</strong></div>"
        )
    else:
        lines.append(
            f"<div class='row'><b>Revenue:</b> ${revenue:,.0f} &nbsp;|&nbsp; "
            f"<b>Expenses:</b> ${total_cost:,.0f} &nbsp;|&nbsp; "
            f"<b>Your net ({margin_label}):</b> <strong>${net_profit:,.0f}</strong></div>"
        )

    # Highlights + risks
    if highlights or risks:
        lines.append("<div class='highlights'>")
        for h in highlights:
            lines.append(f"<div class='hi'>&#x2713; {_h(h)}</div>")
        for r in risks:
            lines.append(f"<div class='ri'>&#x26A0; {_h(r)}</div>")
        if reason:
            lines.append(
                f"<div style='font-size:12px;color:#374151;margin-top:4px'>"
                f"<em>{_h(reason)}</em></div>"
            )
        lines.append("</div>")

    if pp_details:
        lines.append(
            f"<div class='row' style='font-size:12px;color:#7c3aed'><b>Past perf note:</b> "
            f"{_h(pp_details)}</div>"
        )

    if url:
        lines.append(
            f"<a href='{_h(url)}' class='sam-btn' target='_blank'>"
            f"&#x2192; View on SAM.gov</a>"
        )

    lines.append("</div></div>")
    return "".join(lines)


# ---------------------------------------------------------------------------
# Plain-text email (fallback)
# ---------------------------------------------------------------------------

_LINE = "=" * 72
_THIN = "-" * 48


def _build_plain_email(dme: list[dict], consulting: list[dict]) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d  %H:%M UTC")

    dme_bid = sum(1 for o in dme if o.get("bid_recommendation") == "BID")
    con_bid = sum(1 for o in consulting if o.get("bid_recommendation") == "BID")
    dme_profit = sum(
        o.get("estimated_profit", {}).get("net_profit", 0) for o in dme
        if not o.get("requires_past_performance", True) and o.get("score", 0) >= MIN_SCORE_NO_PP
    )
    con_profit = sum(
        o.get("estimated_profit", {}).get("net_profit", 0) for o in consulting
        if not o.get("requires_past_performance", True) and o.get("score", 0) >= MIN_SCORE_NO_PP
    )

    dme_no_pp = sorted(
        [o for o in dme if not o.get("requires_past_performance", True)
         and o.get("score", 0) >= MIN_SCORE_NO_PP],
        key=lambda x: x.get("score", 0), reverse=True
    )
    dme_pp = sorted(
        [o for o in dme if o.get("requires_past_performance", True)
         and o.get("score", 0) >= MIN_SCORE_NEEDS_PP],
        key=lambda x: x.get("score", 0), reverse=True
    )
    con_no_pp = sorted(
        [o for o in consulting if not o.get("requires_past_performance", True)
         and o.get("score", 0) >= MIN_SCORE_NO_PP],
        key=lambda x: x.get("score", 0), reverse=True
    )
    con_pp = sorted(
        [o for o in consulting if o.get("requires_past_performance", True)
         and o.get("score", 0) >= MIN_SCORE_NEEDS_PP],
        key=lambda x: x.get("score", 0), reverse=True
    )

    sections = [
        _LINE,
        "CONTRACT SCOUT -- DAILY OPPORTUNITY REPORT",
        f"Generated: {generated_at}",
        _LINE,
        f"  DME: {len(dme)} contracts | {dme_bid} BID | Net potential: ${dme_profit:,.0f}",
        f"  Consulting: {len(consulting)} contracts | {con_bid} BID | Net potential: ${con_profit:,.0f}",
        f"  (Showing score >= {MIN_SCORE_NO_PP} only. Full log in opportunities_log.csv)",
        _LINE,
        "",
        "PART 1: DME CONTRACTS (EQUIPMENT RESALE)",
        "Business Model: Product Resale | Est. Net Margin: 35-40%",
        _LINE,
        "",
        _plain_no_pp_section(dme_no_pp, is_dme=True),
        "",
        _plain_needs_pp_section(dme_pp),
        "",
        _LINE,
        "PART 2: CONSULTING CONTRACTS (PROFESSIONAL SERVICES)",
        "Business Model: Solo Work | Est. Net Margin: 80%",
        _LINE,
        "",
        _plain_no_pp_section(con_no_pp, is_dme=False),
        "",
        _plain_needs_pp_section(con_pp),
        "",
        _LINE,
        "Contract Scout | theworkedge.ai",
        _LINE,
    ]
    return "\n".join(sections)


def _plain_no_pp_section(opportunities: list[dict], is_dme: bool) -> str:
    net = sum(o.get("estimated_profit", {}).get("net_profit", 0) for o in opportunities)
    lines = [f"NO PAST PERFORMANCE REQUIRED -- {len(opportunities)} contracts | ${net:,.0f} potential"]
    if not opportunities:
        lines.append(f"  No viable opportunities found today (all scored below {MIN_SCORE_NO_PP}/10).")
        return "\n".join(lines)

    for rank, opp in enumerate(opportunities, start=1):
        lines.append(_plain_card(rank, opp, is_dme))
    return "\n".join(lines)


def _plain_needs_pp_section(opportunities: list[dict]) -> str:
    lines = [f"NEEDS PAST PERFORMANCE -- {len(opportunities)} contracts (monitor for future)"]
    if not opportunities:
        lines.append("  No relevant opportunities requiring past performance today.")
        return "\n".join(lines)

    for opp in opportunities[:MAX_NEEDS_PP_SHOWN]:
        score = opp.get("score", 0)
        title = opp.get("title", "Untitled")[:65]
        url = opp.get("uiLink", "")
        lines.append(f"  Score {score}/10 -- {title}")
        if url:
            lines.append(f"    {url}")

    if len(opportunities) > MAX_NEEDS_PP_SHOWN:
        lines.append(f"  ...and {len(opportunities) - MAX_NEEDS_PP_SHOWN} more (see CSV log)")
    return "\n".join(lines)


def _plain_card(rank: int, opp: dict, is_dme: bool) -> str:
    score = opp.get("score", 0)
    rec = opp.get("bid_recommendation", "NO-BID")
    title = opp.get("title", "Untitled")
    agency = opp.get("agency", "Unknown Agency")
    sol = opp.get("solicitationNumber", "N/A")
    deadline = opp.get("responseDeadLine", "")
    url = opp.get("uiLink", "")

    profit = opp.get("estimated_profit", {})
    net_profit = profit.get("net_profit", 0)
    gross = profit.get("gross_profit", 0)
    costs = opp.get("estimated_costs", {})
    total_cost = costs.get("total", 0)

    items = opp.get("products_needed" if is_dme else "services_needed", [])
    margin = "35-40%" if is_dme else "80%"

    highlights = opp.get("opportunity_highlights", [])[:3]
    risks = opp.get("risks", [])[:2]
    reason = opp.get("recommendation_reason", "")

    days_str = _days_until(deadline)

    lines = [
        "",
        f"  #{rank}  SCORE: {score}/10  [{rec}]",
        f"  {title}",
        f"  Agency: {agency}",
        f"  Sol #: {sol} | Deadline: {deadline[:10] if deadline else 'N/A'}{days_str}",
        f"  Est Cost: ${total_cost:,.0f} | Gross: ${gross:,.0f} | "
        f"Your net ({margin}): ${net_profit:,.0f}",
    ]

    if items:
        lines.append(f"  {'Products' if is_dme else 'Services'}: {', '.join(items[:3])}")
    for h in highlights:
        lines.append(f"    + {h}")
    for r in risks:
        lines.append(f"    ! {r}")
    if reason:
        lines.append(f"  >> {reason}")
    if url:
        lines.append(f"  {url}")
    lines.append(f"  {_THIN}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_deadline(deadline_str: str) -> str:
    """Return formatted deadline with days remaining, e.g. 'Mar 25, 2026 (36 days)'."""
    if not deadline_str or deadline_str == "N/A":
        return "N/A"
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(deadline_str[:19], fmt[:len(deadline_str[:19])])
            days = (dt.date() - datetime.now(timezone.utc).date()).days
            formatted = dt.strftime("%b %d, %Y")
            day_str = f"{days} day{'s' if days != 1 else ''}"
            color = "#dc2626" if days < 7 else "#d97706" if days < 14 else "#059669"
            return f"{formatted} <span style='color:{color};font-weight:bold'>({day_str})</span>"
        except ValueError:
            continue
    return deadline_str[:10] if deadline_str else "N/A"


def _days_until(deadline_str: str) -> str:
    """Return a ' (N days)' string for plain text."""
    if not deadline_str:
        return ""
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(deadline_str[:19], fmt[:len(deadline_str[:19])])
            days = (dt.date() - datetime.now(timezone.utc).date()).days
            return f"  ({days} day{'s' if days != 1 else ''})"
        except ValueError:
            continue
    return ""


# Backward compatibility: keep create_dme_email for legacy use
def create_dme_email(opportunities: list[dict]) -> str:
    """Legacy DME-only email builder. Use create_opportunity_email instead."""
    html, _ = create_opportunity_email(opportunities, [])
    return html
