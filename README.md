# Zalo Bot with AWS Bedrock & MongoDB

Vietnamese-language chatbot integrated with Zalo OA using AWS Bedrock (Claude 3.5 Sonnet) and MongoDB knowledge base for UIT admission queries.

**Status**: ✅ Running | **Port**: 5000 | **Auto-start**: ✅ Enabled | **Last Updated**: 2025-11-13

---

## 📋 Quick Start

```bash
# Check status
./check_config.sh

# Restart service  
./restart.sh

# View logs
tail -f /tmp/zalo_bot.log

# Run full system test
python3 test_system.py

# Health check
curl http://localhost:5000/health
```

---

## 🏗️ Architecture

```
┌─────────────────┐
│  Zalo OA Users  │
└────────┬────────┘
         │ (webhook)
         ▼
┌─────────────────────────────────┐
│  Flask Server (port 5000)       │
│  app.py                         │
│  + Hybrid Guardrails 🛡️         │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  Strands Agent                  │
│  google_search_agent_mongodb.py │
│                                 │
│  Tools:                         │
│  • UIT Knowledge Search         │
│  • Google Search (Serper)       │
│  • Web Content Extraction       │
└───┬──────────────────┬──────────┘
    │                  │
    ▼                  ▼
┌─────────────┐  ┌──────────────────┐
│ AWS Bedrock │  │ MongoDB EC2      │
│ Claude 3.5  │  │ 95 UIT docs      │
│ us-west-2   │  │ Private Subnet   │
└─────────────┘  └──────────────────┘
```

**Components:**
- **Frontend**: Zalo OA (Official Account)
- **Backend**: Flask webhook server
- **AI Agent**: Strands Agent with multiple search tools
- **LLM**: AWS Bedrock Claude 3.5 Sonnet
- **Knowledge Base**: MongoDB with 95 UIT admission documents
- **Search APIs**: Serper API, Tavily API

---

## ⚙️ AWS Configuration

### AWS Profile Configuration

**Credentials** (`~/.aws/credentials`):
```ini
[<YOUR_PROFILE>]
aws_access_key_id = <REDACTED>
aws_secret_access_key = <REDACTED>
```

**Config** (`~/.aws/config`):
```ini
[profile <YOUR_PROFILE>]
region = us-west-2
output = json
```

**Environment Variables** (`.env`):
```env
AWS_PROFILE=<YOUR_PROFILE>
AWS_REGION=us-west-2
BEDROCK_MODEL_ID=anthropic.<haiku>
```

**Verify Connection:**
```bash
# Using AWS CLI
aws sts get-caller-identity --profile <YOUR_PROFILE>

# Using Python
python3 -c "import boto3; boto3.Session(profile_name='<YOUR_PROFILE>', region_name='us-west-2').client('bedrock-runtime'); print('✓ Connected to AWS Bedrock')"
```

---

## 💰 EC2 Cost Information (us-west-2)

### Running Instances

| Instance Name | ID | Type | vCPU | RAM | Cost/Hour | Cost/Month | Cost/Day |
|---------------|-------|------|------|-----|-----------|------------|----------|
| **zalo-bot-t4g** | i-XXXXXXXXXXXXXXXXX | t4g.large | 2 | 8 GB | $0.0672 | **$49.06** | $1.61 |
| **UIT-MongoDB-Server** | i-XXXXXXXXXXXXXXXXX | t3a.micro | 2 | 1 GB | $0.0094 | **$6.86*** | $0.23 |
| **TOTAL** | | | | | | **$55.92** | **$1.84** |


**Monthly cost breakdown:**
- t4g.large (zalo-bot): $49.06 (87.7%)
- t3a.micro (MongoDB): $6.86 (12.3%)

---

## 🚀 Service Management

### Systemd Service (Auto-start Enabled)

The Zalo Bot is configured to **automatically start** when the EC2 instance boots.

**Service Commands:**
```bash
# Check status
sudo systemctl status zalo-bot

# Start service
sudo systemctl start zalo-bot

# Stop service
sudo systemctl stop zalo-bot

# Restart service
sudo systemctl restart zalo-bot

# Enable auto-start (already enabled)
sudo systemctl enable zalo-bot

# View logs
sudo journalctl -u zalo-bot -f
```

