import os
import re
from typing import List, Optional
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, Settings
from llama_index.core.retrievers import BaseRetriever, VectorIndexRetriever
from llama_index.core.query_engine import RetrieverQueryEngine, RouterQueryEngine
from llama_index.core.selectors import PydanticSingleSelector
from llama_index.core.tools import QueryEngineTool
from llama_index.core.vector_stores import MetadataFilter, FilterOperator
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.callbacks import CallbackManager
from llama_index.core.text_splitter import TokenTextSplitter
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.core.schema import TextNode, NodeWithScore 

# Set up OpenAI API key (loaded from environment variable)
if not os.environ.get("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY environment variable not set. Please set it using `export OPENAI_API_KEY='sk-...'`")

# Configure global settings for LlamaIndex (OpenAI for embeddings and LLM)
Settings.llm = OpenAI(model="gpt-3.5-turbo")
Settings.embed_model = OpenAIEmbedding(model="text-embedding-ada-002")

# Custom Metadata Retriever with Semantic Fallback
class MetadataRetriever(BaseRetriever):
    def __init__(self, nodes: List, vector_retriever: VectorIndexRetriever, metadata_key: str = "section"):
        super().__init__()
        self.nodes = nodes  # All ingested nodes
        self.vector_retriever = vector_retriever  # Fallback semantic retriever
        self.metadata_key = metadata_key

    def _retrieve(self, query_bundle):
        query_str = query_bundle.query_str
        # Extract section number from query (e.g., "section 2")
        section_match = re.search(r"section\s+(\d+)", query_str, re.IGNORECASE)
        section_number = section_match.group(1) if section_match else None

        if section_number:
            # Metadata-only filtering: Find nodes matching exact section
            filtered_nodes = [node for node in self.nodes if node.metadata.get(self.metadata_key) == section_number]
            if filtered_nodes:
                # Wrap in NodeWithScore with dummy score for compatibility
                return [NodeWithScore(node=node, score=1.0) for node in filtered_nodes[:3]]   # Limit to top 3 if many
        # Fallback to semantic (vector) if no metadata match or no section in query
        return self.vector_retriever.retrieve(query_bundle)

# Custom splitter to split on H2 headers (## )
class H2TextSplitter(TokenTextSplitter):
    def split_text(self, text: str) -> List[str]:
        # Split on ## followed by any text, keeping the header with the section
        sections = re.split(r'(##\s.*?$)', text, flags=re.MULTILINE)
        chunks = []
        current_chunk = ""
        for part in sections:
            if part.startswith("##"):
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = part
            else:
                current_chunk += part
        if current_chunk:
            chunks.append(current_chunk.strip())
        return chunks

# Step 1: Ingest and Chunk Data (prerequisite for indexing)
# Load the dummy document from ./data
try:
    documents = SimpleDirectoryReader("./data").load_data()
except FileNotFoundError:
    raise FileNotFoundError("No documents found in ./data. Ensure robotic_arm_compliance_report.md is in the ./data folder.")

# Manually split and create nodes using custom splitter
text_splitter = H2TextSplitter()
nodes = []
for doc in documents:
    chunks = text_splitter.split_text(doc.text)
    for i, chunk in enumerate(chunks):
        node = TextNode(text=chunk, id_=f"node_{i}", metadata=doc.metadata.copy())  # Create TextNode with chunk text and base metadata
        # Add section metadata based on chunk content
        section_match = re.search(r"Section (\d+):", chunk)
        section_id = section_match.group(1) if section_match else "unknown"
        node.metadata["section"] = section_id
        nodes.append(node)

# Step 2: Build Indexes
# Vector index for semantic search (and fallback)
vector_index = VectorStoreIndex(nodes)

# Step 3: Build Retrievers
# Vector retriever for semantic/fallback
vector_retriever = VectorIndexRetriever(index=vector_index, similarity_top_k=3)

# Metadata retriever with semantic fallback (replaces BM25)
metadata_retriever = MetadataRetriever(nodes=nodes, vector_retriever=vector_retriever)

# Step 4: Set Up Router for Query Detection
# Semantic query engine
semantic_engine = RetrieverQueryEngine.from_args(retriever=vector_retriever)

# Explicit query engine (using metadata retriever with fallback)
explicit_engine = RetrieverQueryEngine.from_args(retriever=metadata_retriever)

# Define query engine tools with descriptions for the router
query_engine_tools = [
    QueryEngineTool.from_defaults(
        query_engine=semantic_engine,
        description="Use for general questions requiring semantic understanding, such as explanations or summaries of concepts."
    ),
    QueryEngineTool.from_defaults(
        query_engine=explicit_engine,
        description="Use for queries specifying a specific section, such as 'section 2' or 'section 3'."
    )
]

# Initialize router query engine
router_engine = RouterQueryEngine(
    selector=PydanticSingleSelector.from_defaults(),
    query_engine_tools=query_engine_tools
)

# Example Queries to Test
# Comprehensive Testing with Edge Cases
if __name__ == "__main__":
    test_queries = [
        # Semantic queries (general, no section)
        "Explain collision avoidance in robotic arms",
        "What are the key safety standards mentioned?",

        # Explicit section mentioned in semantic form
        "Summarize the second section",

        # Explicit queries (valid sections)
        "Summarize section 2",
        "Tell me about testing in section 4",

        # Edge cases: Non-existent section (should fallback to semantic)
        "Summarize section 6",
        "What is in section 10?",

        # Mixed: Section in query but with extra words (test regex)
        "Give a detailed explanation of Section 3 design",
        "summarize Section 2 on safety",

        # Invalid/malformed (no section or bad format, fallback to semantic)
        "Summarize section abc",
        "What is the report about?",  # No section

        # Empty/malformed query (should handle gracefully, perhaps empty response)
        "",
        "section"  # No number
    ]

    for query in test_queries:
        if query:  # Skip empty query if desired, or handle
            response = router_engine.query(query)
            print(f"Query: '{query}' Response: {response}")
        else:
            print("Query: (empty) Response: Skipped or handle as needed")