"""
Milvus vector database client for semantic search.
"""
from typing import List, Dict, Any, Optional
from pymilvus import (
    connections,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility
)
from app.config import get_settings

settings = get_settings()


class MilvusClient:
    """Milvus vector database client wrapper."""
    
    def __init__(self):
        """Initialize Milvus connection."""
        self.collection_name = settings.MILVUS_COLLECTION_NAME
        self.dimension = settings.EMBEDDING_DIMENSION
        self.collection: Optional[Collection] = None
        self._connect()
    
    def _connect(self):
        """Connect to Milvus server."""
        try:
            connections.connect(
                alias="default",
                host=settings.MILVUS_HOST,
                port=settings.MILVUS_PORT
            )
            print(f"Connected to Milvus at {settings.MILVUS_HOST}:{settings.MILVUS_PORT}")
        except Exception as e:
            print(f"Failed to connect to Milvus: {e}")
    
    def create_collection(self):
        """Create collection if it doesn't exist."""
        try:
            if utility.has_collection(self.collection_name):
                print(f"Collection {self.collection_name} already exists")
                self.collection = Collection(self.collection_name)
                return
            
            # Define schema
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="document_id", dtype=DataType.INT64),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dimension)
            ]
            
            schema = CollectionSchema(
                fields=fields,
                description="Document embeddings for semantic search"
            )
            
            # Create collection
            self.collection = Collection(
                name=self.collection_name,
                schema=schema
            )
            
            # Create index
            index_params = {
                "metric_type": "L2",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 1024}
            }
            self.collection.create_index(
                field_name="embedding",
                index_params=index_params
            )
            
            print(f"Collection {self.collection_name} created successfully")
        except Exception as e:
            print(f"Failed to create collection: {e}")
    
    def insert(self, document_ids: List[int], contents: List[str], embeddings: List[List[float]]) -> bool:
        """
        Insert vectors into collection.
        
        Args:
            document_ids: List of document IDs
            contents: List of document contents
            embeddings: List of embedding vectors
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.collection:
                self.collection = Collection(self.collection_name)
            
            entities = [
                document_ids,
                contents,
                embeddings
            ]
            
            self.collection.insert(entities)
            self.collection.flush()
            
            return True
        except Exception as e:
            print(f"Failed to insert vectors: {e}")
            return False
    
    def search(
        self,
        query_embeddings: List[List[float]],
        top_k: int = 5,
        filters: Optional[str] = None
    ) -> List[List[Dict[str, Any]]]:
        """
        Search for similar vectors.
        
        Args:
            query_embeddings: Query embedding vectors
            top_k: Number of results to return
            filters: Optional filter expression
            
        Returns:
            List of search results
        """
        try:
            if not self.collection:
                self.collection = Collection(self.collection_name)
            
            self.collection.load()
            
            search_params = {
                "metric_type": "L2",
                "params": {"nprobe": 10}
            }
            
            results = self.collection.search(
                data=query_embeddings,
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=filters,
                output_fields=["document_id", "content"]
            )
            
            # Format results
            formatted_results = []
            for hits in results:
                hit_list = []
                for hit in hits:
                    hit_list.append({
                        "id": hit.id,
                        "document_id": hit.entity.get("document_id"),
                        "content": hit.entity.get("content"),
                        "distance": hit.distance
                    })
                formatted_results.append(hit_list)
            
            return formatted_results
        except Exception as e:
            print(f"Failed to search vectors: {e}")
            return []
    
    def delete(self, expr: str) -> bool:
        """
        Delete vectors by expression.
        
        Args:
            expr: Delete expression (e.g., "document_id in [1, 2, 3]")
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.collection:
                self.collection = Collection(self.collection_name)
            
            self.collection.delete(expr)
            return True
        except Exception as e:
            print(f"Failed to delete vectors: {e}")
            return False
    
    def drop_collection(self):
        """Drop the collection."""
        try:
            if utility.has_collection(self.collection_name):
                utility.drop_collection(self.collection_name)
                print(f"Collection {self.collection_name} dropped")
        except Exception as e:
            print(f"Failed to drop collection: {e}")
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get collection statistics.
        
        Returns:
            Collection statistics
        """
        try:
            if not self.collection:
                self.collection = Collection(self.collection_name)
            
            stats = self.collection.num_entities
            return {"num_entities": stats}
        except Exception as e:
            print(f"Failed to get collection stats: {e}")
            return {}
    
    def close(self):
        """Close Milvus connection."""
        try:
            connections.disconnect("default")
        except Exception as e:
            print(f"Failed to disconnect from Milvus: {e}")


# Global client instance
milvus_client = MilvusClient()
