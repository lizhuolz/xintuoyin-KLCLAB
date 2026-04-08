# Global backend settings
# Source this file before starting the backend service.
unset http_proxy
unset https_proxy
unset all_proxy

SETTING_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_ROOT="$(cd "$SETTING_DIR/.." && pwd)"
export CUDA_VISIBLE_DEVICES=0
# Search / web retrieval
export RESEARCH_MAX_RESULTS=3
export RESEARCH_SUMMARY_MODEL="Qwen3.5-27B"
export RESEARCH_SUMMARY_TEMPERATURE=0
export RESEARCH_ENABLE_THINKING=1

# Query embedding / local retrieval
export QUERY_EMBEDDING_MODEL="BAAI/bge-base-zh-v1.5"
export QUERY_DB_PATH="${QUERY_DB_PATH:-$BACKEND_ROOT/data/local_db_query}"

# Main chat model
export CHAT_MODEL_NAME="Qwen3.5-27B"
export CHAT_MODEL_TEMPERATURE=0
export CHAT_MODEL_MAX_TOKENS=4096
export CHAT_MODEL_TIMEOUT=120
export CHAT_ENABLE_THINKING=1

# SQL routing / planner behavior
export SQL_ROUTE_TEMPERATURE=0

# Recommendation generation
export CHAT_RECOMMENDATION_INPUT_LIMIT=500
export CHAT_RECOMMENDATION_COUNT=3

# Chat context assembly / streaming
export CHAT_HISTORY_MAX_ROUNDS=6
export CHAT_FILE_TEXT_MAX_CHARS=12000
export KB_FILE_TEXT_MAX_CHARS=40000
export CHAT_FILE_HISTORY_SNIPPET_CHARS=3000
export CHAT_THINKING_CHUNK_SIZE="${CHAT_THINKING_CHUNK_SIZE:-48}"
export CHAT_STREAM_DELTA_CHARS="${CHAT_STREAM_DELTA_CHARS:-8}"
export CHAT_STREAM_CHAR_DELAY_MS="${CHAT_STREAM_CHAR_DELAY_MS:-15}"

# RAG storage backend
# milvus: enterprise vector database backend used for KB chunk indexing and retrieval.
export RAG_VECTOR_BACKEND="milvus"

# Milvus connection / collection settings
# MILVUS_URI can point to a milvus-lite local db file or a standalone Milvus endpoint.
export KL_MILVUS_URI="${KL_MILVUS_URI:-$BACKEND_ROOT/data/milvus/klclab_milvus.db}"
export KL_MILVUS_TOKEN=""
export KL_MILVUS_DB_NAME="default"
export MILVUS_COLLECTION="klclab_kb_chunks"
export MILVUS_CONSISTENCY_LEVEL="Bounded"
export MILVUS_INDEX_TYPE="AUTOINDEX"
export MILVUS_METRIC_TYPE="COSINE"

# Milvus embedding / chunking settings
# MILVUS_EMBED_DIM must match the embedding model output dimension.
export MILVUS_EMBED_DIM=512
export MILVUS_BATCH_SIZE=32
export MILVUS_TOP_K=5
export MILVUS_SCORE_THRESHOLD=0.35
export MILVUS_CHUNK_SIZE=800
export MILVUS_CHUNK_OVERLAP=120

# RAG model settings
export RAG_LLM_MODEL="Qwen3.5-27B"
export RAG_LLM_TEMPERATURE=0.1
export RAG_EMBED_MODEL="${RAG_EMBED_MODEL:-/data1/public/models/bge-small-zh-v1.5}"
export RAG_EMBED_DEVICE="cpu"

# SQL tool LLM settings
# DB_LLM_API_KEY is optional; if unset, code falls back to OPENAI_API_KEY.
export DB_LLM_BASE_URL="http://10.249.40.204:62272/v1"
export DB_LLM_MODEL_NAME="Qwen3.5-27B"
export DB_LLM_SELECTOR_TEMPERATURE=0.1
export DB_LLM_SELECTOR_MAX_TOKENS=1024
export DB_LLM_GENERATE_TEMPERATURE=0.0
export DB_LLM_GENERATE_MAX_TOKENS=1024
export DB_LLM_REVISE_TEMPERATURE=0.0
export DB_MAX_REVISE_ROUND=4
export DB_LLM_ENABLE_THINKING=1

# MySQL connection used by sql_tool
export DB_MYSQL_HOST="183.69.138.62"
export DB_MYSQL_PORT=33666
export DB_MYSQL_USER="hagongda"
export DB_MYSQL_PASSWORD='ha.G/o[tEst]n%gD*a'
export DB_MYSQL_NAME="r_d_test"


export OPENAI_API_KEY="EMPTY" # # lyq 
export OPENAI_API_BASE="http://10.249.40.204:62272/v1"
export TAVILY_API_KEY=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
export SECURITY_ENABLE_GIBBERISH=0
export SECURITY_ENABLE_NO_REFUSAL=0
export SECURITY_ENABLE_BAN_TOPICS=0
export SECURITY_ENABLE_TOXICITY=0
