import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


class MilvusNotReadyError(RuntimeError):
    pass


@dataclass
class MilvusSettings:
    uri: str
    token: str
    db_name: str
    collection: str
    consistency_level: str
    index_type: str
    metric_type: str
    embed_model: str
    embed_device: str
    batch_size: int
    top_k: int
    score_threshold: float
    chunk_size: int
    chunk_overlap: int

    @classmethod
    def from_env(cls) -> "MilvusSettings":
        return cls(
            uri=os.getenv("KL_MILVUS_URI", "/tmp/klclab_milvus.db"),
            token=os.getenv("KL_MILVUS_TOKEN", ""),
            db_name=os.getenv("KL_MILVUS_DB_NAME", "default"),
            collection=os.getenv("MILVUS_COLLECTION", "klclab_kb_chunks"),
            consistency_level=os.getenv("MILVUS_CONSISTENCY_LEVEL", "Bounded"),
            index_type=os.getenv("MILVUS_INDEX_TYPE", "AUTOINDEX"),
            metric_type=os.getenv("MILVUS_METRIC_TYPE", "COSINE"),
            embed_model=os.getenv("RAG_EMBED_MODEL", "BAAI/bge-small-zh-v1.5"),
            embed_device=os.getenv("RAG_EMBED_DEVICE", "cpu"),
            batch_size=_env_int("MILVUS_BATCH_SIZE", 32),
            top_k=_env_int("MILVUS_TOP_K", 5),
            score_threshold=_env_float("MILVUS_SCORE_THRESHOLD", 0.35),
            chunk_size=_env_int("MILVUS_CHUNK_SIZE", 800),
            chunk_overlap=_env_int("MILVUS_CHUNK_OVERLAP", 120),
        )


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return int(default)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return float(default)


def _quote(value: str) -> str:
    safe = str(value).replace('\\', '\\\\').replace('"', '\\"')
    return f'"{safe}"'


