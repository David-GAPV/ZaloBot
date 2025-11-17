#!/usr/bin/env python3
"""
UEH Website Crawler for Zalo Bot Knowledge Base
Crawls https://www.ueh.edu.vn/ and all sub-pages to collect data for MongoDB
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
import json
from datetime import datetime
from pymongo import MongoClient
from collections import deque
import os
from dotenv import load_dotenv
import hashlib
import re

load_dotenv()

# Configuration
START_URLS = [
    "https://www.ueh.edu.vn/",           # Main website
    "https://tuyensinh.ueh.edu.vn/",     # Admission portal (IMPORTANT)
    "https://daotao.ueh.edu.vn/",        # Training/education portal
    "https://student.ueh.edu.vn/",       # Student portal
    "https://youth.ueh.edu.vn/",         # Youth union activities
    "https://hocbong.ueh.edu.vn/",       # Scholarship portal
    "https://lms.ueh.edu.vn/",           # E-learning platform
]
MAX_PAGES = 1000  # Limit to prevent infinite crawling
DELAY_BETWEEN_REQUESTS = 1  # seconds
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
DATABASE_NAME = 'ueh_knowledge_base'
COLLECTION_NAME = 'documents'

# Patterns to include/exclude (prioritize 2024-2025 news and admission)
INCLUDE_PATTERNS = [
    r'/tuyen-sinh',  # Admission
    r'/tin-tuc',  # News
    r'/2024',  # 2024 content
    r'/2025',  # 2025 content
    r'/chuong-trinh-dao-tao',  # Programs
    r'/hoc-phi',  # Tuition
    r'/gioi-thieu',  # About
    r'/khoa-vien',  # Faculties
    r'/sinh-vien',  # Students
    r'/research',  # Research
    r'/thong-bao',  # Announcements
    r'/su-kien',  # Events
]

EXCLUDE_PATTERNS = [
    r'/download/',
    r'/uploads/',
    r'/wp-content/',
    r'\.pdf$',
    r'\.jpg$',
    r'\.png$',
    r'\.gif$',
    r'/wp-admin/',
    r'/tag/',
    r'/category/',
]


class UEHCrawler:
    """Crawler for UEH University website"""
    
    def __init__(self):
        self.visited_urls = set()
        self.to_visit = deque(START_URLS)  # Start from multiple URLs
        self.pages_crawled = 0
        self.documents = []
        
        # Initialize MongoDB connection
        try:
            self.client = MongoClient(MONGODB_URI)
            self.db = self.client[DATABASE_NAME]
            self.collection = self.db[COLLECTION_NAME]
            print(f"Connected to MongoDB: {DATABASE_NAME}.{COLLECTION_NAME}")
        except Exception as e:
            print(f"Failed to connect to MongoDB: {e}")
            raise
    
    def is_valid_url(self, url):
        """Check if URL should be crawled"""
        parsed = urlparse(url)
        
        # Must be from ueh.edu.vn domain
        if 'ueh.edu.vn' not in parsed.netloc:
            return False
        
        # Check exclude patterns
        for pattern in EXCLUDE_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                return False
        
        # Check if URL matches include patterns (or is homepage/start URL)
        if url in START_URLS:
            return True
            
        for pattern in INCLUDE_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        
        return False
    
    def extract_text_content(self, soup):
        """Extract main text content from page"""
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        # Get text
        text = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return text
    
    def extract_metadata(self, soup, url):
        """Extract metadata from page"""
        metadata = {
            'url': url,
            'title': '',
            'description': '',
            'keywords': [],
            'year': self.extract_year(url, soup),
            'crawled_at': datetime.utcnow()
        }
        
        # Title
        if soup.title:
            metadata['title'] = soup.title.string.strip()
        
        # Meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            metadata['description'] = meta_desc.get('content').strip()
        
        # Meta keywords
        meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
        if meta_keywords and meta_keywords.get('content'):
            keywords = meta_keywords.get('content').split(',')
            metadata['keywords'] = [k.strip() for k in keywords]
        
        # Extract headings
        headings = []
        for i in range(1, 4):  # h1, h2, h3
            for heading in soup.find_all(f'h{i}'):
                headings.append(heading.get_text().strip())
        metadata['headings'] = headings
        
        return metadata
    
    def extract_year(self, url, soup):
        """Extract year from URL or content"""
        # Check URL for year
        year_match = re.search(r'/(202[4-5])/', url)
        if year_match:
            return int(year_match.group(1))
        
        # Check content for year mentions
        text = soup.get_text()
        if '2025' in text:
            return 2025
        elif '2024' in text:
            return 2024
        
        return None
    
    def generate_doc_id(self, url):
        """Generate unique document ID from URL"""
        return hashlib.md5(url.encode()).hexdigest()
    
    def crawl_page(self, url):
        """Crawl a single page"""
        try:
            print(f"Crawling: {url}")
            
            response = requests.get(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; UEHBot/1.0; +http://ueh.edu.vn)'
            })
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract content
            text_content = self.extract_text_content(soup)
            metadata = self.extract_metadata(soup, url)
            
            # Create document
            if len(text_content) > 100:  # Only save pages with substantial content
                document = {
                    '_id': self.generate_doc_id(url),
                    'url': url,
                    'title': metadata['title'],
                    'description': metadata['description'],
                    'content': text_content[:10000],  # Limit to 10K chars
                    'keywords': metadata['keywords'],
                    'headings': metadata['headings'],
                    'year': metadata['year'],
                    'crawled_at': metadata['crawled_at'],
                    'word_count': len(text_content.split()),
                    'source': 'ueh.edu.vn'
                }
                
                self.documents.append(document)
                print(f"   Extracted {len(text_content)} chars, {len(text_content.split())} words")
            else:
                print(f"   Skipped (too short: {len(text_content)} chars)")
            
            # Find all links on page
            for link in soup.find_all('a', href=True):
                absolute_url = urljoin(url, link['href'])
                # Remove fragment
                absolute_url = absolute_url.split('#')[0]
                
                if (absolute_url not in self.visited_urls and 
                    absolute_url not in self.to_visit and
                    self.is_valid_url(absolute_url)):
                    self.to_visit.append(absolute_url)
            
        except requests.RequestException as e:
            print(f"   Error crawling {url}: {e}")
        except Exception as e:
            print(f"   Unexpected error: {e}")
    
    def save_to_mongodb(self):
        """Save documents to MongoDB"""
        if not self.documents:
            print("No documents to save")
            return
        
        print(f"\nSaving {len(self.documents)} documents to MongoDB...")
        
        try:
            # Drop existing collection (fresh start)
            self.collection.drop()
            print("   Dropped existing collection")
            
            # Insert documents
            result = self.collection.insert_many(self.documents, ordered=False)
            print(f"   Inserted {len(result.inserted_ids)} documents")
            
            # Create indexes
            self.collection.create_index([('title', 'text'), ('content', 'text'), ('description', 'text')])
            print("   Created text indexes")
            
            self.collection.create_index('url')
            print("   Created URL index")
            
            self.collection.create_index('crawled_at')
            print("   Created date index")
            
            self.collection.create_index('year')
            print("   Created year index")
            
            print(f"\n✅ Successfully saved {len(self.documents)} documents to MongoDB")
            
        except Exception as e:
            print(f"Error saving to MongoDB: {e}")
    
    def save_to_json(self, filename='ueh_data.json'):
        """Save documents to JSON file as backup"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.documents, f, ensure_ascii=False, indent=2, default=str)
            print(f"Saved backup to {filename}")
        except Exception as e:
            print(f"Error saving to JSON: {e}")
    
    def run(self):
        """Main crawler loop"""
        print("=" * 70)
        print("UEH WEBSITE CRAWLER")
        print("=" * 70)
        print(f"Start URLs: {', '.join(START_URLS)}")
        print(f"Max pages: {MAX_PAGES}")
        print(f"Database: {DATABASE_NAME}.{COLLECTION_NAME}")
        print("=" * 70)
        print()
        
        start_time = time.time()
        
        while self.to_visit and self.pages_crawled < MAX_PAGES:
            url = self.to_visit.popleft()
            
            if url in self.visited_urls:
                continue
            
            self.visited_urls.add(url)
            self.crawl_page(url)
            self.pages_crawled += 1
            
            print(f"   Progress: {self.pages_crawled}/{MAX_PAGES} pages crawled, {len(self.to_visit)} in queue\n")
            
            # Delay between requests to be respectful
            time.sleep(DELAY_BETWEEN_REQUESTS)
        
        elapsed_time = time.time() - start_time
        
        print("\n" + "=" * 70)
        print("CRAWLING SUMMARY")
        print("=" * 70)
        print(f"Pages crawled: {self.pages_crawled}")
        print(f"Documents collected: {len(self.documents)}")
        print(f"Time elapsed: {elapsed_time:.2f} seconds")
        print(f"Average: {elapsed_time/max(self.pages_crawled, 1):.2f} sec/page")
        print("=" * 70)
        print()
        
        # Save to MongoDB
        self.save_to_mongodb()
        
        # Save backup to JSON
        self.save_to_json()
        
        print("\n✅ Crawling complete!")
        print(f"📁 Data saved to MongoDB: {DATABASE_NAME}.{COLLECTION_NAME}")
        print(f"📁 Backup saved to: ueh_data.json")


def main():
    """Main entry point"""
    try:
        crawler = UEHCrawler()
        crawler.run()
    except KeyboardInterrupt:
        print("\n\nCrawling interrupted by user")
        if crawler.documents:
            print(f"Saving {len(crawler.documents)} documents collected so far...")
            crawler.save_to_mongodb()
            crawler.save_to_json()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
