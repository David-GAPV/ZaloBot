"""
Guardrails for Zalo Bot - Hybrid approach
Combines AWS Bedrock Guardrails with custom Python validation
"""

import re
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
import structlog

log = structlog.get_logger()

# Rate limiting storage (in-memory, per user)
USER_RATE_LIMITS = defaultdict(list)
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 5  # max requests per window

# Blocked keywords (Vietnamese and English)
BLOCKED_KEYWORDS = [
    # Prompt injection attempts
    'ignore previous instructions',
    'ignore all previous',
    'forget everything',
    'bỏ qua hướng dẫn',
    'quên tất cả',
    
    # System prompt extraction
    'what is your system prompt',
    'show me your instructions',
    'reveal your prompt',
    'system message',
    'hệ thống của bạn',
    
    # Role confusion
    'you are now',
    'act as',
    'pretend to be',
    'bạn giờ là',
    'giả vờ là',
    
    # Vietnamese profanity (common offensive words)
    'đụ',
    'địt',
    'đéo',
    'lồn',
    'cặc',
    'buồi',
    'đồ chó',
    'đồ lợn',
    'con chó',
    'con lợn',
    'mẹ mày',
    'cha mày',
    'bố mày',
    'cụ mày',
    'đồ ngu',
    'đồ khốn',
    'đồ khỉ',
    'thằng chó',
    'thằng lợn',
    'con mẹ',
    'con cha',
    'đm',
    'dm',
    'vcl',
    'vãi',
    'cc',
    'clgt',
    'cmm',
    'đkm',
    'đcm',
    'đmmm',
    'ngu',
    'óc chó',
    'óc lợn',
    
    # English profanity
    'fuck',
    'shit',
    'bitch',
    'asshole',
    'bastard',
    'damn',
]

# PII patterns (for detection)
PII_PATTERNS = {
    'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    'phone_vn': r'\b(0|\+84)[1-9][0-9]{8,9}\b',
    'cccd': r'\b[0-9]{12}\b',  # Vietnamese ID card
}


class GuardrailValidator:
    """Custom Python guardrails for input validation"""
    
    def __init__(self):
        self.max_message_length = 2000
        self.min_message_length = 1
        
    def validate_input(self, user_id: str, message: str) -> Tuple[bool, Optional[str]]:
        """
        Validate user input before sending to LLM
        
        Returns:
            (is_valid, error_message)
        """
        # 1. Check rate limiting
        is_allowed, wait_time = self._check_rate_limit(user_id)
        if not is_allowed:
            return False, f"⏳ Bạn đang gửi tin nhắn quá nhanh. Vui lòng đợi {wait_time:.0f} giây."
        
        # 2. Check message length
        if len(message) < self.min_message_length:
            return False, "❌ Tin nhắn quá ngắn. Vui lòng nhập câu hỏi của bạn."
        
        if len(message) > self.max_message_length:
            return False, f"❌ Tin nhắn quá dài (giới hạn {self.max_message_length} ký tự). Vui lòng rút ngắn câu hỏi."
        
        # 3. Check for blocked keywords (prompt injection)
        has_blocked, keyword = self._check_blocked_keywords(message)
        if has_blocked:
            log.warning("Blocked keyword detected", user_id=user_id, keyword=keyword)
            return False, "⚠️ Tin nhắn của bạn chứa nội dung không phù hợp. Vui lòng hỏi về UIT."
        
        # 4. Check for excessive special characters (spam detection)
        if self._is_spam(message):
            log.warning("Spam detected", user_id=user_id)
            return False, "⚠️ Tin nhắn của bạn có vẻ không hợp lệ. Vui lòng gửi câu hỏi thực tế."
        
        return True, None
    
    def _check_rate_limit(self, user_id: str) -> Tuple[bool, float]:
        """
        Check if user is within rate limit
        
        Returns:
            (is_allowed, wait_time_if_blocked)
        """
        now = time.time()
        
        # Clean old entries
        USER_RATE_LIMITS[user_id] = [
            t for t in USER_RATE_LIMITS[user_id]
            if now - t < RATE_LIMIT_WINDOW
        ]
        
        # Check if limit exceeded
        if len(USER_RATE_LIMITS[user_id]) >= RATE_LIMIT_MAX_REQUESTS:
            oldest_request = USER_RATE_LIMITS[user_id][0]
            wait_time = RATE_LIMIT_WINDOW - (now - oldest_request)
            return False, max(0, wait_time)
        
        # Add current request
        USER_RATE_LIMITS[user_id].append(now)
        return True, 0
    
    def _check_blocked_keywords(self, message: str) -> Tuple[bool, Optional[str]]:
        """Check if message contains blocked keywords"""
        message_lower = message.lower()
        for keyword in BLOCKED_KEYWORDS:
            if keyword.lower() in message_lower:
                return True, keyword
        return False, None
    
    def _is_spam(self, message: str) -> bool:
        """Detect spam patterns"""
        # Check for excessive repetition
        words = message.split()
        if len(words) > 5:
            unique_words = set(words)
            if len(unique_words) / len(words) < 0.3:  # Less than 30% unique words
                return True
        
        # Check for excessive special characters
        special_char_count = sum(1 for c in message if not c.isalnum() and not c.isspace())
        if len(message) > 0 and special_char_count / len(message) > 0.5:
            return True
        
        return False
    
    def validate_output(self, response: str) -> Tuple[bool, str]:
        """
        Validate LLM output before sending to user
        
        Returns:
            (is_valid, cleaned_response)
        """
        # 1. Check response length
        if len(response) > 4000:
            response = response[:4000] + "\n\n[Câu trả lời đã được rút ngắn]"
        
        # 2. Redact any PII that might have leaked
        response = self._redact_pii(response)
        
        # 3. Check if response is on-topic (UIT related)
        # This is a simple check - can be enhanced
        if len(response) < 20:
            return False, "Xin lỗi, tôi không thể tạo câu trả lời phù hợp. Vui lòng hỏi về UIT."
        
        return True, response
    
    def _redact_pii(self, text: str) -> str:
        """Redact PII from text"""
        # Redact emails
        text = re.sub(PII_PATTERNS['email'], '[EMAIL]', text)
        
        # Redact Vietnamese phone numbers
        text = re.sub(PII_PATTERNS['phone_vn'], '[PHONE]', text)
        
        # Redact CCCD numbers
        text = re.sub(PII_PATTERNS['cccd'], '[ID_NUMBER]', text)
        
        return text
    
    def detect_pii(self, text: str) -> Dict[str, int]:
        """
        Detect PII in text (for logging/monitoring)
        
        Returns:
            Dictionary with counts of each PII type
        """
        pii_found = {}
        for pii_type, pattern in PII_PATTERNS.items():
            matches = re.findall(pattern, text)
            if matches:
                pii_found[pii_type] = len(matches)
        return pii_found


