# Hybrid RAG System for Saphira AI Compliance Documents

This repository contains a prototype hybrid Retrieval-Augmented Generation (RAG) system built with LlamaIndex. The goal is to process structured documents (e.g., compliance reports) for semantic similarity searches and explicit section queries, grounding responses in the document to prevent hallucinations. It supports fallback from metadata-based retrieval to semantic for robustness.

## Table of Contents with Explanations

- **main.py**: The core script implementing the RAG pipeline. It ingests a Markdown document from the data folder, splits it into section-based nodes using a custom H2 splitter, adds metadata tags (e.g., 'section': '2'), builds a vector index for semantic search, sets up custom retrievers (metadata-first with semantic fallback), and uses a router query engine to handle queries (semantic for general, explicit for section-specific). Includes tests for verification. Run with `python main.py` after setting OPENAI_API_KEY.

- **data/**: Folder containing input documents. Currently holds `robotic_arm_compliance_report.md`, a dummy Markdown compliance report with sections (1-5) on robotic arm safety standards. Place additional docs here for ingestion; the system assumes Markdown format with "## Section X:" headers.

- **query_assessment_table.md**: A Markdown table assessing test query responses from the system. Columns include Query, Response Excerpt, Pass/Fail, Failure Type, Analysis, and Resolution. It evaluates accuracy, completeness, and hallucination across semantic, explicit, and edge cases (e.g., non-existent sections), highlighting issues like incompleteness or vague outputs.

- **rag_extension_writeup.md**: A writeup on extending the pipeline for complex documents (e.g., long PDFs, nested hierarchies). Discusses challenges (section ID, long chunks), strategies (hierarchical parsing, metadata propagation), and pseudocode for advanced ingestion (tree-based splitting with sub-chunking for oversized sections). Useful for scaling beyond simple Markdown.

For setup: Install LlamaIndex (`pip install llama-index llama-index-embeddings-openai`), set OPENAI_API_KEY, and run main.py. Expand for production by adding logging or API wrappers.