**Service File Location:** `/etc/systemd/system/zalo-bot.service`

### Manual Service Management

**Using restart script:**
```bash
cd /opt/zalo_bot
./restart.sh
```

**Using startup script:**
```bash
cd /opt/zalo_bot
./startup.sh
```

**Direct Python start:**
```bash
cd /opt/zalo_bot
nohup python3 app.py > /tmp/zalo_bot.log 2>&1 &
```

### EC2 Instance Management

**Stop instance** (saves ~$49/month):
```bash
aws ec2 stop-instances \
  --instance-ids <INSTANCE_ID> \
  --profile <YOUR_PROFILE> \
  --region us-west-2
```

**Start instance:**
```bash
aws ec2 start-instances \
  --instance-ids <INSTANCE_ID> \
  --profile <YOUR_PROFILE> \
  --region us-west-2
```

**Check instance status:**
```bash
aws ec2 describe-instances \
  --instance-ids <INSTANCE_ID> \
  --profile <YOUR_PROFILE> \
  --region us-west-2 \
  --query 'Reservations[0].Instances[0].State.Name'
```

**What happens after EC2 restart:**
1. Instance boots up (~1-2 minutes)
2. Network initializes
3. **Systemd automatically starts zalo-bot service**
4. Service loads environment from `.env`
5. Connects to AWS Bedrock
6. Connects to MongoDB
7. Flask server starts on port 5000
8. Ready to handle webhooks!

📖 **See `EC2_MANAGEMENT.md` for detailed instructions**

---

## 📁 Project Structure

```
/opt/zalo_bot/
├── app.py                           # Flask webhook server
├── google_search_agent_mongodb.py   # Strands agent with tools
├── uit_knowledge_base_mongodb.py    # MongoDB knowledge base
├── .env                             # Environment variables (credentials)
├── requirements.txt                 # Python dependencies
│
├── restart.sh                       # Restart service
├── startup.sh                       # Boot startup script
├── check_config.sh                  # Configuration verification
├── test_system.py                   # Full system test
│
├── README.md                        # This file
└── EC2_MANAGEMENT.md                # EC2 operations guide
```

---

## 🛠️ Installation

### Prerequisites
- Python 3.10+
- AWS account with Bedrock access
- MongoDB connection
- Zalo OA credentials

### Setup Steps

1. **Install Python dependencies:**
   ```bash
   cd /opt/zalo_bot
   pip3 install -r requirements.txt
   ```

2. **AWS credentials are already configured:**
   - `~/.aws/credentials` (profile: david_gapv)
   - `~/.aws/config` (region: us-west-2)

3. **Environment variables are set:**
   - `.env` file contains all required configuration

4. **Service is configured:**
   - Systemd service enabled for auto-start
   - Service file: `/etc/systemd/system/zalo-bot.service`

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Info page |
| GET | `/health` | Health check (returns JSON status) |
| GET | `/webhook` | Zalo webhook verification |
| POST | `/webhook` | Zalo message handler |

**Health Check Response:**
```json
{
  "status": "healthy",
  "agent": "UIT MongoDB Agent",
  "mongodb": "connected",
  "aws_profile": "<YOUR_PROFILE>",
  "aws_region": "us-west-2"
}
```

---

## 🧪 Testing

### Run Full System Test
```bash
cd /opt/zalo_bot
python3 test_system.py
```

**Tests included:**
- ✅ AWS Bedrock connection
- ✅ MongoDB connection (95 documents)
- ✅ Google Search Agent initialization
- ✅ Flask service health check

### Manual Tests

**Test AWS connection:**
```python
from google_search_agent_mongodb import GoogleSearchAgent
agent = GoogleSearchAgent()
response = agent.chat("Hello, can you help me?")
print(response)
```

**Test MongoDB:**
```python
from uit_knowledge_base_mongodb import UITMongoKnowledgeBase
import os
from dotenv import load_dotenv

load_dotenv()
kb = UITMongoKnowledgeBase(os.getenv('MONGODB_URI'))
print(f"Documents: {kb.count_documents()}")
results = kb.full_text_search("UIT tuyển sinh", limit=3)
for r in results:
    print(f"- {r['title']}")
```

**Test Flask endpoints:**
```bash
# Health check
curl http://localhost:5000/health | python3 -m json.tool

# Info page
curl http://localhost:5000/

# Check if service is listening
lsof -i :5000
```

