"""
Google Search Agent with MongoDB Knowledge Base
Updated to use MongoDB instead of DynamoDB for UIT admission data
"""

import os
import json
import structlog
import boto3
from strands import Agent, tool
from typing import Optional, Dict, Any
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from uit_knowledge_base_mongodb import UITMongoKnowledgeBase

# Load environment variables from .env file
load_dotenv()

# Configure logging
log = structlog.get_logger()

# Simple in-memory cache for common queries
from functools import lru_cache
import hashlib
from datetime import datetime, timedelta

# Tool-level cache: MongoDB query results (shared across all users)
QUERY_CACHE = {}
CACHE_TTL = 3600  # 1 hour cache

# Agent-level cache: Full agent responses (shared across all users)
RESPONSE_CACHE = {}
RESPONSE_CACHE_MAX_SIZE = 100

# Initialize UIT MongoDB Knowledge Base
try:
    uit_kb = UITMongoKnowledgeBase(
        mongodb_uri=os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
    )
    log.info("UIT MongoDB Knowledge Base initialized")
except Exception as e:
    log.error("Failed to initialize UIT MongoDB KB", error=str(e))
    uit_kb = None


@tool
def search_uit_knowledge(query: str) -> str:
    """
    Search the UIT (University of Information Technology) knowledge base for admission information.
    This should be the FIRST tool used for any UIT-related queries about admission, programs, or tuition.
    
    Args:
        query: Search query in Vietnamese or English about UIT admission, programs, fees, etc.
    
    Returns:
        Relevant information from UIT knowledge base, or message if not found
    """
    if not uit_kb:
        return "Knowledge base not available. Please search online."
    
    # Check cache first
    cache_key = hashlib.md5(query.lower().encode()).hexdigest()
    if cache_key in QUERY_CACHE:
        cached_data = QUERY_CACHE[cache_key]
        if datetime.now() - cached_data['timestamp'] < timedelta(seconds=CACHE_TTL):
            log.info("Cache hit", query=query)
            return cached_data['result']
    
    try:
        log.info("Searching UIT knowledge base", query=query, search_type="full_text")
        
        # Use MongoDB full-text search with reduced limit for faster response
        results = uit_kb.full_text_search(query, limit=3)
        
        if not results:
            return f"No information found in UIT knowledge base for: {query}. Please search online for the latest information."
        
        # Format results - optimized for speed
        response = "Thông tin từ cơ sở dữ liệu UIT:\n\n"
        
        for i, item in enumerate(results, 1):
            response += f"{i}. {item['title']}\n"
            response += f"   URL: {item['url']}\n"
            
            # Include relevant content snippet - reduced to 400 chars for faster processing
            content = item['content']
            if len(content) > 400:
                content = content[:400] + "..."
            response += f"   Nội dung: {content}\n\n"
        
        # Cache the result for future queries
        QUERY_CACHE[cache_key] = {
            'result': response,
            'timestamp': datetime.now()
        }
        log.info("Cached MongoDB result", query=query)
        
        return response
        
    except Exception as e:
        log.error("Error searching UIT knowledge base", error=str(e))
        return f"Error searching knowledge base: {e}. Please try online search."


@tool
def google_search_serper(query: str, num_results: int = 10) -> str:
    """
    Search Google using Serper API for general queries or when UIT KB doesn't have the answer.
    
    Args:
        query: The search query
        num_results: Number of results to return (default 10)
    
    Returns:
        Formatted search results as a string
    """
    try:
        api_key = os.getenv('SERPER_API_KEY')
        if not api_key:
            return "Serper API key not configured. Cannot perform search."
        
        log.info("Performing Serper search", query=query, search_type="search")
        
        url = "https://google.serper.dev/search"
        payload = json.dumps({
            "q": query,
            "num": num_results
        })
        headers = {
            'X-API-KEY': api_key,
            'Content-Type': 'application/json'
        }
        
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Format results
        results_text = f"Search results for: {query}\n\n"
        
        if 'organic' in data:
            for i, result in enumerate(data['organic'][:num_results], 1):
                results_text += f"{i}. {result.get('title', 'No title')}\n"
                results_text += f"   URL: {result.get('link', 'N/A')}\n"
                if 'snippet' in result:
                    results_text += f"   {result['snippet']}\n"
                results_text += "\n"
        
        log.info("Search completed", query=query, results_count=len(data.get('organic', [])))
        return results_text
        
    except Exception as e:
        log.error("Search failed", error=str(e))
        return f"Search error: {e}"


