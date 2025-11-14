#!/bin/bash
# Quick Status Check for Zalo Bot

echo "╔════════════════════════════════════════════════════════════╗"
echo "║          ZALO BOT STATUS - AWS Profile: david_gapv         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Service Status
if lsof -i :5000 > /dev/null 2>&1; then
    echo "✓ Service: RUNNING on port 5000"
    PID=$(lsof -ti :5000 | head -1)
    echo "  PID: $PID"
else
    echo "✗ Service: NOT RUNNING"
fi

# AWS Profile
echo ""
echo "✓ AWS Profile: david_gapv"
echo "  Region: us-west-2"
echo "  Model: Claude 3.5 Sonnet"

# MongoDB
echo ""
echo "✓ MongoDB: 44.250.166.116:27017"
echo "  Database: uit_knowledge_base"

# Quick Test
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Quick Commands:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "• Restart:     ./restart.sh"
echo "• Test:        python3 test_system.py"
echo "• Logs:        tail -f /tmp/zalo_bot.log"
echo "• Health:      curl http://localhost:5000/health"
echo "• This status: ./status.sh"
echo ""