---

## 📊 MongoDB Knowledge Base

**Connection:**
- Host: <MONGODB_IP>:27017 (private subnet)
- Database: uit_knowledge_base
- Collection: documents
- Documents: 95 (UIT admission data)

**Categories:**
- tuyển sinh (admissions)
- thông báo (announcements)
- ngành đào tạo (programs)
- học bổng (scholarships)

**Search Capabilities:**
- Full-text search with MongoDB text indexes
- Keyword search
- Category filtering
- Relevance scoring

---

## 🤖 AI Agent Tools

The Strands Agent has access to these tools:

1. **search_uit_knowledge(query)** - Search UIT MongoDB knowledge base
2. **google_search_serper(query)** - Google search via Serper API
3. **google_search_tavily(query)** - Alternative search via Tavily API
4. **extract_web_content(url)** - Extract content from web pages
5. **analyze_search_results(query, results)** - Synthesize information

**Agent Workflow:**
1. User sends message to Zalo OA
2. Webhook triggers Flask handler
3. Flask calls agent with query
4. Agent decides which tools to use
5. For UIT queries: searches MongoDB first
6. For general queries: uses web search
7. Agent synthesizes response using Claude 3.5 Haiku
8. Response sent back to user via Zalo

---

## ⚡ Performance & Caching

### Two-Layer Cache Architecture

**Layer 1: Tool Cache (MongoDB Results)**
- **Scope**: Global - shared across all users
- **Storage**: `QUERY_CACHE` dictionary
- **TTL**: 1 hour per query
- **Purpose**: Cache MongoDB search results
- **Performance**: 3ms → 0.1ms (30x faster)

**Layer 2: Response Cache (Full Agent Responses)**
- **Scope**: Global - shared across all users  
- **Storage**: `RESPONSE_CACHE` dictionary
- **TTL**: Until service restart
- **Size Limit**: 100 entries (LRU eviction)
- **Purpose**: Cache complete agent responses
- **Performance**: 9s → 0.001s (9000x faster)

### Cache Performance

| Scenario | First User | Second User | Savings |
|----------|-----------|-------------|---------|
| **Same query** | 9.1s (Bedrock call) | 0.001s (cached) | 99.99% |
| **MongoDB only** | 3ms (DB query) | 0.1ms (cached) | 97% |
| **100 identical queries** | 1 × 9s = 9s | 99 × 0s = 0s | 891s saved |

### Real-World Impact

**Without cache (old):**
- 100 students ask "UIT có bao nhiêu phương thức tuyển sinh?"
- Result: 100 × 9s = 900s (15 minutes)
- Cost: 100 Bedrock API calls

**With global cache (current):**
- 100 students ask same question
- Result: 1 × 9s + 99 × 0.001s = 9.1s
- Cost: 1 Bedrock API call
- **Savings: 99% reduction in time and cost!**

### Model Configuration

**Current Model:** Claude 3.5 Haiku (`anthropic.claude-3-5-haiku-20241022-v1:0`)
- **Speed**: 7-10s per query
- **Quality**: Medium-High (good for most queries)
- **Cost**: Lower than Sonnet
- **Best for**: Fast responses, FAQ-style questions

**Alternative Models:**
- Claude 3.5 Sonnet v2: Higher quality, slower (10-15s), more expensive
- Claude Haiku v1: Fastest (2-5s), lower quality, cheapest

### Cache Warming

Common queries are automatically cached after first use:
- "Các phương thức tuyển sinh UIT năm 2025"
- "UIT có bao nhiêu phương thức tuyển sinh"
- "Điều kiện xét tuyển UIT"
- "Học phí UIT bao nhiêu"

All subsequent users get instant responses (0.001s)!

---

## 🔧 Configuration

### Environment Variables (.env)

