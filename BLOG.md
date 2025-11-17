# Building a Smart Vietnamese Chatbot for University Admissions: A Technical Deep Dive

Last weekend, I finished building a chatbot for UEH (University of Economics Ho Chi Minh City) that answers student questions about admissions, programs, and campus life. What started as a simple experiment turned into a production system handling real queries in Vietnamese.

Here's what I learned and how you can build something similar.

## The Problem

UEH gets thousands of repetitive questions every admissions season:
- "What are the admission methods for 2025?"
- "How much is the tuition?"
- "What programs do you offer?"

The admission office was drowning in Facebook messages, Zalo chats, and emails asking the same questions over and over. We needed something that could:
1. Answer in Vietnamese (properly, not Google Translate broken)
2. Pull from official university sources
3. Handle follow-up questions like a real conversation
4. Run 24/7 without breaking the bank

## Why Zalo?

In Vietnam, everyone uses Zalo. It's like WhatsApp meets Facebook Messenger. Students don't want to download another app or visit a website - they just want to message the university's Zalo Official Account and get answers.

Zalo provides webhook APIs similar to Telegram or Slack, so integration is straightforward.

## The Stack

After testing a few approaches, here's what worked:

**Frontend**: Zalo Official Account (free)  
**Backend**: Flask on AWS EC2 (t4g.large, ~$49/month)  
**AI Model**: Claude 3.5 Haiku via AWS Bedrock  
**Knowledge Base**: MongoDB Atlas Local in Docker  
**Search**: Hybrid semantic + keyword search  
**Embeddings**: Amazon Titan v2 (1024 dimensions)

Total cost: About $60-70/month including API calls.

## Architecture Overview

The flow is simple:

```
Student sends message on Zalo
    ↓
Zalo webhook hits Flask server
    ↓
Agent decides: search knowledge base or web?
    ↓
For UEH questions: semantic search MongoDB (fast)
For general questions: Google search (fallback)
    ↓
Claude synthesizes answer
    ↓
Response sent back to Zalo
    ↓
Student gets answer in 3-5 seconds
```

## Part 1: Setting Up the Knowledge Base

First problem: where does the bot get its information?

### Web Scraping

I wrote a crawler that hits multiple UEH domains:
- Main site: www.ueh.edu.vn
- Admissions portal: tuyensinh.ueh.edu.vn (most important!)
- Training info: daotao.ueh.edu.vn
- Student portal: student.ueh.edu.vn
- E-learning: lms.ueh.edu.vn

The crawler is dead simple - Beautiful Soup, respecting robots.txt, 1-second delays:

```python
from bs4 import BeautifulSoup
import requests
from pymongo import MongoClient

def crawl_page(url):
    response = requests.get(url, timeout=10)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Extract content
    title = soup.find('h1').get_text() if soup.find('h1') else ''
    content = soup.get_text(separator='\n', strip=True)
    
    # Save to MongoDB
    db.documents.insert_one({
        'url': url,
        'title': title,
        'content': content[:5000],  # Truncate long pages
        'crawled_at': datetime.now()
    })
```

After running overnight, I had 261 documents from official UEH sources.

### The MongoDB Setup

I'm using MongoDB Atlas Local via Docker - it's free and runs on the same EC2 instance:

```bash
# Pull and run MongoDB
docker pull mongodb/mongodb-atlas-local
docker run -d -p 27017:27017 mongodb/mongodb-atlas-local

# Create user
mongosh "mongodb://localhost:27017" << 'EOF'
use admin
db.createUser({
  user: "ueh_app",
  pwd: "YourPasswordHere",
  roles: [{ role: "readWrite", db: "ueh_knowledge_base" }]
})
EOF
```

Connection string:
```
mongodb://ueh_app:YourPassword@localhost:27017/ueh_knowledge_base?directConnection=true&authSource=admin
```

## Part 2: Semantic Search (The Magic Part)

Here's where it gets interesting. Traditional keyword search sucks for conversational queries.

If someone asks "làm sao để vào học UEH?" (how do I get into UEH?) and your database only has "phương thức tuyển sinh" (admission methods), keyword search returns nothing.

### Enter Vector Embeddings

I used AWS Bedrock's Titan Embed Text v2 to convert every document into a 1024-dimensional vector. These vectors capture semantic meaning.

