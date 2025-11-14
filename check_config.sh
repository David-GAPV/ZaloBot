#!/bin/bash
# Check Zalo Bot Configuration

echo "=================================="
echo "Zalo Bot Configuration Check"
echo "=================================="
echo ""

echo "1. AWS Credentials:"
echo "   Profile: david_gapv"
if grep -q "david_gapv" ~/.aws/credentials; then
    echo "   ✓ Profile exists in ~/.aws/credentials"
    echo "   Access Key: $(grep -A1 "\[david_gapv\]" ~/.aws/credentials | grep aws_access_key_id | cut -d'=' -f2 | xargs | cut -c1-8)..."
else
    echo "   ✗ Profile not found"
fi

echo ""
echo "2. Environment Variables (.env):"
echo "   AWS_PROFILE: $(grep AWS_PROFILE /opt/zalo_bot/.env | cut -d'=' -f2)"
echo "   AWS_REGION: $(grep AWS_REGION /opt/zalo_bot/.env | cut -d'=' -f2)"
echo "   BEDROCK_MODEL: $(grep BEDROCK_MODEL_ID /opt/zalo_bot/.env | cut -d'=' -f2)"

echo ""
echo "3. MongoDB Connection:"
MONGO_URI=$(grep MONGODB_URI /opt/zalo_bot/.env | cut -d'=' -f2)
echo "   URI: ${MONGO_URI:0:30}..."

echo ""
echo "4. Service Status:"
if lsof -i :5000 > /dev/null 2>&1; then
    echo "   ✓ Zalo Bot is running on port 5000"
    PID=$(lsof -ti :5000)
    echo "   Process ID: $PID"
else
    echo "   ✗ Zalo Bot is not running"
fi

echo ""
echo "5. Recent Logs (last 10 lines):"
echo "-----------------------------------"
tail -n 10 /tmp/zalo_bot.log 2>/dev/null || echo "   No logs found"

echo ""
echo "=================================="
echo "Configuration check complete!"
echo "=================================="
