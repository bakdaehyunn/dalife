#!/usr/bin/env bash
set -euo pipefail

LAUNCH_DIR="$HOME/Library/LaunchAgents"
BOT_PLIST="$LAUNCH_DIR/com.hennei.dalife.telegram.plist"
PROCESS_PLIST="$LAUNCH_DIR/com.hennei.dalife.processor.plist"
FOOD_PLIST="$LAUNCH_DIR/com.hennei.dalife.food-collect.plist"
LIFE_PLIST="$LAUNCH_DIR/com.hennei.dalife.life-send.plist"
FOOD_FOLLOWUPS_PLIST="$LAUNCH_DIR/com.hennei.dalife.food-followups.plist"
DIGEST_PLIST="$LAUNCH_DIR/com.hennei.dalife.digest.plist"
DIGEST_PROJECT_SEED_PLIST="$LAUNCH_DIR/com.hennei.dalife.digest.project-seed.plist"
DIGEST_WEEKLY_PLIST="$LAUNCH_DIR/com.hennei.dalife.digest.weekly.plist"

launchctl unload "$BOT_PLIST" 2>/dev/null || true
launchctl unload "$PROCESS_PLIST" 2>/dev/null || true
launchctl unload "$FOOD_PLIST" 2>/dev/null || true
launchctl unload "$LIFE_PLIST" 2>/dev/null || true
launchctl unload "$FOOD_FOLLOWUPS_PLIST" 2>/dev/null || true
launchctl unload "$DIGEST_PLIST" 2>/dev/null || true
launchctl unload "$DIGEST_PROJECT_SEED_PLIST" 2>/dev/null || true
launchctl unload "$DIGEST_WEEKLY_PLIST" 2>/dev/null || true
rm -f "$BOT_PLIST" "$PROCESS_PLIST" "$FOOD_PLIST" "$LIFE_PLIST" "$FOOD_FOLLOWUPS_PLIST" \
  "$DIGEST_PLIST" "$DIGEST_PROJECT_SEED_PLIST" "$DIGEST_WEEKLY_PLIST"
echo "uninstalled dalife launch agents"
