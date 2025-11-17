"""
Zalo Bot Webhook Handler for UEH (University of Economics Ho Chi Minh City) Knowledge Base Agent
Integrates with MongoDB-powered agent for Vietnamese queries
"""

import os
import sys
from flask import Flask, request, jsonify
import hashlib
import hmac
import json
from dotenv import load_dotenv

# Add parent directory to path to import agent
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from google_search_agent_mongodb import GoogleSearchAgent
from guardrails import validator, init_bedrock_guardrails, bedrock_guardrails
import structlog

# Load environment variables
load_dotenv()

# Setup logging
log = structlog.get_logger()

app = Flask(__name__)

# Initialize UEH agent
agent = GoogleSearchAgent()
print("UEH MongoDB Agent initialized for Zalo Bot")

# Initialize guardrails (hybrid: custom Python + AWS Bedrock)
guardrail_id = os.getenv('BEDROCK_GUARDRAIL_ID')
init_bedrock_guardrails(guardrail_id)
if guardrail_id:
    print(f"Hybrid Guardrails enabled (Custom Python + AWS Bedrock {guardrail_id})")
else:
    print("Custom Python Guardrails enabled (AWS Bedrock disabled - set BEDROCK_GUARDRAIL_ID to enable)")

# Zalo webhook configuration
ZALO_SECRET = os.getenv('ZALO_SECRET_KEY', '')
ZALO_ACCESS_TOKEN = os.getenv('ZALO_ACCESS_TOKEN', '')

def verify_zalo_signature(secret_token: str) -> bool:
    """
    Verify webhook secret token from Zalo Bot API
    Zalo sends the secret_token in X-Secret-Token header
    """
    if not ZALO_SECRET:
        print("Warning: ZALO_SECRET not configured, skipping verification")
        return True  # Skip verification in dev mode
    
    # For Zalo Bot API (zapps.me), verify the secret token directly
    return secret_token == ZALO_SECRET


@app.route('/webhook', methods=['GET'])
def webhook_verify():
    """
    Webhook verification endpoint for Zalo
    Zalo will send a GET request to verify the webhook URL
    """
    # Get verification parameters
    mode = request.args.get('mode')
    token = request.args.get('token')
    challenge = request.args.get('challenge')
    
    # Verify token matches
    if mode == 'subscribe' and token == ZALO_ACCESS_TOKEN:
        print(f"Webhook verified: {challenge}")
        return challenge, 200
    else:
        print("Webhook verification failed")
        return 'Forbidden', 403


