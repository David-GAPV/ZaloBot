#!/usr/bin/env python3
"""Test vector search semantic understanding"""

from ueh_knowledge_base_mongodb import UEHMongoKnowledgeBase
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize with vector search
kb = UEHMongoKnowledgeBase(
    mongodb_uri=os.getenv('MONGODB_URI'),
    database_name=os.getenv('MONGODB_DATABASE'),
    enable_vector_search=True
)

# Test semantic queries
test_queries = [
    "cách thức vào học UEH 2025",  # Different wording for admission methods
    "tôi muốn học tại đại học kinh tế TPHCM năm 2025",  # Natural language
    "admission requirements for UEH",  # English query
]

for query in test_queries:
    print(f'\nQuery: "{query}"')
    print('=' * 80)
    
    # Vector search
    results = kb.vector_search(query, limit=2, similarity_threshold=0.3)
    
    if results:
        print(f'Top {len(results)} results (Vector Search):')
        for i, doc in enumerate(results, 1):
            print(f'\n{i}. {doc["title"]}')
            print(f'   Similarity: {doc.get("similarity_score", 0):.4f}')
            print(f'   Year: {doc.get("year", "N/A")}')
    else:
        print('No results found')
    
    print()

print('\n' + '=' * 80)
print('Semantic search test completed!')