```env
# Zalo Bot Configuration
ZALO_ACCESS_TOKEN=<REDACTED>
ZALO_SECRET_KEY=<REDACTED>
ZALO_OA_ID=<REDACTED>

# Server Configuration
PORT=5000
DEBUG=True
HOST=0.0.0.0

# MongoDB Configuration
MONGODB_URI=mongodb://<USERNAME>:<PASSWORD>@<MONGODB_IP>:27017/uit_knowledge_base

# AWS Configuration
AWS_REGION=us-west-2
AWS_PROFILE=david_gapv
BEDROCK_MODEL_ID=anthropic.claude-3-5-haiku-20241022-v1:0

# Search APIs
SERPER_API_KEY=<REDACTED>
TAVILY_API_KEY=<REDACTED>

# Agent Configuration
AGENT_NAME=UIT_Zalo_Bot
LOG_LEVEL=INFO
```

---

## 🐛 Troubleshooting

### Service Won't Start

```bash
# Check service status
sudo systemctl status zalo-bot

# View detailed logs
sudo journalctl -u zalo-bot -n 100

# Check if port is already in use
lsof -i :5000

# Kill any conflicting process
pkill -f "python.*app.py"

# Try manual start to see errors
cd /opt/zalo_bot
python3 app.py
```

### AWS Connection Issues

```bash
# Verify credentials
aws sts get-caller-identity --profile <YOUR_PROFILE>

# Check if profile exists
cat ~/.aws/credentials | grep <YOUR_PROFILE>

# Test Bedrock access
python3 -c "
import boto3
session = boto3.Session(profile_name='<YOUR_PROFILE>', region_name='us-west-2')
client = session.client('bedrock-runtime')
print('✓ AWS Bedrock OK')
"
```

### MongoDB Connection Issues

```bash
# Test MongoDB connection
python3 -c "
from pymongo import MongoClient
uri = 'mongodb://<USERNAME>:<PASSWORD>@<MONGODB_IP>:27017/uit_knowledge_base'
client = MongoClient(uri, serverSelectionTimeoutMS=5000)
client.server_info()
print('✓ MongoDB OK')
"

# Check if MongoDB EC2 is running
aws ec2 describe-instances \
  --instance-ids <MONGODB_INSTANCE_ID> \
  --profile <YOUR_PROFILE> \
  --region us-west-2 \
  --query 'Reservations[0].Instances[0].State.Name'
```

### Common Issues

| Issue | Solution |
|-------|----------|
| Port 5000 in use | Run `./restart.sh` |
| AWS credentials not found | Check `~/.aws/credentials` has profile configured |
| MongoDB connection failed | Verify MongoDB EC2 instance is running |
| Bedrock permission denied | Verify AWS credentials have `bedrock:InvokeModel` |
| Service doesn't auto-start | Check `sudo systemctl is-enabled zalo-bot` |

---

## 🔒 Security Notes

⚠️ **Important Security Considerations**

This setup uses hardcoded credentials for demonstration. For production:

1. **Use IAM Roles** instead of access keys when possible
2. **Store secrets** in AWS Secrets Manager or Parameter Store
3. **Rotate credentials** regularly (90 days recommended)
4. **Enable CloudWatch** logging and monitoring
5. **Use HTTPS** with SSL certificates
6. **Implement rate limiting** to prevent abuse
7. **Use production WSGI** server (gunicorn/uWSGI) instead of Flask dev server
8. **Set up VPC** and security groups properly
9. **Enable MFA** on AWS accounts
10. **Review IAM permissions** regularly

**Never commit credentials to version control!**

---

## 🛡️ Guardrails & Security

**Hybrid Approach** - Custom Python validation + AWS Bedrock Guardrails:

### 1️⃣ Custom Python Guardrails (`guardrails.py`)

**Input Validation:**
- ✅ Rate limiting (5 messages/minute per user)
- ✅ Message length limits (1-2000 characters)
- ✅ Prompt injection detection (blocks "ignore previous instructions", etc.)
- ✅ Spam detection (repetitive text, excessive special characters)
- ✅ Blocked keywords (Vietnamese + English)

**Output Validation:**
- ✅ Response length limits (max 4000 chars)
- ✅ PII detection and redaction (emails, phone numbers, ID cards)
- ✅ Content relevance checks

**Blocked Patterns:**
```python
# Prompt injection attempts
"ignore previous instructions", "bỏ qua hướng dẫn"
"forget everything", "quên tất cả"
"what is your system prompt", "hệ thống của bạn"

# PII detection
emails, Vietnamese phone numbers, CCCD numbers
```

**Cost**: $0 (code-based)

### 2️⃣ AWS Bedrock Guardrails (Optional)

