# Global backend settings
# Source this file before starting the backend service.

# Search / web retrieval
export RESEARCH_MAX_RESULTS=3
export RESEARCH_SUMMARY_MODEL="gpt-4o"
export RESEARCH_SUMMARY_TEMPERATURE=0

# Query embedding / local retrieval
export QUERY_EMBEDDING_MODEL="BAAI/bge-base-zh-v1.5"
export QUERY_DB_PATH="./data/local_db_query"

# Main chat model
export CHAT_MODEL_NAME="gpt-4o"
export CHAT_MODEL_TEMPERATURE=0
export CHAT_MODEL_MAX_TOKENS=4096
export CHAT_MODEL_TIMEOUT=120

# SQL routing / planner behavior
export SQL_ROUTE_TEMPERATURE=0

# Recommendation generation
export CHAT_RECOMMENDATION_INPUT_LIMIT=500
export CHAT_RECOMMENDATION_COUNT=3

# Chat context assembly / streaming
export CHAT_HISTORY_MAX_ROUNDS=6
export CHAT_FILE_TEXT_MAX_CHARS=12000
export CHAT_FILE_HISTORY_SNIPPET_CHARS=3000
export CHAT_THINKING_CHUNK_SIZE=48

# RAG model settings
export RAG_LLM_MODEL="gpt-4o"
export RAG_LLM_TEMPERATURE=0.1
export RAG_EMBED_MODEL="text-embedding-3-small"

# SQL tool LLM settings
# DB_LLM_API_KEY is optional; if unset, code falls back to OPENAI_API_KEY.
export DB_LLM_BASE_URL="https://api.claudeshop.top/v1"
export DB_LLM_MODEL_NAME="gpt-4o"
export DB_LLM_SELECTOR_TEMPERATURE=0.1
export DB_LLM_SELECTOR_MAX_TOKENS=1024
export DB_LLM_GENERATE_TEMPERATURE=0.0
export DB_LLM_GENERATE_MAX_TOKENS=1024
export DB_LLM_REVISE_TEMPERATURE=0.0
export DB_MAX_REVISE_ROUND=4

# MySQL connection used by sql_tool
export DB_MYSQL_HOST="183.69.138.62"
export DB_MYSQL_PORT=33666
export DB_MYSQL_USER="hagongda"
export DB_MYSQL_PASSWORD='ha.G/o[tEst]n%gD*a'
export DB_MYSQL_NAME="r_d_test"
