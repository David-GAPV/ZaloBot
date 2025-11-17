"""
MongoDB-based Knowledge Base for UEH (University of Economics Ho Chi Minh City) Data
Provides full-text search capabilities for university information
"""

import os
from pymongo import MongoClient, ASCENDING, TEXT
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import hashlib
import time
from urllib.parse import urljoin, urlparse
import json
from dotenv import load_dotenv
import boto3
import numpy as np

# Load environment variables from .env file
load_dotenv()


class UEHMongoKnowledgeBase:
    """MongoDB Knowledge Base for UEH data with full-text search and vector search"""
    
    def __init__(
        self, 
        mongodb_uri: Optional[str] = None,
        database_name: str = "ueh_knowledge_base",
        collection_name: str = "documents",
        enable_vector_search: bool = True
    ):
        """
        Initialize MongoDB connection
        
        Args:
            mongodb_uri: MongoDB connection string. If None, uses environment variable MONGODB_URI
            database_name: Name of the database
            collection_name: Name of the collection
            enable_vector_search: Enable vector search with AWS Bedrock embeddings
        """
        self.mongodb_uri = mongodb_uri or os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
        self.database_name = database_name
        self.collection_name = collection_name
        self.enable_vector_search = enable_vector_search
        
        try:
            self.client = MongoClient(self.mongodb_uri, serverSelectionTimeoutMS=5000)
            # Test connection
            self.client.server_info()
            self.db = self.client[database_name]
            self.collection = self.db[collection_name]
            print(f"Connected to MongoDB: {database_name}.{collection_name}")
        except Exception as e:
            print(f"Failed to connect to MongoDB: {e}")
            raise
        
        # Initialize Bedrock client for vector search
        if self.enable_vector_search:
            try:
                aws_profile = os.getenv('AWS_PROFILE', 'david_gapv')
                aws_region = os.getenv('AWS_REGION', 'us-west-2')
                session = boto3.Session(profile_name=aws_profile)
                self.bedrock_runtime = session.client(
                    service_name='bedrock-runtime',
                    region_name=aws_region
                )
                self.embedding_model = 'amazon.titan-embed-text-v2:0'
                self.embedding_dimension = 1024
            except Exception as e:
                print(f"Warning: Could not initialize Bedrock for vector search: {e}")
                self.enable_vector_search = False
    
    def setup_indexes(self):
        """Create indexes for better search performance"""
        try:
            # Text index for full-text search
            self.collection.create_index(
                [
                    ("title", TEXT),
                    ("content", TEXT),
                    ("keywords", TEXT)
                ],
                weights={
                    "title": 10,
                    "keywords": 5,
                    "content": 1
                },
                name="text_search_index"
            )
            
            # Regular indexes
            self.collection.create_index([("category", ASCENDING)], name="category_index")
            self.collection.create_index([("url", ASCENDING)], name="url_index", unique=True)
            self.collection.create_index([("content_id", ASCENDING)], name="content_id_index", unique=True)
            
            print("Indexes created successfully")
        except Exception as e:
            print(f"Note: Indexes may already exist: {e}")
    
    def add_document(self, document: Dict[str, Any]) -> str:
        """
        Add or update a document in the knowledge base
        
        Args:
            document: Dictionary containing document data
                Required fields: url, title, content
                Optional: category, keywords, content_type
        
        Returns:
            Inserted document ID
        """
        # Generate content_id if not provided
        if 'content_id' not in document:
            document['content_id'] = hashlib.md5(document['url'].encode()).hexdigest()
        
        # Add timestamp
        document['updated_at'] = datetime.now().isoformat()
        
        # Upsert (update if exists, insert if new)
        result = self.collection.replace_one(
            {'content_id': document['content_id']},
            document,
            upsert=True
        )
        
        return document['content_id']
    
    def full_text_search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Perform full-text search across all documents
        
        Args:
            query: Search query string
            limit: Maximum number of results
        
        Returns:
            List of matching documents sorted by relevance
        """
        try:
            results = self.collection.find(
                {'$text': {'$search': query}},
                {'score': {'$meta': 'textScore'}}
            ).sort([('score', {'$meta': 'textScore'})]).limit(limit)
            
            documents = []
            for doc in results:
                doc.pop('_id', None)  # Remove MongoDB ObjectId
                doc.pop('embedding', None)  # Remove embedding vector
                doc.pop('score', None)  # Remove search score
                documents.append(doc)
            
            return documents
        except Exception as e:
            print(f"Full-text search error: {e}")
            return []
    
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for query text using AWS Bedrock"""
        if not self.enable_vector_search:
            return None
        
        try:
            # Truncate text if too long
            max_chars = 8192 * 4
            if len(text) > max_chars:
                text = text[:max_chars]
            
            response = self.bedrock_runtime.invoke_model(
                modelId=self.embedding_model,
                contentType='application/json',
                accept='application/json',
                body=json.dumps({
                    'inputText': text,
                    'dimensions': self.embedding_dimension,
                    'normalize': True
                })
            )
            
            response_body = json.loads(response['body'].read())
            embedding = response_body.get('embedding', [])
            
            return embedding if embedding else None
            
        except Exception as e:
            print(f"Error generating embedding: {e}")
            return None
    
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            vec1_np = np.array(vec1)
            vec2_np = np.array(vec2)
            
            dot_product = np.dot(vec1_np, vec2_np)
            norm1 = np.linalg.norm(vec1_np)
            norm2 = np.linalg.norm(vec2_np)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            return float(dot_product / (norm1 * norm2))
        except Exception as e:
            print(f"Error calculating similarity: {e}")
            return 0.0
    
    def vector_search(self, query: str, limit: int = 10, similarity_threshold: float = 0.5) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search
        
        Args:
            query: Search query string
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score (0-1)
        
        Returns:
            List of matching documents sorted by similarity
        """
        if not self.enable_vector_search:
            print("Vector search not enabled, falling back to text search")
            return self.full_text_search(query, limit)
        
        try:
            # Generate query embedding
            query_embedding = self.generate_embedding(query)
            if not query_embedding:
                print("Could not generate query embedding, falling back to text search")
                return self.full_text_search(query, limit)
            
            # Get all documents with embeddings
            documents = list(self.collection.find({'embedding': {'$exists': True}}))
            
            # Calculate similarity scores
            results = []
            for doc in documents:
                if 'embedding' in doc and doc['embedding']:
                    similarity = self.cosine_similarity(query_embedding, doc['embedding'])
                    
                    if similarity >= similarity_threshold:
                        doc.pop('_id', None)
                        doc.pop('embedding', None)
                        doc['similarity_score'] = similarity
                        results.append(doc)
            
            # Sort by similarity and return top results
            results.sort(key=lambda x: x['similarity_score'], reverse=True)
            return results[:limit]
            
        except Exception as e:
            print(f"Vector search error: {e}, falling back to text search")
            return self.full_text_search(query, limit)
    
    def hybrid_search(self, query: str, limit: int = 10, text_weight: float = 0.3, vector_weight: float = 0.7) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining text and vector search
        
        Args:
            query: Search query string
            limit: Maximum number of results
            text_weight: Weight for text search score (0-1)
            vector_weight: Weight for vector search score (0-1)
        
        Returns:
            List of matching documents with combined scores
        """
        if not self.enable_vector_search:
            return self.full_text_search(query, limit)
        
        try:
            # Get text search results
            text_results = self.full_text_search(query, limit * 2)
            text_scores = {doc.get('url', doc.get('content_id', '')): 1.0 / (i + 1) for i, doc in enumerate(text_results)}
            
            # Get vector search results
            vector_results = self.vector_search(query, limit * 2, similarity_threshold=0.3)
            vector_scores = {doc.get('url', doc.get('content_id', '')): doc.get('similarity_score', 0) for doc in vector_results}
            
            # Combine results
            all_docs = {doc.get('url', doc.get('content_id', '')): doc for doc in text_results + vector_results}
            
            # Calculate combined scores
            combined_results = []
            for doc_id, doc in all_docs.items():
                text_score = text_scores.get(doc_id, 0)
                vector_score = vector_scores.get(doc_id, 0)
                combined_score = (text_weight * text_score) + (vector_weight * vector_score)
                
                doc['combined_score'] = combined_score
                doc.pop('similarity_score', None)
                combined_results.append(doc)
            
            # Sort by combined score
            combined_results.sort(key=lambda x: x['combined_score'], reverse=True)
            return combined_results[:limit]
            
        except Exception as e:
            print(f"Hybrid search error: {e}, falling back to text search")
            return self.full_text_search(query, limit)
    
    def search_by_category(self, category: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search documents by category"""
        results = self.collection.find({'category': category}).limit(limit)
        documents = []
        for doc in results:
            doc.pop('_id', None)
            documents.append(doc)
        return documents
    
    def search_by_keywords(self, keywords: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search documents by keywords using regex (for flexible matching)
        
        Args:
            keywords: Keywords to search for
            limit: Maximum number of results
        """
        # Split keywords and create regex pattern
        keyword_list = [k.strip() for k in keywords.split(',') if k.strip()]
        
        if not keyword_list:
            return []
        
        # Search in keywords field or content
        query = {
            '$or': [
                {'keywords': {'$regex': '|'.join(keyword_list), '$options': 'i'}},
                {'content': {'$regex': '|'.join(keyword_list), '$options': 'i'}},
                {'title': {'$regex': '|'.join(keyword_list), '$options': 'i'}}
            ]
        }
        
        results = self.collection.find(query).limit(limit)
        documents = []
        for doc in results:
            doc.pop('_id', None)
            documents.append(doc)
        return documents
    
    def get_document_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Get a specific document by URL"""
        doc = self.collection.find_one({'url': url})
        if doc:
            doc.pop('_id', None)
            return doc
        return None
    
    def get_all_documents(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all documents from the knowledge base"""
        results = self.collection.find().limit(limit)
        documents = []
        for doc in results:
            doc.pop('_id', None)
            documents.append(doc)
        return documents
    
    def count_documents(self) -> int:
        """Get total number of documents in the knowledge base"""
        return self.collection.count_documents({})
    
    def delete_document(self, content_id: str) -> bool:
        """Delete a document by content_id"""
        result = self.collection.delete_one({'content_id': content_id})
        return result.deleted_count > 0
    
    def clear_all(self):
        """Clear all documents (use with caution!)"""
        self.collection.delete_many({})
        print("All documents cleared")


# Quick setup script
def setup_mongodb_knowledge_base():
    
    def __init__(self, base_url: str = "https://tuyensinh.uit.edu.vn"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.session.verify = False
        
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    def scrape_page(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape a single page"""
        try:
            print(f"Scraping: {url}")
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract content
            title = self._extract_title(soup)
            content = self._extract_content(soup)
            
            if len(content) < 50:  # Skip pages with minimal content
                return None
            
            category = self._extract_category(url)
            keywords = self._extract_keywords(title, content)
            content_id = hashlib.md5(url.encode()).hexdigest()
            
            return {
                'content_id': content_id,
                'url': url,
                'title': title,
                'content': content,
                'category': category,
                'keywords': ','.join(keywords) if isinstance(keywords, list) else keywords,
                'scraped_at': datetime.now().isoformat(),
                'content_type': self._determine_content_type(url, title)
            }
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract page title"""
        for selector in ['h1', 'h2', '.page-title', '.post-title', 'title']:
            element = soup.find(selector)
            if element:
                return element.get_text(strip=True)
        return "Untitled"
    
    def _extract_content(self, soup: BeautifulSoup) -> str:
        """Extract main content"""
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        for selector in ['article', '.content', '.post-content', '.main-content', 'main']:
            element = soup.find(selector)
            if element:
                return element.get_text(separator='\n', strip=True)
        
        return soup.get_text(separator='\n', strip=True)
    
    def _extract_category(self, url: str) -> str:
        """Extract category from URL"""
        if 'tuyen-sinh' in url:
            return 'tuyển sinh'
        elif 'thong-bao' in url:
            return 'thông báo'
        elif 'nganh-dao-tao' in url:
            return 'ngành đào tạo'
        elif 'hoc-bong' in url:
            return 'học bổng'
        return 'general'
    
    def _extract_keywords(self, title: str, content: str) -> List[str]:
        """Extract keywords"""
        keywords = set()
        text = (title + ' ' + content).lower()
        
        important_terms = [
            'tuyển sinh', 'phương thức', 'xét tuyển', 'điểm chuẩn',
            'học bổng', 'ĐGNL', 'tốt nghiệp THPT', 'ngành đào tạo',
            'đăng ký', 'hồ sơ', '2025', '2024', 'UIT', 'ĐHQG'
        ]
        
        for term in important_terms:
            if term.lower() in text:
                keywords.add(term)
        
        return list(keywords)[:10]
    
    def _determine_content_type(self, url: str, title: str) -> str:
        """Determine content type"""
        title_lower = title.lower()
        if 'thông báo' in title_lower:
            return 'announcement'
        elif 'phương thức' in title_lower or 'đề án' in title_lower:
            return 'admission_plan'
        elif 'ngành' in title_lower:
            return 'program'
        return 'article'


# Quick setup script
def setup_mongodb_knowledge_base():
    """Setup MongoDB knowledge base with initial data"""
    print("=" * 60)
    print("MongoDB Knowledge Base Setup")
    print("=" * 60)
    
    # Initialize MongoDB KB
    kb = UITMongoKnowledgeBase()
    
    # Setup indexes
    kb.setup_indexes()
    
    # Add manual admission methods entry
    admission_info = {
        'content_id': 'uit_2025_admission_methods',
        'url': 'https://tuyensinh.uit.edu.vn/tuyen-sinh-chung',
        'title': 'UIT có 3 phương thức tuyển sinh năm 2025',
        'content': '''THÔNG TIN TUYỂN SINH ĐẠI HỌC UIT NĂM 2025

Trường Đại học Công nghệ Thông tin (UIT) - ĐHQG TP.HCM có 3 phương thức tuyển sinh năm 2025:

PHƯƠNG THỨC 1: TUYỂN THẲNG VÀ ƯU TIÊN XÉT TUYỂN
- Tuyển thẳng theo quy định của Bộ GD&ĐT
- Ưu tiên xét tuyển theo quy định ĐHQG-HCM
- Ưu tiên xét tuyển theo quy định của UIT

PHƯƠNG THỨC 2: XÉT TUYỂN DỰA TRÊN KẾT QUẢ KỲ THI ĐÁNH GIÁ NĂNG LỰC (ĐGNL)
- Kỳ thi do ĐHQG-HCM tổ chức năm 2025
- Điểm xét tuyển = Điểm ĐGNL + Điểm ưu tiên
- Đánh giá năng lực Toán học, Đọc hiểu, Giải quyết vấn đề

PHƯƠNG THỨC 3: XÉT TUYỂN DỰA TRÊN KẾT QUẢ THI TỐT NGHIỆP THPT
- Sử dụng điểm thi tốt nghiệp THPT năm 2025
- Các tổ hợp: A00 (Toán-Lý-Hóa), A01 (Toán-Lý-Anh), D01 (Toán-Văn-Anh), D07 (Toán-Hóa-Anh)

Liên hệ: 
- Website: https://tuyensinh.uit.edu.vn
- Email: tuyensinh@uit.edu.vn
- Điện thoại: 028 3725 2002
''',
        'category': 'tuyển sinh',
        'keywords': 'tuyển sinh,phương thức,xét tuyển,UIT,2025,ĐGNL,tốt nghiệp THPT,3 phương thức',
        'content_type': 'admission_methods'
    }
    
    kb.add_document(admission_info)
    print("Added admission methods document")
    
    # Test search
    print("\n" + "=" * 60)
    print("Testing search...")
    print("=" * 60)
    
    results = kb.full_text_search("UIT có bao nhiêu phương thức tuyển sinh")
    print(f"\nSearch results: {len(results)}")
    for doc in results[:3]:
        print(f"  - {doc['title']}")
    
    print(f"\nTotal documents in KB: {kb.count_documents()}")
    print("\nSetup completed!")


if __name__ == '__main__':
    setup_mongodb_knowledge_base()
