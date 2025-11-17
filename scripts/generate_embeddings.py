#!/usr/bin/env python3
"""
Generate embeddings for UEH knowledge base documents using AWS Bedrock
"""

import os
import json
import time
from pymongo import MongoClient
from dotenv import load_dotenv
import boto3
from typing import List, Dict

load_dotenv()

# Configuration
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
DATABASE_NAME = 'ueh_knowledge_base'
COLLECTION_NAME = 'documents'
AWS_REGION = os.getenv('AWS_REGION', 'us-west-2')
AWS_PROFILE = os.getenv('AWS_PROFILE', 'david_gapv')

# Bedrock embedding model
EMBEDDING_MODEL = 'amazon.titan-embed-text-v2:0'
EMBEDDING_DIMENSION = 1024  # Titan v2 produces 1024-dimensional embeddings
BATCH_SIZE = 10
DELAY_BETWEEN_BATCHES = 1  # seconds


class EmbeddingGenerator:
    """Generate and store embeddings for documents"""
    
    def __init__(self):
        # Initialize MongoDB connection
        try:
            self.client = MongoClient(MONGODB_URI)
            self.db = self.client[DATABASE_NAME]
            self.collection = self.db[COLLECTION_NAME]
            print(f"Connected to MongoDB: {DATABASE_NAME}.{COLLECTION_NAME}")
        except Exception as e:
            print(f"Failed to connect to MongoDB: {e}")
            raise
        
        # Initialize Bedrock client
        try:
            session = boto3.Session(profile_name=AWS_PROFILE)
            self.bedrock_runtime = session.client(
                service_name='bedrock-runtime',
                region_name=AWS_REGION
            )
            print(f"Connected to AWS Bedrock: {AWS_REGION}")
        except Exception as e:
            print(f"Failed to connect to AWS Bedrock: {e}")
            raise
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text using Bedrock"""
        try:
            # Truncate text if too long (max 8192 tokens for Titan v2)
            # Approximate: 1 token ~= 4 characters
            max_chars = 8192 * 4
            if len(text) > max_chars:
                text = text[:max_chars]
            
            # Call Bedrock
            response = self.bedrock_runtime.invoke_model(
                modelId=EMBEDDING_MODEL,
                contentType='application/json',
                accept='application/json',
                body=json.dumps({
                    'inputText': text,
                    'dimensions': EMBEDDING_DIMENSION,
                    'normalize': True
                })
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            embedding = response_body.get('embedding', [])
            
            if not embedding:
                print(f"   Warning: Empty embedding returned")
                return None
            
            return embedding
            
        except Exception as e:
            print(f"   Error generating embedding: {e}")
            return None
    
    def create_embedding_text(self, doc: Dict) -> str:
        """Create combined text for embedding from document fields"""
        parts = []
        
        # Add title (weighted more heavily by repeating)
        if doc.get('title'):
            parts.append(f"{doc['title']} {doc['title']}")
        
        # Add description
        if doc.get('description'):
            parts.append(doc['description'])
        
        # Add headings
        if doc.get('headings') and isinstance(doc['headings'], list):
            parts.append(' '.join(doc['headings']))
        
        # Add main content (truncated to first 3000 chars to prioritize important content)
        if doc.get('content'):
            content = doc['content'][:3000]
            parts.append(content)
        
        return ' '.join(parts)
    
    def process_documents(self, batch_size: int = BATCH_SIZE):
        """Process all documents and generate embeddings"""
        
        # Count documents without embeddings
        total_docs = self.collection.count_documents({})
        docs_with_embeddings = self.collection.count_documents({'embedding': {'$exists': True}})
        docs_to_process = total_docs - docs_with_embeddings
        
        print("\n" + "=" * 70)
        print("EMBEDDING GENERATION")
        print("=" * 70)
        print(f"Total documents: {total_docs}")
        print(f"Documents with embeddings: {docs_with_embeddings}")
        print(f"Documents to process: {docs_to_process}")
        print(f"Embedding model: {EMBEDDING_MODEL}")
        print(f"Embedding dimension: {EMBEDDING_DIMENSION}")
        print(f"Batch size: {batch_size}")
        print("=" * 70)
        print()
        
        if docs_to_process == 0:
            print("All documents already have embeddings!")
            return
        
        # Process documents in batches
        processed = 0
        failed = 0
        start_time = time.time()
        
        # Get documents without embeddings
        cursor = self.collection.find(
            {'embedding': {'$exists': False}},
            {'_id': 1, 'title': 1, 'description': 1, 'content': 1, 'headings': 1}
        ).batch_size(batch_size)
        
        batch = []
        for doc in cursor:
            batch.append(doc)
            
            if len(batch) >= batch_size:
                # Process batch
                success = self.process_batch(batch)
                processed += success
                failed += (len(batch) - success)
                
                print(f"Progress: {processed}/{docs_to_process} processed, {failed} failed")
                
                # Clear batch
                batch = []
                
                # Delay between batches to avoid rate limits
                time.sleep(DELAY_BETWEEN_BATCHES)
        
        # Process remaining documents
        if batch:
            success = self.process_batch(batch)
            processed += success
            failed += (len(batch) - success)
        
        elapsed_time = time.time() - start_time
        
        print("\n" + "=" * 70)
        print("EMBEDDING GENERATION SUMMARY")
        print("=" * 70)
        print(f"Documents processed: {processed}")
        print(f"Documents failed: {failed}")
        print(f"Time elapsed: {elapsed_time:.2f} seconds")
        print(f"Average: {elapsed_time/max(processed, 1):.2f} sec/document")
        print("=" * 70)
    
    def process_batch(self, batch: List[Dict]) -> int:
        """Process a batch of documents"""
        success_count = 0
        
        for doc in batch:
            try:
                # Create embedding text
                embedding_text = self.create_embedding_text(doc)
                
                if not embedding_text:
                    print(f"Skipping document {doc['_id']}: No text to embed")
                    continue
                
                # Generate embedding
                embedding = self.generate_embedding(embedding_text)
                
                if embedding is None:
                    print(f"Failed to generate embedding for {doc['_id']}")
                    continue
                
                # Update document with embedding
                self.collection.update_one(
                    {'_id': doc['_id']},
                    {'$set': {'embedding': embedding}}
                )
                
                title = doc.get('title', 'Untitled')[:60]
                print(f"   ✓ {doc['_id']}: {title}...")
                success_count += 1
                
            except Exception as e:
                print(f"   ✗ Error processing {doc['_id']}: {e}")
        
        return success_count
    
    def create_vector_search_index(self):
        """Create vector search index (for MongoDB Atlas)"""
        print("\n" + "=" * 70)
        print("VECTOR SEARCH INDEX")
        print("=" * 70)
        print("Note: Vector search indexes can only be created in MongoDB Atlas")
        print("If using Atlas, create the index manually with this definition:")
        print()
        print(json.dumps({
            "name": "vector_index",
            "type": "vectorSearch",
            "definition": {
                "fields": [
                    {
                        "type": "vector",
                        "path": "embedding",
                        "numDimensions": EMBEDDING_DIMENSION,
                        "similarity": "cosine"
                    }
                ]
            }
        }, indent=2))
        print("=" * 70)


def main():
    """Main entry point"""
    try:
        generator = EmbeddingGenerator()
        
        # Process all documents
        generator.process_documents()
        
        # Show vector search index instructions
        generator.create_vector_search_index()
        
        print("\n✅ Embedding generation complete!")
        
    except KeyboardInterrupt:
        print("\n\nEmbedding generation interrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