@tool
def google_search_tavily(query: str, num_results: int = 5) -> str:
    """
    Alternative search using Tavily API (if Serper fails or for different results).
    
    Args:
        query: The search query
        num_results: Number of results to return
    
    Returns:
        Formatted search results
    """
    try:
        api_key = os.getenv('TAVILY_API_KEY')
        if not api_key:
            return "Tavily API key not configured."
        
        log.info("Performing Tavily search", query=query)
        
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": api_key,
            "query": query,
            "max_results": num_results
        }
        
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        results_text = f"Search results for: {query}\n\n"
        
        if 'results' in data:
            for i, result in enumerate(data['results'], 1):
                results_text += f"{i}. {result.get('title', 'No title')}\n"
                results_text += f"   URL: {result.get('url', 'N/A')}\n"
                results_text += f"   {result.get('content', 'No description')}\n\n"
        
        return results_text
        
    except Exception as e:
        log.error("Tavily search failed", error=str(e))
        return f"Tavily search error: {e}"


@tool
def extract_web_content(url: str) -> str:
    """
    Extract main content from a webpage.
    
    Args:
        url: The URL to extract content from
    
    Returns:
        Main text content from the webpage
    """
    try:
        log.info("Extracting content from URL", url=url)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header']):
            element.decompose()
        
        # Extract text
        text = soup.get_text(separator='\n', strip=True)
        
        # Limit length
        if len(text) > 3000:
            text = text[:3000] + "..."
        
        log.info("Content extracted", url=url, length=len(text))
        return text
        
    except Exception as e:
        log.error("Content extraction failed", url=url, error=str(e))
        return f"Error extracting content from {url}: {e}"


@tool
def analyze_search_results(query: str, results: str) -> str:
    """
    Analyze and synthesize information from search results.
    
    Args:
        query: Original search query
        results: Search results to analyze
    
    Returns:
        Summary or analysis of the results
    """
    # This is a simple passthrough - the LLM will do the actual analysis
    return f"Analyzing results for query: {query}\n\nResults to analyze:\n{results}"


class GoogleSearchAgent:
    """Google Search Agent with AWS Bedrock and UIT MongoDB Knowledge Base"""
    
    def __init__(
        self,
        model_id: Optional[str] = None,
        region: Optional[str] = None,
        profile: Optional[str] = None
    ):
        self.model_id = model_id or os.getenv('BEDROCK_MODEL_ID', 'anthropic.claude-3-5-sonnet-20241022-v2:0')
        self.region = region or os.getenv('AWS_REGION', 'us-west-2')
        self.profile = profile or os.getenv('AWS_PROFILE', 'default')
        
        # Create Bedrock client
        session = boto3.Session(profile_name=self.profile, region_name=self.region)
        self.bedrock_client = session.client('bedrock-runtime')
        
        # Create agent with all tools
        self.agent = Agent(
            model=self.model_id,
            tools=[
                search_uit_knowledge,
                google_search_serper,
                google_search_tavily,
                extract_web_content,
                analyze_search_results
            ],
            name="GoogleSearchAgent_MongoDB",
            description="AI agent with Google search and UIT MongoDB knowledge base. For UIT queries, searches knowledge base FIRST before web search."
        )
        
        log.info(
            "Google Search Agent initialized",
            model=self.model_id,
            profile=self.profile,
            region=self.region
        )
    
    def chat(self, message: str) -> str:
        """
        Send a message to the agent and get a response.
        
        Args:
            message: User's message/query
        
        Returns:
            Agent's response text
        """
        try:
            # Check global response cache first
            cache_key = message.lower().strip()
            if cache_key in RESPONSE_CACHE:
                log.info("Cache hit (global)", query=message[:50])
                return RESPONSE_CACHE[cache_key]
            
            # Use invocation_state instead of deprecated **kwargs
            response = self.agent(message, invocation_state={'bedrock_client': self.bedrock_client})
            
            # Extract text from AgentResult
            result_text = None
            if hasattr(response, 'message'):
                msg = response.message
                if isinstance(msg, dict) and 'content' in msg:
                    content = msg['content']
                    if isinstance(content, list) and len(content) > 0:
                        result_text = content[0].get('text', str(response))
                else:
                    result_text = str(msg)
            else:
                result_text = str(response)
            
            # Cache the response globally (shared across all users)
            if len(RESPONSE_CACHE) < RESPONSE_CACHE_MAX_SIZE:
                RESPONSE_CACHE[cache_key] = result_text
                log.info("Cached response (global)", query=message[:50])
            
            return result_text
        except Exception as e:
            log.error("Chat failed", error=str(e))
            return f"Error: {e}"


def main():
    """Test the agent"""
    agent = GoogleSearchAgent()
    
    print("\n" + "=" * 60)
    print("Google Search Agent with MongoDB Knowledge Base")
    print("=" * 60)
    print("\nTest queries:")
    print("1. UIT có bao nhiêu phương thức tuyển sinh năm 2025?")
    print("2. What are the latest AI developments?")
    print("\nType 'quit' to exit\n")
    
    while True:
        try:
            query = input("\nYour query: ").strip()
            if query.lower() in ['quit', 'exit', 'q']:
                break
            
            if not query:
                continue
            
            # Agent will stream the response during execution
            # No need to print again - just call it
            response = agent.chat(query)
            # Response already streamed, just add separator
            print("\n" + "-" * 60)
            
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")


if __name__ == '__main__':
    main()
