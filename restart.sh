#!/bin/bash
# Restart Zalo Bot Service

echo "Stopping existing Flask app..."
pkill -f "python.*app.py" || echo "No existing process found"

# Wait for processes to fully terminate
sleep 3

# Double check port is free
while lsof -i :5000 > /dev/null 2>&1; do
    echo "Waiting for port 5000 to be free..."
    sleep 1
done

echo "Starting Zalo Bot..."
cd /opt/zalo_bot
nohup python3 app.py > /tmp/zalo_bot.log 2>&1 &

# Wait for service to start
sleep 5

echo "Checking if app is running..."
if lsof -i :5000 > /dev/null 2>&1; then
    echo "✓ Zalo Bot is running on port 5000"
    echo "✓ Log file: /tmp/zalo_bot.log"
    echo ""
    echo "Recent logs:"
    tail -n 20 /tmp/zalo_bot.log
else
    echo "✗ Failed to start Zalo Bot"
    echo "Check logs: tail -f /tmp/zalo_bot.log"
fi