@app.route('/webhook', methods=['POST'])
def webhook_handler():
    """
    Main webhook handler for incoming Zalo messages
    """
    try:
        # Log received headers for debugging
        print(f"📥 Headers: {dict(request.headers)}")
        
        # Get secret token from header (Zalo Bot API sends this as X-Bot-Api-Secret-Token)
        secret_token = request.headers.get('X-Bot-Api-Secret-Token', '')
        
        # Verify secret token
        if not verify_zalo_signature(secret_token):
            print(f"Invalid signature. Received token: '{secret_token}' Expected: '{ZALO_SECRET}'")
            return jsonify({'error': 'Invalid signature'}), 403
        
        print(f"Secret token verified")
        
        # Parse JSON payload
        payload = request.get_json()
        print(f"📨 Received webhook: {json.dumps(payload, indent=2)}")
        
        # Handle different event types
        event_name = payload.get('event_name')
        
        if event_name == 'message.text.received' or event_name == 'user_send_text':
            return handle_text_message(payload)
        elif event_name == 'message.image.received' or event_name == 'user_send_image':
            return handle_image_message(payload)
        elif event_name == 'message.link.received' or event_name == 'user_send_link':
            return handle_link_message(payload)
        else:
            print(f"Unhandled event type: {event_name}")
            return jsonify({'status': 'ok'}), 200
            
    except Exception as e:
        print(f"Error handling webhook: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def handle_text_message(payload):
    """
    Handle text messages from users
    Query the UEH agent and send response back
    """
    user_id = None
    try:
        # Extract message details
        print(f"Processing payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        # Handle both old and new payload formats
        message = payload.get('message', {})
        
        # Get user_id from either 'from' (new format) or 'sender' (old format)
        from_user = message.get('from', {})
        sender = payload.get('sender', {})
        user_id = from_user.get('id') or sender.get('id')
        
        # Get chat_id as fallback
        chat = message.get('chat', {})
        if not user_id:
            user_id = chat.get('id')
        
        text = message.get('text', '')
        
        print(f"👤 User {user_id}: {text}")
        
        # Check if empty message
        if not text.strip():
            print(f"Empty message, returning OK")
            return jsonify({'status': 'ok'}), 200
        
        # 1. Validate input with custom Python guardrails
        is_valid, error_msg = validator.validate_input(user_id, text)
        if not is_valid:
            log.warning("Input validation failed", user_id=user_id, reason=error_msg)
            send_zalo_message(user_id, error_msg)
            return jsonify({'status': 'ok', 'guardrail': 'input_blocked'}), 200
        
        # 2. Apply AWS Bedrock Guardrails (if enabled)
        if bedrock_guardrails and bedrock_guardrails.enabled:
            is_safe, filtered_msg, intervention = bedrock_guardrails.apply_guardrails(
                agent.bedrock_client,
                agent.model_id,
                text
            )
            if not is_safe:
                log.warning("Bedrock guardrails blocked", user_id=user_id, intervention=intervention)
                send_zalo_message(user_id, filtered_msg)
                return jsonify({'status': 'ok', 'guardrail': 'bedrock_blocked'}), 200
        
        # Query the agent
        print(f"Querying agent with: {text}")
        response = agent.chat(text)
        
        print(f"Agent response ({len(response)} chars): {response[:200]}...")
        
        # 3. Validate output before sending
        is_valid, cleaned_response = validator.validate_output(response)
        if not is_valid:
            log.warning("Output validation failed", user_id=user_id)
        
        # 4. Check for PII in response (log for monitoring)
        pii_detected = validator.detect_pii(cleaned_response)
        if pii_detected:
            log.warning("PII detected and redacted in response", user_id=user_id, pii_types=pii_detected)
        
        # Send response back to Zalo
        print(f"📤 Sending response to user {user_id} (validated)")
        send_zalo_message(user_id, cleaned_response)
        
        print(f"✅ Message handled successfully")
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        print(f"Error handling text message: {e}")
        import traceback
        traceback.print_exc()
        # Send error message to user
        try:
            if user_id:
                error_msg = "Xin lỗi, tôi gặp lỗi khi xử lý tin nhắn của bạn. Vui lòng thử lại sau."
                send_zalo_message(user_id, error_msg)
        except Exception as e2:
            print(f"Failed to send error message: {e2}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


def handle_image_message(payload):
    """
    Handle image messages - respond that we only support text
    """
    message = payload.get('message', {})
    from_user = message.get('from', {})
    sender = payload.get('sender', {})
    user_id = from_user.get('id') or sender.get('id')
    if not user_id:
        chat = message.get('chat', {})
        user_id = chat.get('id')
    
    response = "Xin lỗi, hiện tại tôi chỉ hỗ trợ trả lời câu hỏi bằng văn bản. Vui lòng gửi câu hỏi của bạn dưới dạng text."
    send_zalo_message(user_id, response)
    
    return jsonify({'status': 'ok'}), 200


def handle_link_message(payload):
    """
    Handle link messages - respond that we only support text
    """
    message = payload.get('message', {})
    from_user = message.get('from', {})
    sender = payload.get('sender', {})
    user_id = from_user.get('id') or sender.get('id')
    if not user_id:
        chat = message.get('chat', {})
        user_id = chat.get('id')
    
    response = "Xin lỗi, hiện tại tôi chỉ hỗ trợ trả lời câu hỏi bằng văn bản. Vui lòng mô tả câu hỏi của bạn."
    send_zalo_message(user_id, response)
    
    return jsonify({'status': 'ok'}), 200


def send_zalo_message(user_id: str, message: str):
    """
    Send message back to Zalo user via Bot API (zapps.me)
    """
    import requests
    
    # Zalo Bot API endpoint for sending messages
    bot_token = ZALO_ACCESS_TOKEN  # Format: bot<bot_id>:<access_token>
    url = f"https://bot-api.zapps.me/{bot_token}/sendMessage"
    
    headers = {
        'Content-Type': 'application/json'
    }
    
    # Split long messages into chunks (Zalo has character limit)
    max_length = 2000
    if len(message) > max_length:
        chunks = [message[i:i+max_length] for i in range(0, len(message), max_length)]
    else:
        chunks = [message]
    
    # Send each chunk
    for i, chunk in enumerate(chunks):
        if len(chunks) > 1:
            chunk = f"[{i+1}/{len(chunks)}]\n{chunk}"
        
        payload = {
            "chat_id": user_id,
            "text": chunk
        }
        
        try:
            print(f"📤 Sending to {url}: {payload}")
            response = requests.post(url, headers=headers, json=payload)
            print(f"📥 Response: {response.status_code} - {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    print(f"Sent message to user {user_id}")
                else:
                    print(f"API returned ok=false: {result}")
            else:
                print(f"Failed to send message: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Error sending message: {e}")
            import traceback
            traceback.print_exc()


@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint
    """
    # Check if agent is initialized
    mongodb_status = 'connected' if agent else 'disconnected'
    
    return jsonify({
        'status': 'healthy',
        'agent': 'UEH MongoDB Agent',
        'mongodb': mongodb_status,
        'aws_profile': os.getenv('AWS_PROFILE', 'default'),
        'aws_region': os.getenv('AWS_REGION', 'us-west-2')
    }), 200


@app.route('/', methods=['GET'])
def index():
    """
    Root endpoint - info page
    """
    return """
    <html>
    <head><title>UEH Zalo Bot</title></head>
    <body>
        <h1>UEH Knowledge Base - Zalo Bot</h1>
        <p>Webhook server is running!</p>
        <ul>
            <li><b>Agent:</b> MongoDB-powered UEH information assistant</li>
            <li><b>Language:</b> Vietnamese</li>
            <li><b>Database:</b> UEH university information</li>
        </ul>
        <h3>Endpoints:</h3>
        <ul>
            <li><code>GET /</code> - This page</li>
            <li><code>GET /health</code> - Health check</li>
            <li><code>GET /webhook</code> - Webhook verification</li>
            <li><code>POST /webhook</code> - Message handler</li>
        </ul>
    </body>
    </html>
    """


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'False').lower() == 'true'
    
    print("\n" + "=" * 60)
    print("UEH Zalo Bot - Starting")
    print("=" * 60)
    print(f"Port: {port}")
    print(f"Debug: {debug}")
    print(f"MongoDB: {'Connected' if agent else 'Not connected'}")
    print("=" * 60 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
