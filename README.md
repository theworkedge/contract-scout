# Contract Scout

Automated government contract opportunity finder. Searches SAM.gov daily for solicitations matching your consulting firm's capabilities, scores them with Claude AI, and emails you a digest of the best matches.

## What It Does

1. **Searches SAM.gov** for recent solicitations across target NAICS codes (management consulting, training, digital transformation, etc.)
2. **Analyzes each opportunity with Claude AI** and scores them 1–10 based on fit (deliverables-based work, small business set-asides, reasonable deadlines, etc.)
3. **Emails an HTML digest** of opportunities scoring 7+ with scores, summaries, key requirements, and direct links to SAM.gov
4. **Logs everything to CSV** for tracking and historical analysis

## Prerequisites

- **Python 3.10+**
- **SAM.gov API key** — register at <https://sam.gov/content/entity-registration> and request an API key under "System Account"
- **Anthropic API key** — sign up at <https://console.anthropic.com/>
- **Gmail App Password** — generate one at <https://myaccount.google.com/apppasswords> (requires 2FA enabled on your Google account)

## Installation

```bash
git clone https://github.com/your-username/contract-scout.git
cd contract-scout
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your values:

| Variable | Description |
|---|---|
| `SAM_API_KEY` | Your SAM.gov API key |
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `GMAIL_ADDRESS` | Gmail address to send from |
| `GMAIL_APP_PASSWORD` | Gmail App Password (not your regular password) |
| `RECIPIENT_EMAIL` | Email address to receive the digest |
| `RECIPIENT_NAME` | Recipient's name |

## Usage

Run manually:

```bash
python contract_scout.py
```

The script will print progress to the console and:
- Save matching opportunities to `opportunities_log.csv`
- Email you if any opportunities score 7+

## Scheduling Daily Runs

### Mac / Linux (cron)

Open your crontab:

```bash
crontab -e
```

Add a line to run daily at 7:00 AM:

```
0 7 * * * cd /path/to/contract-scout && /path/to/.venv/bin/python contract_scout.py >> scout.log 2>&1
```

Replace `/path/to/` with the actual paths on your system.

### Windows (Task Scheduler)

1. Open **Task Scheduler** and click **Create Basic Task**
2. Set the trigger to **Daily** at your preferred time
3. Set the action to **Start a Program**:
   - Program: `C:\path\to\.venv\Scripts\python.exe`
   - Arguments: `contract_scout.py`
   - Start in: `C:\path\to\contract-scout`
4. Save and enable the task

## Project Structure

```
contract-scout/
  contract_scout.py    # Main script
  requirements.txt     # Python dependencies
  .env.example         # Environment variable template
  .env                 # Your credentials (git-ignored)
  opportunities_log.csv # Running log of scored opportunities (git-ignored)
```
