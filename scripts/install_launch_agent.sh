#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LAUNCH_DIR="$HOME/Library/LaunchAgents"
BOT_PLIST="$LAUNCH_DIR/com.hennei.darchivebot.telegram.plist"
PROCESS_PLIST="$LAUNCH_DIR/com.hennei.darchivebot.processor.plist"
DIGEST_PLIST="$LAUNCH_DIR/com.hennei.darchivebot.digest.plist"
DIGEST_PROJECT_SEED_PLIST="$LAUNCH_DIR/com.hennei.darchivebot.digest.project-seed.plist"
DIGEST_WEEKLY_PLIST="$LAUNCH_DIR/com.hennei.darchivebot.digest.weekly.plist"

mkdir -p "$LAUNCH_DIR" "$ROOT/.local/logs"

cat > "$BOT_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.hennei.darchivebot.telegram</string>
  <key>ProgramArguments</key>
  <array>
    <string>$ROOT/.venv/bin/darchive</string>
    <string>telegram</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$ROOT</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$ROOT/.local/logs/telegram.launchd.out</string>
  <key>StandardErrorPath</key>
  <string>$ROOT/.local/logs/telegram.launchd.err</string>
</dict>
</plist>
PLIST

cat > "$PROCESS_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.hennei.darchivebot.processor</string>
  <key>ProgramArguments</key>
  <array>
    <string>$ROOT/.venv/bin/darchive</string>
    <string>process</string>
    <string>--export-graph</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$ROOT</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>StartInterval</key>
  <integer>300</integer>
  <key>StandardOutPath</key>
  <string>$ROOT/.local/logs/processor.launchd.out</string>
  <key>StandardErrorPath</key>
  <string>$ROOT/.local/logs/processor.launchd.err</string>
</dict>
</plist>
PLIST

cat > "$DIGEST_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.hennei.darchivebot.digest</string>
  <key>ProgramArguments</key>
  <array>
    <string>$ROOT/.venv/bin/darchive</string>
    <string>telegram-digest</string>
    <string>--kind</string>
    <string>revisit</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$ROOT</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>9</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>$ROOT/.local/logs/digest.launchd.out</string>
  <key>StandardErrorPath</key>
  <string>$ROOT/.local/logs/digest.launchd.err</string>
</dict>
</plist>
PLIST

cat > "$DIGEST_PROJECT_SEED_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.hennei.darchivebot.digest.project-seed</string>
  <key>ProgramArguments</key>
  <array>
    <string>$ROOT/.venv/bin/darchive</string>
    <string>telegram-digest</string>
    <string>--kind</string>
    <string>project-seed</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$ROOT</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>18</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>$ROOT/.local/logs/digest-project-seed.launchd.out</string>
  <key>StandardErrorPath</key>
  <string>$ROOT/.local/logs/digest-project-seed.launchd.err</string>
</dict>
</plist>
PLIST

cat > "$DIGEST_WEEKLY_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.hennei.darchivebot.digest.weekly</string>
  <key>ProgramArguments</key>
  <array>
    <string>$ROOT/.venv/bin/darchive</string>
    <string>telegram-digest</string>
    <string>--kind</string>
    <string>weekly</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$ROOT</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>9</integer>
    <key>Minute</key>
    <integer>30</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>$ROOT/.local/logs/digest-weekly.launchd.out</string>
  <key>StandardErrorPath</key>
  <string>$ROOT/.local/logs/digest-weekly.launchd.err</string>
</dict>
</plist>
PLIST

launchctl unload "$BOT_PLIST" 2>/dev/null || true
launchctl unload "$PROCESS_PLIST" 2>/dev/null || true
launchctl unload "$DIGEST_PLIST" 2>/dev/null || true
launchctl unload "$DIGEST_PROJECT_SEED_PLIST" 2>/dev/null || true
launchctl unload "$DIGEST_WEEKLY_PLIST" 2>/dev/null || true
launchctl load "$BOT_PLIST"
launchctl load "$PROCESS_PLIST"
launchctl load "$DIGEST_PLIST"
launchctl load "$DIGEST_PROJECT_SEED_PLIST"
launchctl load "$DIGEST_WEEKLY_PLIST"
echo "installed $BOT_PLIST"
echo "installed $PROCESS_PLIST"
echo "installed $DIGEST_PLIST"
echo "installed $DIGEST_PROJECT_SEED_PLIST"
echo "installed $DIGEST_WEEKLY_PLIST"
