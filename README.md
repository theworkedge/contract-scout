# Contract Scout

Automated government contract opportunity finder. Searches SAM.gov for recent solicitations, scores them with Claude AI, emails the top matches, and logs everything to CSV.

## How it works

1. **Search** — Queries the SAM.gov Opportunities API for solicitations posted in the last 2 days matching target NAICS codes (541611, 541990, 611430, 541519, 541720).
2. **Analyze** — Sends the results to Claude (Sonnet) which scores each opportunity 1–10 based on fit criteria (deliverables-based work, value range, deadline, relevant keywords).
3. **Email** — Sends an HTML report of opportunities scoring 7+ via Gmail SMTP.
4. **Log** — Appends all scored opportunities to `opportunities_log.csv` for tracking.

## Setup

### Prerequisites

- Python 3.10+
- A [SAM.gov API key](https://sam.gov/content/entity-registration)
- An [Anthropic API key](https://console.anthropic.com/)
- A Gmail account with an [App Password](https://myaccount.google.com/apppasswords) (for email delivery)

### Install

```bash
git clone https://github.com/<your-org>/contract-scout.git
cd contract-scout
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configure

Copy the example env file and fill in your keys:

```bash
cp .env.example .env
```

Edit `.env` with your values:

| Variable | Description |
|---|---|
| `SAM_API_KEY` | SAM.gov API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `GMAIL_ADDRESS` | Gmail address for sending reports |
| `GMAIL_APP_PASSWORD` | Gmail App Password (not your regular password) |
| `RECIPIENT_EMAIL` | Where to send the report |
| `RECIPIENT_NAME` | Name used in the greeting |

## Usage

```bash
python contract_scout.py
```

The script will:
- Search SAM.gov for recent solicitations
- Score each one with Claude AI
- Email you opportunities scoring 7+
- Log all results to `opportunities_log.csv`

### Automate with cron

Run daily at 7 AM:

```
0 7 * * * cd /path/to/contract-scout && .venv/bin/python contract_scout.py
```

## Output

### Email

An HTML-formatted report with:
- Opportunity title, agency, solicitation number
- Score (1–10) with reasoning
- Key requirements summary
- Direct link to SAM.gov listing

### CSV log

`opportunities_log.csv` columns:

| Column | Description |
|---|---|
| `date_found` | Date the opportunity was found |
| `title` | Opportunity title |
| `solicitation_id` | SAM.gov solicitation number |
| `naics` | NAICS code |
| `agency` | Issuing agency |
| `estimated_value` | Estimated contract value (when available) |
| `deadline` | Response deadline |
| `score` | Claude's fit score (1–10) |
| `reasoning` | Why Claude assigned that score |
| `sam_url` | Direct link to SAM.gov |
| `status` | Tracking status |

## Scoring criteria

**Positive signals (increase score):**
- Deliverables-based work (consulting, training, research, assessments)
- Contract value $75K–$250K
- Response deadline 10+ days away
- Keywords: process improvement, Agile, consulting, assessment, recommendations

**Negative signals (decrease score):**
- Staff augmentation / body-shop contracts
- Full-time on-site requirements
- Security clearance requirements
- Value outside the $75K–$250K sweet spot
