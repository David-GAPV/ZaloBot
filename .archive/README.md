# Zalo Bot with AWS Bedrock & MongoDB

A Vietnamese-language chatbot integrated with Zalo OA (Official Account) using AWS Bedrock's Claude 3.5 Sonnet model and MongoDB knowledge base.

## Architecture

- **Frontend**: Zalo OA (Official Account)
- **Backend**: Flask webhook server
- **AI Agent**: Strands Agent with AWS Bedrock (Claude 3.5 Sonnet)
- **Knowledge Base**: MongoDB on EC2 instance (UIT admission data)
- **Search APIs**: Serper API, Tavily API

## AWS Configuration

### Credentials
The project uses the AWS profile `david_gapv` with the following configuration:

**Location**: `~/.aws/credentials`
```ini
[david_gapv]
aws_access_key_id = 
aws_secret_access_key = 
```

**Location**: `~/.aws/config`
```ini
[profile david_gapv]
region = us-west-2
output = json
```

### Environment Variables
The `.env` file specifies:
- `AWS_PROFILE=david_gapv`
- `AWS_REGION=us-west-2`
- `BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0`

## Project Structure

```
/opt/zalo_bot/
├── app.py                              # Flask webhook server
├── google_search_agent_mongodb.py      # Strands Agent with tools
├── uit_knowledge_base_mongodb.py       # MongoDB knowledge base
├── .env                                # Environment variables
├── requirements.txt                    # Python dependencies
├── restart.sh                          # Service restart script
└── check_config.sh                     # Configuration checker
```

## Key Components

### 1. Flask Webhook Server (`app.py`)
- Handles Zalo webhook events
- Processes incoming messages
- Routes queries to the AI agent
- Sends responses back to users

### 2. Google Search Agent (`google_search_agent_mongodb.py`)
Strands Agent with multiple tools:
- `search_uit_knowledge()` - Search UIT MongoDB knowledge base
- `google_search_serper()` - Google search via Serper API
- `google_search_tavily()` - Alternative search via Tavily API
- `extract_web_content()` - Extract webpage content
- `analyze_search_results()` - Analyze and synthesize information

### 3. MongoDB Knowledge Base (`uit_knowledge_base_mongodb.py`)
- Connection to MongoDB EC2 instance
- Full-text search capabilities
- UIT admission data (95 documents)
- Categories: tuyển sinh, thông báo, ngành đào tạo, học bổng

## Installation

### Prerequisites
- Python 3.10+
- AWS credentials with Bedrock access
- MongoDB connection string
- Zalo OA access token

### Setup
```bash
# Install dependencies
cd /opt/zalo_bot
pip3 install -r requirements.txt

# Configure AWS credentials (already done)
# Files created: ~/.aws/credentials, ~/.aws/config

# Update .env file with your credentials
# (already configured with david_gapv profile)
```

## Running the Bot

### Start the Service
```bash
./restart.sh
```

### Check Configuration
```bash
./check_config.sh
```

### View Logs
```bash
tail -f /tmp/zalo_bot.log
```

### Stop the Service
```bash
pkill -f "python.*app.py"
```

## Service Status

The bot is currently running:
- **Port**: 5000
- **Host**: 0.0.0.0 (all interfaces)
- **Public URL**: http://172.31.29.81:5000
- **Webhook**: POST /webhook
- **Health**: GET /health

## Testing

### Health Check
```bash
curl http://localhost:5000/health
```

### Test Agent
```python
from google_search_agent_mongodb import GoogleSearchAgent

agent = GoogleSearchAgent()
response = agent.chat("UIT có bao nhiêu phương thức tuyển sinh năm 2025?")
print(response)
```

## Endpoints

- `GET /` - Info page
- `GET /health` - Health check
- `GET /webhook` - Webhook verification (Zalo)
- `POST /webhook` - Message handler (Zalo)

## Environment Variables

```env
# Zalo Bot Configuration
ZALO_ACCESS_TOKEN=bot<bot_id>:<access_token>
ZALO_SECRET_KEY=<secret>
ZALO_OA_ID=<oa_id>

# Server Configuration
PORT=5000
DEBUG=True
HOST=0.0.0.0

# MongoDB Configuration
MONGODB_URI=mongodb://uit_app:UitApp2025!@44.250.166.116:27017/uit_knowledge_base

# AWS Configuration
AWS_REGION=us-west-2
AWS_PROFILE=david_gapv
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0

# Search APIs
SERPER_API_KEY=<key>
TAVILY_API_KEY=<key>
```

## Troubleshooting

### Check AWS Connection
```python
python3 -c "
import boto3
from dotenv import load_dotenv
import os

load_dotenv()
session = boto3.Session(
    profile_name=os.getenv('AWS_PROFILE'),
    region_name=os.getenv('AWS_REGION')
)
bedrock = session.client('bedrock-runtime')
print('✓ Connected to AWS Bedrock')
print(f'✓ Region: {bedrock.meta.region_name}')
"
```

### Check MongoDB Connection
```python
python3 -c "
from uit_knowledge_base_mongodb import UITMongoKnowledgeBase
import os

kb = UITMongoKnowledgeBase(mongodb_uri=os.getenv('MONGODB_URI'))
print(f'✓ Connected to MongoDB')
print(f'✓ Total documents: {kb.count_documents()}')
"
```

### Common Issues

1. **Port 5000 already in use**
   - Run `./restart.sh` to kill and restart

2. **AWS credentials not found**
   - Check `~/.aws/credentials` has `[david_gapv]` section
   - Verify `.env` has `AWS_PROFILE=david_gapv`

3. **MongoDB connection failed**
   - Check EC2 instance is running: 44.250.166.116
   - Verify security group allows port 27017

4. **Bedrock access denied**
   - Verify AWS credentials have bedrock:InvokeModel permission
   - Check model ID is correct

## Security Notes

⚠️ **Important**: The credentials in this README are for demonstration purposes. In production:
- Use AWS Secrets Manager or Parameter Store
- Rotate credentials regularly
- Use IAM roles instead of access keys when possible
- Don't commit credentials to version control

## Support

For issues or questions:
- Check logs: `tail -f /tmp/zalo_bot.log`
- Run config check: `./check_config.sh`
- Contact: tuyensinh@uit.edu.vn

---

**Last Updated**: November 13, 2025
**Status**: ✓ Running on port 5000 with AWS profile `david_gapv`
