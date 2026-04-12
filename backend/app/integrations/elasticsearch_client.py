import os
import logging
from elasticsearch import Elasticsearch, exceptions

logger = logging.getLogger(__name__)

class ESClient:
    def __init__(self):
        url = os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")
        self.client = Elasticsearch(url)
        self.is_connected = False
        try:
            if self.client.ping():
                self.is_connected = True
                logger.info("Connected to Elasticsearch at %s", url)
            else:
                logger.warning("Could not ping Elasticsearch at %s", url)
        except Exception as e:
            logger.warning("Elasticsearch connection failed: %s. Global search will gracefully degrade.", str(e))

    def index_document(self, index_name: str, doc_id: str, document: dict) -> bool:
        """Upserts a document into the specified Elasticsearch index."""
        if not self.is_connected:
            return False
            
        try:
            self.client.index(index=index_name, id=doc_id, document=document)
            return True
        except exceptions.ElasticsearchException as e:
            logger.error("Error indexing document %s to %s: %s", doc_id, index_name, e)
            return False

    def search(self, index_name: str, query: str, fields: list = None, size: int = 10) -> list:
        """Performs a multi-match fuzzy search across specified fields."""
        if not self.is_connected:
            return []
            
        # Support wildcard if multiple indices requested
        if index_name == "all":
            index_name = "medassist_*"
            
        body = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": fields if fields else ["*"],
                    "fuzziness": "AUTO"
                }
            },
            "size": size
        }
        
        try:
            # We ignore_unavailable so we don't crash if the index doesn't exist yet
            res = self.client.search(index=index_name, body=body, ignore_unavailable=True)
            hits = []
            for hit in res.get("hits", {}).get("hits", []):
                source = hit.get("_source", {})
                source["_id"] = hit.get("_id")
                source["_index"] = hit.get("_index")
                hits.append(source)
            return hits
        except Exception as e:
            logger.error("Search query failed on index %s: %s", index_name, e)
            return []

# Singleton
es_client = ESClient()
