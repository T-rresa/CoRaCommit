import os
import json
import pickle
import faiss
import numpy as np
import sqlite3
import threading
from typing import Dict, Any, Optional, List
from ..embedding.codebert import CodeBERTEmbedding
from ..embedding.jina import JinaEmbedding

class ResourceManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ResourceManager, cls).__new__(cls)
            cls._instance.initialized = False
            cls._instance.db_conn = None
            cls._instance.db_lock = threading.Lock()
        return cls._instance

    def initialize(self, resource_path: str = "resource"):
        if self.initialized:
            print("DEBUG: Already initialized")
            return
            
        print(f"DEBUG: Entering initialize with path {resource_path}")
        self.resource_path = resource_path
        
        try:
            # Connect to SQLite (lazy load)
            db_path = os.path.join(self.resource_path, "docs.db")
            if os.path.exists(db_path):
                # check_same_thread=False for cross-thread read-only access
                self.db_conn = sqlite3.connect(db_path, check_same_thread=False)
                print(f"DEBUG: Connected to SQLite database at {db_path}")
            else:
                print(f"DEBUG: Warning: {db_path} not found. Fallback to empty docs.")
                self.db_conn = None
            
            # Load FAISS indices (mmap for memory efficiency)
            print("DEBUG: Step 2 - Loading FAISS Indices...")
            self.faiss_indices = {}
            self.doc_id_maps = {}
            
            # Load only selected model (default: codebert)
            selected_model = os.getenv("EMBEDDING_MODEL", "codebert")
            print(f"DEBUG: Selected embedding model: {selected_model}")
            
            if selected_model == "all":
                self._load_faiss_index("codebert")
                self._load_faiss_index("jina")
            else:
                self._load_faiss_index(selected_model)
            
            
            # Lazy-load embedding models
            print("DEBUG: Step 3 - Initializing Embedding Models container...")
            self.embedding_models = {}
            
            self.initialized = True
            print("DEBUG: Resources loaded successfully.")
            
        except Exception as e:
            print(f"CRITICAL ERROR in initialize: {e}")
            import traceback
            traceback.print_exc()
            raise e

    def get_doc(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve document by ID from SQLite database.
        Returns dict with keys: id, message, diff, repo
        """
        if not self.db_conn:
            return None
            
        try:
            safe_doc_id = str(doc_id)
            # Query by ID (TEXT primary key)
            with self.db_lock:
                cursor = self.db_conn.cursor()
                try:
                    cursor.execute("SELECT message, diff, repo FROM docs WHERE id=?", (safe_doc_id,))
                    row = cursor.fetchone()
                finally:
                    cursor.close()
            
            if row:
                return {
                    "id": safe_doc_id,
                    "message": row[0],
                    "diff": row[1],
                    "repo": row[2]
                }
            return None
        except Exception as e:
            print(f"Error querying doc {safe_doc_id if 'safe_doc_id' in locals() else doc_id}: {e}")
            return None

    def get_docs(self, doc_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Batch retrieve documents by IDs from SQLite database.
        Returns a dict keyed by doc id.
        """
        if not self.db_conn or not doc_ids:
            return {}

        safe_doc_ids = [str(doc_id) for doc_id in doc_ids]
        placeholders = ",".join(["?"] * len(safe_doc_ids))
        sql = f"SELECT id, message, diff, repo FROM docs WHERE id IN ({placeholders})"

        try:
            with self.db_lock:
                cursor = self.db_conn.cursor()
                try:
                    cursor.execute(sql, safe_doc_ids)
                    rows = cursor.fetchall()
                finally:
                    cursor.close()

            return {
                str(row[0]): {
                    "id": str(row[0]),
                    "message": row[1],
                    "diff": row[2],
                    "repo": row[3],
                }
                for row in rows
            }
        except Exception as e:
            print(f"Error querying docs batch: {e}")
            return {}

    def _load_faiss_index(self, model_name: str):
        index_path = os.path.join(self.resource_path, "faiss", f"{model_name}.index")
        map_path = os.path.join(self.resource_path, "embeddings", f"{model_name}.doc_ids.npy")
        
        if os.path.exists(index_path) and os.path.exists(map_path):
            try:
                self.faiss_indices[model_name] = faiss.read_index(index_path, faiss.IO_FLAG_MMAP)
                self.doc_id_maps[model_name] = np.load(map_path)
                print(f"Loaded FAISS index for {model_name} (mmap)")
            except Exception as e:
                print(f"Error loading index for {model_name}: {e}")
        else:
            # print(f"Warning: Index or map for {model_name} not found.")
            pass

    def get_embedding_model(self, model_name: str):
        if model_name not in self.embedding_models:
            print(f"Initializing embedding model: {model_name}")
            if model_name == "codebert":
                self.embedding_models[model_name] = CodeBERTEmbedding()
            elif model_name == "jina":
                self.embedding_models[model_name] = JinaEmbedding()
            else:
                return None
        return self.embedding_models[model_name]

# Global instance
resource_manager = ResourceManager()
