#!/bin/sh
# PDFX AI bot watchdog: restarts the bot if it's not running.
# Intended to be invoked periodically by a cron job.
cd /root/.openclaw/workspace/pdfx-ai || exit 1

if ! pgrep -f "pdfx-ai/bot.py" > /dev/null 2>&1; then
  echo "$(date -Iseconds) watchdog: bot not running, starting it" >> watchdog.log
  nohup ./run_bot.sh >> bot.log 2>&1 &
fi
