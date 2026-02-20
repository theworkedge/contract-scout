#!/bin/bash
# run_daily.sh — Helper script for Contract Scout daily automation.
# Loads .env variables and runs contract_scout.py with full logging.
# Can be run manually to test: bash run_daily.sh

set -euo pipefail

SCRIPT_DIR="/Users/dperez7390/Library/CloudStorage/Dropbox/Mac (2)/Documents/Local Code Repository/contract-scout"
ENV_FILE="$SCRIPT_DIR/.env"
LOG_FILE="$HOME/Library/Logs/contract_scout.log"

cd "$SCRIPT_DIR"

echo "----------------------------------------" >> "$LOG_FILE"
echo "Run started: $(date)" >> "$LOG_FILE"

# Load .env — skip blank lines and comments
if [ -f "$ENV_FILE" ]; then
    while IFS= read -r line; do
        # Skip blank lines and comment lines
        [[ -z "$line" || "$line" == \#* ]] && continue
        export "$line"
    done < "$ENV_FILE"
else
    echo "ERROR: .env file not found at $ENV_FILE" >> "$LOG_FILE"
    exit 1
fi

/usr/bin/python3 "$SCRIPT_DIR/contract_scout.py"

echo "Run finished: $(date)" >> "$LOG_FILE"
