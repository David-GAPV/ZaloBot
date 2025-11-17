#!/usr/bin/env python3
"""Test vector search functionality"""

from ueh_knowledge_base_mongodb import UEHMongoKnowledgeBase
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize with vector search
print("Initializing knowledge base with vector search...")
kb = UEHMongoKnowledgeBase(
    mongodb_uri=os.getenv('MONGODB_URI'),
    database_name=os.getenv('MONGODB_DATABASE'),
    enable_vector_search=True
)

query = 'phương thức tuyển sinh 2025'
print(f'\nQuery: {query}')
print('=' * 70)

# Test vector search
print("\n1. Testing VECTOR SEARCH")
print('-' * 70)
results = kb.vector_search(query, limit=3, similarity_threshold=0.3)

print(f'Results: {len(results)} documents\n')
for i, doc in enumerate(results, 1):
    print(f'{i}. {doc["title"]}')
    print(f'   Similarity: {doc.get("similarity_score", "N/A"):.4f}')
    print(f'   Year: {doc.get("year", "N/A")}')
    print()

# Test hybrid search
print("\n2. Testing HYBRID SEARCH (Vector + Text)")
print('-' * 70)
results = kb.hybrid_search(query, limit=3)

print(f'Results: {len(results)} documents\n')
for i, doc in enumerate(results, 1):
    print(f'{i}. {doc["title"]}')
    print(f'   Combined Score: {doc.get("combined_score", "N/A"):.4f}')
    print(f'   Year: {doc.get("year", "N/A")}')
    print()

print('=' * 70)
print('Vector search test completed!')
