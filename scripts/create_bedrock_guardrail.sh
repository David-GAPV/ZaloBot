#!/bin/bash
# AWS Bedrock Guardrail Creation Script for Zalo Bot
# This script creates a guardrail using AWS CLI

set -e

echo "════════════════════════════════════════════════════════════"
echo "🛡️ Creating AWS Bedrock Guardrail for Zalo Bot"
echo "════════════════════════════════════════════════════════════"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Please install it first:"
    echo "   https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    exit 1
fi

# Get AWS profile from .env or use default
AWS_PROFILE=${AWS_PROFILE:-david_gapv}
AWS_REGION=${AWS_REGION:-us-west-2}

echo "📋 Using AWS Profile: $AWS_PROFILE"
echo "📍 Region: $AWS_REGION"
echo ""

# Create guardrail configuration
GUARDRAIL_NAME="zalo-bot-uit-guardrail"
GUARDRAIL_DESCRIPTION="Hybrid guardrails for UIT Zalo chatbot - content filtering, PII detection, topic blocking"

echo "Creating guardrail: $GUARDRAIL_NAME"
echo ""

# Create the guardrail using AWS CLI
aws bedrock create-guardrail \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    --name "$GUARDRAIL_NAME" \
    --description "$GUARDRAIL_DESCRIPTION" \
    --blocked-input-messaging "⚠️ Tin nhắn của bạn vi phạm chính sách sử dụng. Vui lòng hỏi về UIT một cách lịch sự." \
    --blocked-outputs-messaging "⚠️ Tôi không thể trả lời câu hỏi này. Vui lòng hỏi về thông tin UIT." \
    --content-policy-config '{
        "filtersConfig": [
            {
                "type": "HATE",
                "inputStrength": "MEDIUM",
                "outputStrength": "MEDIUM"
            },
            {
                "type": "VIOLENCE",
                "inputStrength": "MEDIUM",
                "outputStrength": "MEDIUM"
            },
            {
                "type": "SEXUAL",
                "inputStrength": "HIGH",
                "outputStrength": "HIGH"
            },
            {
                "type": "MISCONDUCT",
                "inputStrength": "MEDIUM",
                "outputStrength": "MEDIUM"
            }
        ]
    }' \
    --sensitive-information-policy-config '{
        "piiEntitiesConfig": [
            {"type": "EMAIL", "action": "ANONYMIZE"},
            {"type": "PHONE", "action": "ANONYMIZE"},
            {"type": "NAME", "action": "BLOCK"},
            {"type": "ADDRESS", "action": "ANONYMIZE"},
            {"type": "CREDIT_DEBIT_CARD_NUMBER", "action": "BLOCK"},
            {"type": "US_SOCIAL_SECURITY_NUMBER", "action": "BLOCK"}
        ]
    }' \
    --word-policy-config '{
        "wordsConfig": [
            {"text": "hack"},
            {"text": "cheat"},
            {"text": "fraud"},
            {"text": "scam"},
            {"text": "lừa đảo"},
            {"text": "gian lận"}
        ],
        "managedWordListsConfig": [
            {"type": "PROFANITY"}
        ]
    }' \
    --topic-policy-config '{
        "topicsConfig": [
            {
                "name": "financial-advice",
                "definition": "Providing financial, investment, or money advice",
                "examples": ["Should I invest in stocks?", "How to make money fast?"],
                "type": "DENY"
            },
            {
                "name": "medical-advice",
                "definition": "Providing medical diagnosis or health treatment advice",
                "examples": ["What medicine should I take?", "Do I have cancer?"],
                "type": "DENY"
            },
            {
                "name": "legal-advice",
                "definition": "Providing legal counsel or representation",
                "examples": ["Can I sue them?", "What are my legal rights?"],
                "type": "DENY"
            }
        ]
    }' \
    --output json > /tmp/guardrail_output.json

# Extract guardrail ID and version
GUARDRAIL_ID=$(cat /tmp/guardrail_output.json | grep -o '"guardrailId": "[^"]*' | cut -d'"' -f4)
GUARDRAIL_VERSION=$(cat /tmp/guardrail_output.json | grep -o '"version": "[^"]*' | cut -d'"' -f4)

echo ""
echo "════════════════════════════════════════════════════════════"
echo "✅ Guardrail Created Successfully!"
echo "════════════════════════════════════════════════════════════"
echo "Guardrail ID: $GUARDRAIL_ID"
echo "Version: $GUARDRAIL_VERSION"
echo ""
echo "📝 Add this to your .env file:"
echo ""
echo "BEDROCK_GUARDRAIL_ID=$GUARDRAIL_ID"
echo "BEDROCK_GUARDRAIL_VERSION=$GUARDRAIL_VERSION"
echo ""
echo "════════════════════════════════════════════════════════════"
echo ""
echo "🔄 Next steps:"
echo "1. Add BEDROCK_GUARDRAIL_ID to .env file"
echo "2. Restart the Zalo bot service: ./restart.sh"
echo "3. Test with a message to verify guardrails are working"
echo ""
echo "💰 Cost estimate:"
echo "   - ~$0.0001 per guardrail unit (input + output)"
echo "   - For 7,500 messages/month: ~$0.75/month"
echo ""
echo "📊 To view your guardrail in AWS Console:"
echo "https://console.aws.amazon.com/bedrock/home?region=$AWS_REGION#/guardrails"
echo ""