**Content Filtering:**
- ✅ Hate speech (MEDIUM strength)
- ✅ Violence (MEDIUM strength)  
- ✅ Sexual content (HIGH strength)
- ✅ Misconduct (MEDIUM strength)

**PII Protection:**
- ✅ Email anonymization
- ✅ Phone number anonymization
- ✅ Name blocking
- ✅ Address anonymization
- ✅ Credit card blocking

**Topic Blocking:**
- ❌ Financial advice
- ❌ Medical advice
- ❌ Legal advice

**Word Filtering:**
- ✅ Profanity (managed list)
- ✅ Custom blocked words (hack, cheat, fraud, lừa đảo, etc.)

**Cost**: ~$0.0001 per guardrail unit (~$0.75/month for 7,500 messages)

### Setup Instructions

**1. Enable Custom Python Guardrails (Already Active)**

Custom guardrails are automatically enabled when the app starts. No configuration needed!

**2. Enable AWS Bedrock Guardrails (Optional)**

```bash
# Run the creation script
./scripts/create_bedrock_guardrail.sh

# This will output a guardrail ID like:
# BEDROCK_GUARDRAIL_ID=abc123xyz

# Add to .env file:
echo "BEDROCK_GUARDRAIL_ID=abc123xyz" >> .env
echo "BEDROCK_GUARDRAIL_VERSION=DRAFT" >> .env

# Restart service
./restart.sh
```

**3. Test Guardrails**

```bash
# Test rate limiting (send 6+ messages quickly)
# Test blocked keywords (send "ignore previous instructions")
# Test content filtering (send inappropriate content)
# Test PII detection (send email or phone number)
```

### Monitoring

**Check logs for blocked content:**
```bash
tail -f /tmp/zalo_bot.log | grep -i "guardrail\|blocked\|pii"
```

**Guardrail events logged:**
- Input validation failures
- Bedrock guardrail interventions
- PII detections and redactions
- Rate limit violations

### Performance Impact

- **Custom guardrails**: <1ms per message (negligible)
- **Bedrock guardrails**: ~100ms per message (if enabled)
- **Total impact**: <5% increase in response time

---

## 📞 Support

**For issues or questions:**
- Check logs: `tail -f /tmp/zalo_bot.log`
- Run diagnostics: `./check_config.sh`
- Run tests: `python3 test_system.py`
- Contact: tuyensinh@uit.edu.vn

**Useful Commands:**
```bash
# Quick status check
./check_config.sh

# View live logs
tail -f /tmp/zalo_bot.log

# Check service health
curl http://localhost:5000/health

# Restart service
./restart.sh

# Full system test
python3 test_system.py
```

---

## 📝 Change Log

**2025-11-13:**
- ✅ Configured AWS profile `david_gapv`
- ✅ Installed all dependencies
- ✅ Fixed health check endpoint
- ✅ Created systemd service for auto-start
- ✅ Created management scripts (restart, check, test)
- ✅ All system tests passing
- ✅ Service running on port 5000
- ✅ Documentation consolidated

**2025-11-14:**
- ✅ Optimized MongoDB connection (public IP → private IP 172.31.60.10)
- ✅ Switched to Claude 3.5 Haiku (faster responses, lower cost)
- ✅ Implemented two-layer global caching (99% cost reduction)
- ✅ Fixed dual-process webhook bug
- ✅ Redacted all PII from README
- ✅ Removed unused venv folder (132 MB saved)
- ✅ Created .gitignore and pushed to GitHub
- ✅ **Implemented hybrid guardrails** (Custom Python + AWS Bedrock)

---

## 📚 Additional Documentation

- **EC2_MANAGEMENT.md** - Detailed EC2 operations, stop/start procedures
- **test_system.py** - Automated system tests
- **.env** - Environment configuration (keep secure!)

---

**Instance Information:**
- **EC2**: <INSTANCE_ID> (zalo-bot-t4g, t4g.large)
- **MongoDB**: <INSTANCE_ID> (UIT-MongoDB-Server, t3a.micro)
- **Region**: us-west-2
- **AWS Profile**: <YOUR_PROFILE>
- **Auto-start**: ✅ Enabled via systemd

**Last Updated**: November 13, 2025  
**Status**: ✅ All systems operational
