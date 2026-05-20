#!/usr/bin/env bash
# Launch Scholar via the Reachy Mini Conversation App
#
# Usage:
#   ./launch_scholar.sh              # headless (robot mic/speaker)
#   ./launch_scholar.sh --gradio     # with Gradio UI (testing)
#
# Prerequisites:
#   1. reachy_mini_conversation_app cloned and installed (uv sync)
#   2. .env file in the conversation app directory (copy from fleet-gateway/reachy/.env.example)
#   3. nats-py installed in the conversation app venv (pip install nats-py)
#   4. Jarvis running on GB10: uv run jarvis serve-nats
#   5. Reachy Mini on the network (or --sim for simulation)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FLEET_GATEWAY_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONV_APP_DIR="${CONV_APP_DIR:-$FLEET_GATEWAY_ROOT/../reachy_mini_conversation_app}"

# fleet-gateway must be on PYTHONPATH so external tools can import common/
export PYTHONPATH="${FLEET_GATEWAY_ROOT}:${PYTHONPATH:-}"

# Activate the conversation app venv
if [ -f "$CONV_APP_DIR/.venv/bin/activate" ]; then
    source "$CONV_APP_DIR/.venv/bin/activate"
else
    echo "ERROR: No venv found at $CONV_APP_DIR/.venv"
    echo "Run: cd $CONV_APP_DIR && uv sync"
    exit 1
fi

# Check .env exists
if [ ! -f "$CONV_APP_DIR/.env" ]; then
    echo "WARNING: No .env file in $CONV_APP_DIR"
    echo "Copy from: $FLEET_GATEWAY_ROOT/reachy/.env.example"
    echo "  cp $FLEET_GATEWAY_ROOT/reachy/.env.example $CONV_APP_DIR/.env"
    echo "Then edit NATS_URL with your password."
    exit 1
fi

cd "$CONV_APP_DIR"

echo "=== Scholar Launch ==="
echo "  Fleet Gateway: $FLEET_GATEWAY_ROOT"
echo "  Conv App:      $CONV_APP_DIR"
echo "  PYTHONPATH:    $PYTHONPATH"
echo "  Args:          $*"
echo "======================"

python -c "from reachy_mini_conversation_app.main import main; main()" -- "$@"
