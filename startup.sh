#!/bin/bash
# Auto-start script for Zalo Bot service
# Run this after EC2 instance starts

echo "Starting Zalo Bot service..."

# Wait for network to be fully ready
sleep 5

# Change to project directory
cd /opt/zalo_bot

# Start the service
nohup python3 app.py > /tmp/zalo_bot.log 2>&1 &

# Wait a moment for service to start
sleep 3

# Check if running
if lsof -i :5000 > /dev/null 2>&1; then
    echo "✓ Zalo Bot started successfully on port 5000"
else
    echo "✗ Failed to start Zalo Bot"
    exit 1
fi