class BedrockGuardrails:
    """AWS Bedrock Guardrails integration"""
    
    def __init__(self, guardrail_id: Optional[str] = None, guardrail_version: str = "DRAFT"):
        """
        Initialize Bedrock Guardrails
        
        Args:
            guardrail_id: AWS Bedrock Guardrail ID (from AWS Console)
            guardrail_version: Version of guardrail (default: DRAFT)
        """
        self.guardrail_id = guardrail_id
        self.guardrail_version = guardrail_version
        self.enabled = guardrail_id is not None
        
        if not self.enabled:
            log.warning("Bedrock Guardrails not enabled - no guardrail_id provided")
    
    def apply_guardrails(self, bedrock_client, model_id: str, prompt: str) -> Tuple[bool, str, Optional[str]]:
        """
        Apply AWS Bedrock Guardrails to prompt
        
        Returns:
            (is_safe, response_or_error, intervention_type)
        """
        if not self.enabled:
            # Skip if guardrails not configured
            return True, prompt, None
        
        try:
            # Use Bedrock's ApplyGuardrail API
            response = bedrock_client.apply_guardrail(
                guardrailIdentifier=self.guardrail_id,
                guardrailVersion=self.guardrail_version,
                source='INPUT',
                content=[{
                    'text': {'text': prompt}
                }]
            )
            
            # Check if content was blocked
            action = response.get('action')
            
            if action == 'GUARDRAIL_INTERVENED':
                # Content was blocked
                assessments = response.get('assessments', [])
                intervention_reasons = []
                
                for assessment in assessments:
                    if 'topicPolicy' in assessment:
                        intervention_reasons.append('blocked_topic')
                    if 'contentPolicy' in assessment:
                        intervention_reasons.append('harmful_content')
                    if 'wordPolicy' in assessment:
                        intervention_reasons.append('blocked_word')
                    if 'sensitiveInformationPolicy' in assessment:
                        intervention_reasons.append('pii_detected')
                
                intervention_type = ','.join(intervention_reasons) if intervention_reasons else 'unknown'
                
                log.warning(
                    "Bedrock Guardrails blocked content",
                    intervention_type=intervention_type,
                    prompt_preview=prompt[:100]
                )
                
                return False, "⚠️ Tin nhắn của bạn vi phạm chính sách sử dụng. Vui lòng hỏi về UIT một cách lịch sự.", intervention_type
            
            return True, prompt, None
            
        except Exception as e:
            log.error("Bedrock Guardrails error", error=str(e))
            # On error, allow through (fail open) but log
            return True, prompt, None


# Global validator instance
validator = GuardrailValidator()
bedrock_guardrails = None  # Will be initialized with guardrail_id if configured


def init_bedrock_guardrails(guardrail_id: Optional[str] = None, version: str = "DRAFT"):
    """Initialize Bedrock Guardrails (call from app.py)"""
    global bedrock_guardrails
    bedrock_guardrails = BedrockGuardrails(guardrail_id, version)
    if bedrock_guardrails.enabled:
        log.info("Bedrock Guardrails enabled", guardrail_id=guardrail_id)
    else:
        log.info("Bedrock Guardrails disabled - using custom guardrails only")
