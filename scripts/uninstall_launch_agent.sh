#!/usr/bin/env bash
set -euo pipefail

LAUNCH_DIR="$HOME/Library/LaunchAgents"
BOT_PLIST="$LAUNCH_DIR/com.hennei.dalife.telegram.plist"
PROCESS_PLIST="$LAUNCH_DIR/com.hennei.dalife.processor.plist"
DIGEST_PLIST="$LAUNCH_DIR/com.hennei.dalife.digest.plist"
DIGEST_PROJECT_SEED_PLIST="$LAUNCH_DIR/com.hennei.dalife.digest.project-seed.plist"
DIGEST_WEEKLY_PLIST="$LAUNCH_DIR/com.hennei.dalife.digest.weekly.plist"

launchctl unload "$BOT_PLIST" 2>/dev/null || true
launchctl unload "$PROCESS_PLIST" 2>/dev/null || true
launchctl unload "$DIGEST_PLIST" 2>/dev/null || true
launchctl unload "$DIGEST_PROJECT_SEED_PLIST" 2>/dev/null || true
launchctl unload "$DIGEST_WEEKLY_PLIST" 2>/dev/null || true
rm -f "$BOT_PLIST" "$PROCESS_PLIST" "$DIGEST_PLIST" "$DIGEST_PROJECT_SEED_PLIST" "$DIGEST_WEEKLY_PLIST"
echo "uninstalled dalife launch agents"