class MilvusService:
    def __init__(self, settings: MilvusSettings | None = None):
        self.settings = settings or MilvusSettings.from_env()
        self._client = None
        self._embed_model = None
        self._embed_dim = None

    def _ensure_runtime(self):
        try:
            from pymilvus import DataType, MilvusClient
        except Exception as exc:
            raise MilvusNotReadyError(
                f"pymilvus 运行时不可用: {exc}"
            ) from exc
        return DataType, MilvusClient

    def _get_client(self):
        if self._client is not None:
            return self._client
        _, client_cls = self._ensure_runtime()
        kwargs = {"uri": self.settings.uri}
        if self.settings.token:
            kwargs["token"] = self.settings.token
        if self.settings.db_name:
            kwargs["db_name"] = self.settings.db_name
        self._client = client_cls(**kwargs)
        return self._client

    def _get_embed_model(self):
        if self._embed_model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except Exception as exc:
                raise MilvusNotReadyError(f"本地 embedding 运行时不可用: {exc}") from exc
            model_ref = self._resolve_embed_model_ref()
            self._embed_model = SentenceTransformer(model_ref, device=self.settings.embed_device)
        return self._embed_model

    def _resolve_embed_model_ref(self) -> str:
        model_ref = (self.settings.embed_model or "").strip()
        if not model_ref:
            raise MilvusNotReadyError("未配置本地 embedding 模型，请设置 RAG_EMBED_MODEL。")
        if Path(model_ref).exists():
            return model_ref
        try:
            from modelscope import snapshot_download
        except Exception as exc:
            raise MilvusNotReadyError(
                f"embedding 模型 {model_ref} 不是本地路径，且 modelscope 不可用: {exc}"
            ) from exc
        try:
            return snapshot_download(model_id=model_ref)
        except Exception as exc:
            raise MilvusNotReadyError(
                f"无法通过 modelscope 下载 embedding 模型 {model_ref}: {exc}"
            ) from exc

    def _get_embed_dim(self) -> int:
        if self._embed_dim is None:
            model = self._get_embed_model()
            dim = model.get_sentence_embedding_dimension()
            if not dim:
                dim = len(model.encode(["test"], normalize_embeddings=True)[0])
            self._embed_dim = int(dim)
        return self._embed_dim

    def ensure_collection(self):
        data_type, _ = self._ensure_runtime()
        client = self._get_client()
        if client.has_collection(self.settings.collection):
            return
        dim = self._get_embed_dim()
        try:
            schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
            schema.add_field(field_name="id", datatype=data_type.VARCHAR, is_primary=True, max_length=128)
            schema.add_field(field_name="vector", datatype=data_type.FLOAT_VECTOR, dim=dim)
            schema.add_field(field_name="kb_id", datatype=data_type.VARCHAR, max_length=128)
            schema.add_field(field_name="kb_name", datatype=data_type.VARCHAR, max_length=256)
            schema.add_field(field_name="scope", datatype=data_type.VARCHAR, max_length=128)
            schema.add_field(field_name="belong_to", datatype=data_type.VARCHAR, max_length=256)
            schema.add_field(field_name="allowed_users", datatype=data_type.VARCHAR, max_length=2048)
            schema.add_field(field_name="enabled", datatype=data_type.BOOL)
            schema.add_field(field_name="file_name", datatype=data_type.VARCHAR, max_length=256)
            schema.add_field(field_name="rel_path", datatype=data_type.VARCHAR, max_length=512)
            schema.add_field(field_name="chunk_no", datatype=data_type.INT64)
            schema.add_field(field_name="content", datatype=data_type.VARCHAR, max_length=65535)
            index_params = client.prepare_index_params()
            index_params.add_index(field_name="vector", index_type=self.settings.index_type, metric_type=self.settings.metric_type)
            client.create_collection(collection_name=self.settings.collection, schema=schema, index_params=index_params, consistency_level=self.settings.consistency_level)
        except Exception:
            client.create_collection(
                collection_name=self.settings.collection,
                dimension=dim,
                primary_field_name="id",
                vector_field_name="vector",
                id_type="string",
                metric_type=self.settings.metric_type,
                auto_id=False,
                consistency_level=self.settings.consistency_level,
                enable_dynamic_field=True,
            )

    def chunk_text(self, text: str) -> list[str]:
        compact = re.sub(r"\s+", " ", (text or "")).strip()
        if not compact:
            return []
        chunk_size = max(200, self.settings.chunk_size)
        overlap = max(0, min(self.settings.chunk_overlap, chunk_size // 2))
        step = max(1, chunk_size - overlap)
        return [compact[start:start + chunk_size] for start in range(0, len(compact), step)]

    def embed_texts(self, texts: Iterable[str]) -> list[list[float]]:
        clean_texts = [text.strip() for text in texts if text and text.strip()]
        if not clean_texts:
            return []
        model = self._get_embed_model()
        vectors = model.encode(
            clean_texts,
            batch_size=max(1, self.settings.batch_size),
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [vector.tolist() for vector in vectors]

    def build_chunk_records(self, *, kb: dict[str, Any], file_name: str, rel_path: str, text: str) -> list[dict[str, Any]]:
        chunks = self.chunk_text(text)
        if not chunks:
            return []
        vectors = self.embed_texts(chunks)
        allowed_users = kb.get("users", []) or []
        allowed_names = [item.get("name", "").strip() for item in allowed_users if isinstance(item, dict) and item.get("name")]
        allowed_user_expr = "|" + "|".join(allowed_names) + "|" if allowed_names else "|all|"
        category = kb.get("category", "")
        owner_info = kb.get("owner_info", "")
        owner_parts = owner_info.split("/") if owner_info else []
        if "企业" in category:
            belong_to = owner_parts[0] if owner_parts else ""
        elif "部门" in category:
            belong_to = owner_parts[-1] if owner_parts else ""
        else:
            belong_to = kb.get("users", [{}])[0].get("name", "") if kb.get("users") else ""
        records = []
        for index, (chunk, vector) in enumerate(zip(chunks, vectors)):
            raw_id = f"{kb.get('id', '')}::{rel_path}::{index}"
            chunk_id = hashlib.md5(raw_id.encode("utf-8")).hexdigest()
            records.append({
                "id": chunk_id,
                "vector": vector,
                "kb_id": kb.get("id", ""),
                "kb_name": kb.get("name", ""),
                "scope": category,
                "belong_to": belong_to,
                "allowed_users": allowed_user_expr,
                "enabled": bool(kb.get("enabled", True)),
                "file_name": file_name,
                "rel_path": rel_path,
                "chunk_no": index,
                "content": chunk,
            })
        return records

    def upsert_records(self, records: list[dict[str, Any]]):
        if not records:
            return
        self.ensure_collection()
        client = self._get_client()
        try:
            client.upsert(collection_name=self.settings.collection, data=records)
        except Exception:
            ids = [item["id"] for item in records if item.get("id")]
            if ids:
                client.delete(collection_name=self.settings.collection, filter=f"id in [{', '.join(_quote(item) for item in ids)}]")
            client.insert(collection_name=self.settings.collection, data=records)

    def delete_by_kb(self, kb_id: str):
        self.ensure_collection()
        self._get_client().delete(collection_name=self.settings.collection, filter=f"kb_id == {_quote(kb_id)}")

    def delete_by_files(self, kb_id: str, filenames: list[str]):
        if not filenames:
            return
        self.ensure_collection()
        self._get_client().delete(collection_name=self.settings.collection, filter=f"kb_id == {_quote(kb_id)} and file_name in [{', '.join(_quote(name) for name in filenames)}]")

    def build_permission_filter(self, user: dict[str, Any]) -> str:
        name = (user.get("name") or "").strip()
        company = (user.get("company") or "").strip()
        department = (user.get("department") or "").strip()
        clauses = ['scope == "基础知识库"']
        if company:
            clauses.append(f"belong_to == {_quote(company)}")
        if department:
            clauses.append(f"belong_to == {_quote(department)}")
        if name:
            clauses.append(f'allowed_users like "%|{name}|%"')
        return "enabled == true and (" + " or ".join(clauses) + ")"

    def search(self, *, question: str, user: dict[str, Any], top_k: int | None = None) -> list[dict[str, Any]]:
        self.ensure_collection()
        vectors = self.embed_texts([question])
        if not vectors:
            return []
        hits = self._get_client().search(collection_name=self.settings.collection, data=vectors, limit=top_k or self.settings.top_k, filter=self.build_permission_filter(user), output_fields=["kb_id", "kb_name", "scope", "belong_to", "file_name", "rel_path", "chunk_no", "content"])
        results = []
        for item in hits[0] if hits else []:
            entity = item.get("entity") or {}
            results.append({
                "score": item.get("distance"),
                "kb_id": entity.get("kb_id", ""),
                "kb_name": entity.get("kb_name", ""),
                "scope": entity.get("scope", ""),
                "belong_to": entity.get("belong_to", ""),
                "file_name": entity.get("file_name", ""),
                "rel_path": entity.get("rel_path", ""),
                "chunk_no": entity.get("chunk_no", 0),
                "content": entity.get("content", ""),
            })
        return results


def build_milvus_service_from_env() -> MilvusService:
    return MilvusService(MilvusSettings.from_env())