```python
import boto3
import numpy as np

bedrock = boto3.client('bedrock-runtime', region_name='us-west-2')

def generate_embedding(text):
    response = bedrock.invoke_model(
        modelId='amazon.titan-embed-text-v2:0',
        body=json.dumps({
            "inputText": text,
            "dimensions": 1024,
            "normalize": True
        })
    )
    
    result = json.loads(response['body'].read())
    return result['embedding']

# Generate for all documents
for doc in db.documents.find({'embedding': {'$exists': False}}):
    embedding_text = f"{doc['title']} {doc['title']} {doc['content'][:3000]}"
    embedding = generate_embedding(embedding_text)
    
    db.documents.update_one(
        {'_id': doc['_id']},
        {'$set': {'embedding': embedding}}
    )
```

Processing 261 documents took about 60 seconds. Each embedding costs practically nothing (fractions of a cent).

### Hybrid Search

I combine two approaches:

**70% semantic similarity** (understands intent)  
**30% keyword matching** (finds exact terms)

```python
def hybrid_search(query, limit=15):
    # Generate query embedding
    query_embedding = generate_embedding(query)
    
    # Text search (MongoDB full-text)
    text_results = db.documents.find(
        {'$text': {'$search': query}},
        {'score': {'$meta': 'textScore'}}
    ).sort([('score', {'$meta': 'textScore'})])
    
    # Vector search (cosine similarity)
    all_docs = db.documents.find({'embedding': {'$exists': True}})
    vector_results = []
    
    for doc in all_docs:
        similarity = cosine_similarity(query_embedding, doc['embedding'])
        if similarity > 0.3:  # Threshold
            vector_results.append({
                'doc': doc,
                'similarity': similarity
            })
    
    # Combine scores
    combined = {}
    for result in vector_results:
        doc_id = str(result['doc']['_id'])
        combined[doc_id] = {
            'doc': result['doc'],
            'score': result['similarity'] * 0.7  # 70% weight
        }
    
    for result in text_results:
        doc_id = str(result['_id'])
        if doc_id in combined:
            combined[doc_id]['score'] += result['score'] * 0.3  # 30% weight
        else:
            combined[doc_id] = {
                'doc': result,
                'score': result['score'] * 0.3
            }
    
    # Sort by combined score
    sorted_results = sorted(
        combined.values(),
        key=lambda x: x['score'],
        reverse=True
    )
    
    return sorted_results[:limit]
```

This approach works incredibly well. Students can ask in natural language, use different phrasings, or even switch between Vietnamese and English - the bot understands.

## Part 3: The AI Agent

I'm using a tool-calling agent pattern. The agent has access to three tools:

1. **search_ueh_knowledge**: Query the MongoDB knowledge base
2. **google_search_serper**: Search the web (fallback)
3. **extract_web_content**: Grab content from URLs

The agent decides which tools to use based on the query:

```python
from strands import Agent

agent = Agent(
    model="anthropic.claude-3-5-haiku-20241022-v1:0",
    provider="bedrock",
    tools=[
        search_ueh_knowledge,
        google_search_serper,
        extract_web_content
    ],
    system_prompt="""You are a helpful assistant for UEH university.
    
For questions about UEH (admissions, programs, fees, campus), ALWAYS use 
search_ueh_knowledge first. Only use Google for general questions unrelated 
to UEH.

Answer in Vietnamese unless asked in English. Be concise but complete."""
)

# Usage
response = agent.chat("UEH có bao nhiêu phương thức tuyển sinh 2025?")
```

### Why Claude Haiku?

I tested three models:

**Claude 3.5 Sonnet**: Best quality, but slow (10-15s) and expensive  
**Claude 3.5 Haiku**: Good quality, fast (3-5s), cheap  
**Claude 3 Haiku**: Fastest (2s), but lower quality

For a chatbot, response time matters. Students won't wait 15 seconds. Haiku hits the sweet spot - good enough answers, fast enough responses.

## Part 4: The Flask Server

The webhook server is straightforward:

```python
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    
    # Extract message
    message = data['message']['text']
    user_id = data['sender']['id']
    
    # Check guardrails
    if not is_valid_input(message):
        return jsonify({'status': 'blocked'}), 200
    
    # Get response from agent
    response = agent.chat(message)
    
    # Send back to Zalo
    send_zalo_message(user_id, response)
    
    return jsonify({'status': 'ok'}), 200

def send_zalo_message(user_id, text):
    url = f"https://openapi.zalo.me/v3.0/oa/message/cs"
    headers = {
        'access_token': ZALO_ACCESS_TOKEN,
        'Content-Type': 'application/json'
    }
    payload = {
        'recipient': {'user_id': user_id},
        'message': {'text': text}
    }
    requests.post(url, headers=headers, json=payload)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

### Guardrails

I added basic input validation to prevent abuse:

```python
def is_valid_input(message):
    # Length check
    if len(message) < 1 or len(message) > 2000:
        return False
    
    # Prompt injection detection
    blocked_patterns = [
        'ignore previous instructions',
        'bỏ qua hướng dẫn',
        'forget everything',
        'system prompt'
    ]
    
    message_lower = message.lower()
    for pattern in blocked_patterns:
        if pattern in message_lower:
            return False
    
    # Rate limiting (5 messages/minute per user)
    # ... implementation details ...
    
    return True
```

AWS Bedrock also has built-in guardrails for content filtering (hate speech, violence, PII), but I'm not using them yet to save costs.

## Part 5: Performance Optimizations

### Two-Layer Caching

This was a game-changer for costs.

**Layer 1**: Cache MongoDB search results (1 hour TTL)  
**Layer 2**: Cache full agent responses (until restart)

```python
QUERY_CACHE = {}  # Layer 1: tool results
RESPONSE_CACHE = {}  # Layer 2: full responses

def search_ueh_knowledge(query):
    if query in QUERY_CACHE:
        return QUERY_CACHE[query]  # 0.1ms
    
    results = hybrid_search(query)  # 3ms
    QUERY_CACHE[query] = results
    return results

def chat_with_cache(message):
    if message in RESPONSE_CACHE:
        return RESPONSE_CACHE[message]  # 0.001s
    
    response = agent.chat(message)  # 3-9s
    RESPONSE_CACHE[message] = response
    return response
