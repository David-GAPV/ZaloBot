# Guardrails Quick Reference

## 🛡️ Hybrid Guardrails System

**Status**: ✅ Custom Python Guardrails ACTIVE | ⚙️ AWS Bedrock Guardrails OPTIONAL

---

## Current Protection (Active Now)

### Custom Python Guardrails ✅

**Input Protection:**
```
✓ Rate limiting: 5 messages/minute per user
✓ Length limits: 1-2000 characters
✓ Prompt injection blocking (15+ patterns)
✓ Spam detection (repetition + special chars)
✓ Blocked keywords (Vietnamese + English)
```

**Output Protection:**
```
✓ Response length limits (max 4000 chars)
✓ PII redaction (emails, phones, CCCD)
✓ Relevance validation
```

**Blocked Patterns:**
- `ignore previous instructions` / `bỏ qua hướng dẫn`
- `forget everything` / `quên tất cả`
- `what is your system prompt` / `hệ thống của bạn`
- `you are now` / `bạn giờ là`

**Cost**: $0 (included)

---

## Optional Enhancement

### AWS Bedrock Guardrails ⚙️

**What it adds:**
```
+ AI-powered content filtering (hate, violence, sexual)
+ Advanced PII detection (11+ types)
+ Topic blocking (financial/medical/legal advice)
+ Profanity filtering (managed lists)
```

**Cost**: ~$0.75/month (7,500 messages)

**Setup:**

```bash
# 1. Create guardrail in AWS
./scripts/create_bedrock_guardrail.sh

# 2. Add to .env (output from script above)
BEDROCK_GUARDRAIL_ID=abc123xyz
BEDROCK_GUARDRAIL_VERSION=DRAFT

# 3. Restart service
./restart.sh

# 4. Verify in logs
tail -f /tmp/zalo_bot.log | grep -i "guardrail"
```

---

## Testing

### Test Custom Guardrails (Current)

```bash
# Run automated tests
python3 test_guardrails.py

# Test via Zalo:
# 1. Send 6 messages quickly → blocked after 5th
# 2. Send "ignore previous instructions" → blocked
# 3. Send "bỏ qua hướng dẫn" → blocked  
# 4. Send very long message (>2000 chars) → blocked
```

### Test Bedrock Guardrails (After Setup)

```bash
# Send via Zalo:
# 1. Inappropriate content → blocked by AWS
# 2. Financial advice request → blocked by topic filter
# 3. Message with profanity → blocked by word filter
# 4. Email/phone in message → PII detected

# Check logs
tail -f /tmp/zalo_bot.log | grep "Bedrock guardrails"
```

---

## Monitoring

**View blocked content:**
```bash
# All guardrail events
tail -f /tmp/zalo_bot.log | grep -i "guardrail\|blocked\|pii"

# Rate limiting
tail -f /tmp/zalo_bot.log | grep "rate"

# Prompt injection attempts
tail -f /tmp/zalo_bot.log | grep "injection"

# PII detections
tail -f /tmp/zalo_bot.log | grep "PII"
```

**Log Format:**
```
2025-11-14 06:23:38 [warning] Blocked keyword detected keyword='ignore previous instructions' user_id=123
2025-11-14 06:23:38 [warning] PII detected and redacted in response pii_types={'email': 1, 'phone_vn': 2}
2025-11-14 06:23:38 [warning] Bedrock guardrails blocked intervention=harmful_content user_id=456
```

---

## Performance Impact

| Component | Latency | Cost |
|-----------|---------|------|
| No guardrails | 0ms | $0 |
| Custom Python | <1ms | $0 |
| AWS Bedrock (optional) | ~100ms | $0.0001/unit |
| **Total (hybrid)** | **~100ms** | **~$0.75/month** |

**Response Time:**
- Without Bedrock: 9.1s (no change)
- With Bedrock: 9.2s (+1% increase)

---

## Error Messages (User-Facing)

