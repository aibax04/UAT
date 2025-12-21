
import os
import json
import logging
import math
import time
from typing import List, Dict, Optional, Tuple, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ChromaMemory")

class ChromaMemory:
    """
    Self-healing memory using ChromaDB.
    Stores semantic fingerprints of successful element interactions.
    """
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ChromaMemory, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, persistence_path="chroma_db"):
        if self._initialized:
            return
            
        self.persistence_path = os.path.join(os.getcwd(), persistence_path)
        self.client = None
        self.collection = None
        self.embedding_fn = None
        self._initialized = True
        
        try:
            import chromadb
            from chromadb.utils import embedding_functions
            
            # Use a persistent client
            self.client = chromadb.PersistentClient(path=self.persistence_path)
            
            # Create or get collection
            self.collection = self.client.get_or_create_collection(
                name="element_memory",
                metadata={"hnsw:space": "cosine"}
            )
            
            self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()
            
            logger.info(f"ChromaDB initialized at {self.persistence_path}")
            
        except ImportError:
            logger.error("ChromaDB not installed. Self-healing memory disabled.")
        except Exception as e:
            logger.error(f"Error initializing ChromaDB: {e}")

    def is_available(self) -> bool:
        return self.collection is not None

    def _fingerprint_to_text(self, fingerprint: Dict) -> str:
        """Convert fingerprint dict to semantic text description"""
        parts = []
        
        # Add basic info
        if fingerprint.get('tag'):
            parts.append(f"tag: {fingerprint['tag']}")
        
        if fingerprint.get('text'):
             # Clean text
            clean_text = fingerprint['text'].strip().replace('\n', ' ')
            if clean_text:
                parts.append(f"text: {clean_text}")
        
        # Add attributes
        if fingerprint.get('attributes'):
            attrs = fingerprint['attributes']
            # Prioritize semantic attributes
            important_attrs = ['id', 'name', 'type', 'aria-label', 'role', 'placeholder', 'title', 'alt', 'data-testid']
            attr_strs = []
            
            for k in important_attrs:
                if k in attrs and attrs[k]:
                    attr_strs.append(f"{k}={attrs[k]}")
            
            # Add class if meaningful (not excessive)
            if 'class' in attrs and len(attrs['class']) < 50:
                 attr_strs.append(f"class={attrs['class']}")
            
            if attr_strs:
                parts.append(f"attributes: {', '.join(attr_strs)}")
                
        # Add parent context
        if fingerprint.get('parent_context'):
            parts.append(f"parent: {fingerprint['parent_context']}")
            
        return " | ".join(parts)

    def _get_element_key(self, element_info: Dict) -> str:
        """Generate a consistent key/ID for the element intent"""
        fingerprint_data = {
            'selector': element_info.get('selector', ''),
            'description': element_info.get('description', ''),
            'text': element_info.get('text', '')
        }
        
        import hashlib
        return hashlib.md5(json.dumps(fingerprint_data, sort_keys=True).encode()).hexdigest()

    def store_success(self, element_info: Dict, actual_fingerprint: Dict, locator: str):
        """Store a successful interaction fingerprint"""
        if not self.is_available():
            return
            
        try:
            key = self._get_element_key(element_info)
            text_representation = self._fingerprint_to_text(actual_fingerprint)
            
            # Upsert into Chroma
            self.collection.upsert(
                documents=[text_representation],
                metadatas=[{
                    "locator": locator,
                    "description": element_info.get('description', ''),
                    "selector": element_info.get('selector', ''),
                    "timestamp": str(time.time())
                }],
                ids=[key]
            )
            logger.info(f"Stored self-healing memory for: {element_info.get('description', url_key)}")
            
        except Exception as e:
            logger.error(f"Error storing memory: {e}")

    def find_best_candidate(self, element_info: Dict, candidates_fingerprints: List[Dict]) -> Tuple[Optional[int], float]:
        """
        Find best matching candidate for the given element intent.
        Returns (index_of_candidate, score)
        """
        if not self.is_available() or not candidates_fingerprints:
            return None, 0.0
            
        try:
            key = self._get_element_key(element_info)
            
            # 1. Retrieve the "Golden" memory
            results = self.collection.get(ids=[key], include=['embeddings', 'documents'])
            
            if not results['ids']:
                return None, 0.0
            
            target_embedding = None
            if results.get('embeddings') and len(results['embeddings']) > 0:
                target_embedding = results['embeddings'][0]
            elif results.get('documents') and len(results['documents']) > 0:
                # Re-embed if necessary
                if self.embedding_fn:
                    target_embedding = self.embedding_fn([results['documents'][0]])[0]
            
            if target_embedding is None:
                return None, 0.0
                
            # 2. Embed candidates
            candidate_texts = [self._fingerprint_to_text(fp) for fp in candidates_fingerprints]
            
            candidate_embeddings = []
            if self.embedding_fn:
                 candidate_embeddings = self.embedding_fn(candidate_texts)
            else:
                 return None, 0.0
            
            # 3. Compute Similarity (Cosine)
            best_score = -1.0
            best_idx = -1
            
            for i, emb in enumerate(candidate_embeddings):
                score = self._cosine_similarity(target_embedding, emb)
                if score > best_score:
                    best_score = score
                    best_idx = i
            
            return best_idx, best_score

        except Exception as e:
            logger.error(f"Error finding best candidate: {e}")
            return None, 0.0

    def _cosine_similarity(self, v1, v2):
        dot_product = sum(a*b for a,b in zip(v1, v2))
        norm_a = math.sqrt(sum(a*a for a in v1))
        norm_b = math.sqrt(sum(b*b for b in v2))
        return dot_product / (norm_a * norm_b) if norm_a * norm_b > 0 else 0

# Global instance
chroma_memory = ChromaMemory()