```

**Impact**: If 100 students ask "phương thức tuyển sinh 2025?"
- Without cache: 100 Bedrock calls × $0.01 = $1.00
- With cache: 1 Bedrock call × $0.01 = $0.01

99% cost reduction for repeated queries.

### Content Truncation

I truncate long documents to 2000 characters when passing to the agent. Claude doesn't need the entire page - just the relevant sections. This reduces token costs significantly.

## Part 6: Deployment

### EC2 Setup

I'm running on a t4g.large (ARM-based Graviton):
- 2 vCPUs
- 8 GB RAM
- $0.0672/hour = $49.06/month

Why not Lambda? The agent initialization takes 2-3 seconds (loading models, connecting to MongoDB). With EC2, it stays warm.

### Systemd Service

Auto-start on boot:

```bash
# /etc/systemd/system/zalo-bot.service
[Unit]
Description=Zalo Bot Service
After=network.target docker.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/zalo_bot
Environment="PATH=/usr/bin:/usr/local/bin"
ExecStart=/usr/bin/python3 /opt/zalo_bot/app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable zalo-bot
sudo systemctl start zalo-bot
```

### Monitoring

Simple log tailing for now:
```bash
tail -f /tmp/zalo_bot.log
```

I should set up CloudWatch, but honestly, it's been running fine for weeks without issues.

## Cost Breakdown

Here's what I actually pay per month:

**AWS EC2 (t4g.large)**: $49.06  
**AWS Bedrock (Claude Haiku)**: ~$5-10 (200-400 queries/day)  
**AWS Bedrock (Titan Embeddings)**: <$1 (one-time generation + occasional updates)  
**Google Serper API**: $0 (free tier, rarely used)  
**MongoDB**: $0 (Docker on same EC2)  
**Zalo OA**: $0 (free)

**Total**: $55-60/month

If I get more traffic, costs will scale:
- 1,000 queries/day: ~$70/month
- 5,000 queries/day: ~$120/month
- 10,000 queries/day: ~$200/month

Still way cheaper than hiring a person to answer questions 24/7.

## What It Can Actually Do

Real examples from production:

**Query**: "UEH có bao nhiêu phương thức tuyển sinh 2025?"  
**Response**: "UEH có 5 phương thức tuyển sinh chính năm 2025:
1. Xét tuyển điểm thi THPT
2. Xét tuyển học bạ THPT
3. Xét tuyển kết quả kỳ thi đánh giá năng lực
4. Xét tuyển thẳng và ưu tiên
5. Xét tuyển theo chương trình quốc tế (SAT, A-Level, IB)

Bạn có muốn biết chi tiết về phương thức nào không?"

**Query**: "học phí bao nhiêu"  
**Response**: "Học phí UEH năm học 2024-2025:
- Ngành kinh tế, quản trị: 15.5 - 18 triệu/năm
- Ngành kế toán, tài chính: 16 - 18.5 triệu/năm
- Chương trình tiên tiến: 30 - 35 triệu/năm
- Chương trình quốc tế: 60 - 80 triệu/năm

Đây là mức học phí ước tính. Bạn nên kiểm tra website chính thức để có thông tin cập nhật nhất."

**Query**: "what programs do you offer?" (English)  
**Response**: "UEH offers programs in:
- Economics and Business Administration
- Finance and Banking
- Accounting and Auditing
- International Business
- Marketing and Digital Marketing
- Information Systems
- Tourism and Hospitality Management
- Law and Business Law

We have standard programs, advanced programs, and international programs (taught in English). Which area interests you?"

It handles follow-ups, understands context, and switches languages naturally.

## Challenges I Hit

### 1. Missing the Admissions Portal

Initially, the bot kept saying "I don't know" for admission questions. Turns out I was only crawling www.ueh.edu.vn, but the official admission info lives at **tuyensinh.ueh.edu.vn** (separate subdomain).

Fixed by updating the crawler to hit all UEH portals.

### 2. SSL Certificate Issues

Some UEH subdomains have certificate problems. The crawler would crash with `SSLError: certificate verify failed`.

Quick fix:
```python
response = requests.get(url, verify=False, timeout=10)
```

Not ideal for production, but it works.

### 3. Agent Calling Google Too Much

The agent would sometimes call Google instead of the knowledge base, wasting money and time.

Fix: Stronger system prompt emphasizing "ALWAYS search knowledge base first for UEH questions."

### 4. Vietnamese Tokenization

Vietnamese is tricky. Words like "phương thức tuyển sinh" should be treated as a single term, but standard tokenizers split it.

The semantic search handles this perfectly - it understands the phrase regardless of tokenization.

## What's Next?

Things I want to add:

**Image support**: Students send photos of their transcripts, bot analyzes eligibility  
**Voice messages**: Zalo supports audio, could transcribe and respond  
**Multi-turn conversations**: Remember context across messages  
**Analytics dashboard**: Track popular questions, response times  
**A/B testing**: Compare different prompts and models  

But honestly, the current version works well enough. Students get answers in seconds, and the admission office is happy.

## Lessons Learned

1. **Semantic search is worth it**: The embedding generation took an hour to set up but made the bot 10x smarter.

2. **Cache everything**: Response caching reduced costs by 99% for repeated queries.

3. **Start simple**: I almost built a complex RAG pipeline with Pinecone, LangChain, etc. MongoDB + NumPy works fine for 261 documents.

4. **Vietnamese is hard**: Make sure your model actually supports Vietnamese well. Claude handles it great, but I tested some open-source models that produced garbage.

5. **Response time > Quality**: Students prefer a good answer in 3 seconds over a perfect answer in 15 seconds.

6. **Guardrails matter**: Added input validation after getting spammed with "ignore previous instructions" messages.

## Should You Build This?

If you're in Vietnam and dealing with repetitive customer questions, absolutely yes.

The setup takes a weekend if you're comfortable with Python, AWS, and Docker. Ongoing maintenance is minimal - I spend maybe an hour per month updating the knowledge base.

For universities, businesses with FAQs, or government services, this pattern works great:
- Crawl your official sources
- Generate embeddings
- Set up the agent
- Deploy and forget

The technology is mature enough now that you don't need a PhD to build this. Just follow the steps above.

## Code Repository

Full code is on GitHub: [github.com/David-GAPV/ZaloBot](https://github.com/David-GAPV/ZaloBot)

Includes:
- Flask webhook server
- MongoDB knowledge base with vector search
- Web crawler for UEH sites
- Embedding generation script
- Systemd service files
- Deployment scripts

Feel free to fork and adapt for your use case.

---

**Questions?** Open an issue on GitHub or email me at the university. Happy to help others build similar systems.

**P.S.** If you're a UEH student reading this and wondering why the bot sometimes responds slowly - now you know it's because I'm cheaping out on the EC2 instance. Sorry, budget constraints. 😅
