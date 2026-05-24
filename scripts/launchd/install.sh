#!/usr/bin/env zsh
# Install the WhaleIndex orchestrator as a macOS launchd daily job.
#
# Usage:
#   scripts/launchd/install.sh           # interactive, prompts for hour + AUM
#   scripts/launchd/install.sh --hour 9 --aum 0.5
#   scripts/launchd/install.sh --uninstall
#   scripts/launchd/install.sh --status
#
# What it does:
#   - Expands the template into ~/Library/LaunchAgents/com.whaleindex.orchestrator.plist
#   - launchctl bootstrap-loads it (macOS 10.10+) into the user's GUI session
#   - Future automatic runs happen daily at the configured local-time hour
#
# Idempotent: re-running --install with different values overwrites the
# existing plist + reloads.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${0:A}")/../.." && pwd)"
TEMPLATE="$REPO_ROOT/scripts/launchd/com.whaleindex.orchestrator.plist.template"
DEST_DIR="$HOME/Library/LaunchAgents"
DEST="$DEST_DIR/com.whaleindex.orchestrator.plist"
LABEL="com.whaleindex.orchestrator"

mode="install"
hour=""
aum=""

while (( $# > 0 )); do
  case "$1" in
    --uninstall) mode="uninstall" ;;
    --status)    mode="status" ;;
    --hour)      hour="$2"; shift ;;
    --aum)       aum="$2"; shift ;;
    -h|--help)
      sed -n '/^# Usage:/,/^# Idempotent/p' "$0"
      exit 0
      ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
  shift
done

case "$mode" in
  status)
    if [[ ! -f "$DEST" ]]; then
      echo "not installed (no plist at $DEST)"
      exit 0
    fi
    echo "plist: $DEST"
    grep -E "Hour|AUM_USDC|StartCalendarInterval" "$DEST" | sed 's/^/  /'
    echo
    launchctl print "gui/$(id -u)/$LABEL" 2>/dev/null \
      | grep -E "state|last exit|run interval" | sed 's/^/  /' \
      || echo "  (not loaded — run install)"
    exit 0
    ;;

  uninstall)
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    rm -f "$DEST"
    echo "uninstalled: $DEST removed, agent unloaded"
    exit 0
    ;;
esac

# --- install path ---

if [[ -z "$hour" ]]; then
  read -r "hour?wakeup hour (0-23, local time) [default 9]: " || true
  hour=${hour:-9}
fi
if [[ -z "$aum" ]]; then
  read -r "AUM in USDC for each daily rebalance (decimal) [default 0.5]: " || true
  aum=${aum:-0.5}
fi
if ! [[ "$hour" =~ ^[0-9]+$ ]] || (( hour < 0 || hour > 23 )); then
  echo "hour must be an integer 0-23" >&2; exit 2
fi
if ! [[ "$aum" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
  echo "aum must be a decimal number (e.g. 0.5)" >&2; exit 2
fi

mkdir -p "$DEST_DIR"
mkdir -p "$REPO_ROOT/data"

# Expand the template.
sed \
  -e "s|@REPO_ROOT@|$REPO_ROOT|g" \
  -e "s|@HOME@|$HOME|g" \
  -e "s|@WAKEUP_HOUR@|$hour|g" \
  -e "s|@AUM_USDC@|$aum|g" \
  "$TEMPLATE" > "$DEST"

# Unload any previous version, then load this one.
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$DEST"

echo "installed: $DEST"
echo "  scheduled: every day at $hour:00 local time"
echo "  AUM per run: $aum USDC"
echo
echo "next steps:"
echo "  scripts/launchd/install.sh --status     # check the agent state"
echo "  tail -f $REPO_ROOT/data/orchestrator.log"
echo "  scripts/launchd/install.sh --uninstall  # remove"