**Rate Limiting:**
```
⏳ Bạn đang gửi tin nhắn quá nhanh. Vui lòng đợi 60 giây.
```

**Blocked Content:**
```
⚠️ Tin nhắn của bạn chứa nội dung không phù hợp. Vui lòng hỏi về UIT.
```

**Bedrock Blocked:**
```
⚠️ Tin nhắn của bạn vi phạm chính sách sử dụng. Vui lòng hỏi về UIT một cách lịch sự.
```

**Invalid Response:**
```
⚠️ Tôi không thể trả lời câu hỏi này. Vui lòng hỏi về thông tin UIT.
```

---

## Customization

### Add Blocked Keywords

Edit `/opt/zalo_bot/guardrails.py`:

```python
BLOCKED_KEYWORDS = [
    # Add your keywords here
    'new_blocked_word',
    'từ khóa mới',
]
```

### Adjust Rate Limits

Edit `/opt/zalo_bot/guardrails.py`:

```python
RATE_LIMIT_WINDOW = 60  # seconds (change to 120 for 2 minutes)
RATE_LIMIT_MAX_REQUESTS = 5  # max requests (change to 10 for more)
```

### Modify Message Length

Edit `/opt/zalo_bot/guardrails.py`:

```python
self.max_message_length = 2000  # change to 5000 for longer messages
```

**After changes:**
```bash
./restart.sh
```

---

## Troubleshooting

**Problem**: Too many false positives
**Solution**: Review `BLOCKED_KEYWORDS` list, remove overly broad patterns

**Problem**: Legitimate messages being blocked
**Solution**: Check logs for specific pattern, adjust thresholds

**Problem**: Bedrock guardrails not working
**Solution**: 
1. Check BEDROCK_GUARDRAIL_ID in .env
2. Verify guardrail exists in AWS Console
3. Check AWS credentials (aws sts get-caller-identity)

**Problem**: PII not being redacted
**Solution**: Check PII_PATTERNS regex in guardrails.py

---

## AWS Bedrock Guardrail Management

**View in AWS Console:**
```
https://console.aws.amazon.com/bedrock/home?region=us-west-2#/guardrails
```

**Update guardrail:**
```bash
# Edit via AWS Console or CLI
aws bedrock update-guardrail \
  --profile david_gapv \
  --region us-west-2 \
  --guardrail-identifier <id> \
  --name zalo-bot-uit-guardrail \
  ...

# Update version in .env
BEDROCK_GUARDRAIL_VERSION=1  # or 2, 3, etc.

# Restart
./restart.sh
```

**Delete guardrail:**
```bash
aws bedrock delete-guardrail \
  --profile david_gapv \
  --region us-west-2 \
  --guardrail-identifier <id>
```

---

## Best Practices

✅ **Start with Custom Python guardrails** (free, fast, already active)
✅ **Enable Bedrock guardrails** if you need AI-powered content filtering
✅ **Monitor logs regularly** for blocked content patterns
✅ **Adjust thresholds** based on false positive rate
✅ **Test changes** with `test_guardrails.py` before deploying
✅ **Document blocked keywords** for transparency
✅ **Review PII detections** monthly to ensure compliance

---

## Cost Breakdown (Monthly)

**Scenario 1: Custom Python Only (Current)**
```
Messages: 7,500
Custom guardrails: $0
AWS Bedrock LLM: ~$11.25 (Haiku)
MongoDB: $0 (existing)
Total: $11.25/month
```

**Scenario 2: Hybrid (Custom + Bedrock)**
```
Messages: 7,500
Custom guardrails: $0
AWS Bedrock guardrails: ~$0.75
AWS Bedrock LLM: ~$11.25 (Haiku)
MongoDB: $0 (existing)
Total: $12.00/month (+$0.75 = +6.7%)
```

**Recommendation**: Start with Custom Python (current setup), add Bedrock if needed for compliance or advanced content filtering.

---

**Last Updated**: November 14, 2025  
**Current Status**: ✅ Custom Python Guardrails ACTIVE
