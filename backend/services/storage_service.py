import logging
import os
from datetime import timedelta

from minio import Minio
from minio.commonconfig import CopySource
from minio.error import MinioException, S3Error

logger = logging.getLogger(__name__)


class StorageNotReadyError(RuntimeError):
    pass


class StorageService:
    def __init__(self):
        self.endpoint = os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000").strip()
        self.access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
        self.secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
        self.bucket_name = os.getenv("MINIO_BUCKET_NAME", "xintuoyin-data").strip() or "xintuoyin-data"
        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure,
        )

    def ensure_ready(self):
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
        except Exception as exc:
            raise StorageNotReadyError(
                f"MinIO 不可用: endpoint={self.endpoint}, bucket={self.bucket_name}, reason={exc}"
            ) from exc

    def upload_file_obj(self, file_obj, object_name: str, content_type: str = "application/octet-stream"):
        try:
            self.ensure_ready()
            file_obj.seek(0, os.SEEK_END)
            size = file_obj.tell()
            file_obj.seek(0)
            self.client.put_object(self.bucket_name, object_name, file_obj, size, content_type=content_type)
            return True
        except Exception as exc:
            logger.error("上传文件失败 [%s]: %s", object_name, exc)
            return False

    def download_file(self, object_name: str, local_path: str):
        try:
            self.ensure_ready()
            self.client.fget_object(self.bucket_name, object_name, local_path)
            return True
        except Exception as exc:
            logger.error("下载文件失败 [%s]: %s", object_name, exc)
            return False

    def read_file_bytes(self, object_name: str) -> bytes:
        response = None
        try:
            self.ensure_ready()
            response = self.client.get_object(self.bucket_name, object_name)
            return response.read()
        except Exception as exc:
            logger.error("读取文件失败 [%s]: %s", object_name, exc)
            return b""
        finally:
            if response is not None:
                response.close()
                response.release_conn()

    def delete_file(self, object_name: str):
        try:
            self.ensure_ready()
            self.client.remove_object(self.bucket_name, object_name)
            return True
        except Exception as exc:
            logger.error("删除文件失败 [%s]: %s", object_name, exc)
            return False

    def delete_files_by_prefix(self, prefix: str):
        try:
            self.ensure_ready()
            objects = list(self.client.list_objects(self.bucket_name, prefix=prefix, recursive=True))
            for obj in objects:
                self.client.remove_object(self.bucket_name, obj.object_name)
            return True
        except Exception as exc:
            logger.error("批量删除文件失败 [%s]: %s", prefix, exc)
            return False

    def list_files(self, prefix: str):
        try:
            self.ensure_ready()
            return [
                {"object_name": obj.object_name, "size": obj.size, "last_modified": obj.last_modified}
                for obj in self.client.list_objects(self.bucket_name, prefix=prefix, recursive=True)
            ]
        except Exception as exc:
            logger.error("列出文件失败 [%s]: %s", prefix, exc)
            return []

    def get_presigned_url(self, object_name: str, expires_in_days: int = 7):
        try:
            self.ensure_ready()
            return self.client.presigned_get_object(self.bucket_name, object_name, expires=timedelta(days=expires_in_days))
        except Exception as exc:
            logger.error("获取签名URL失败 [%s]: %s", object_name, exc)
            return ""

    def move_object(self, src_object: str, dst_object: str) -> bool:
        try:
            self.ensure_ready()
            self.client.copy_object(self.bucket_name, dst_object, CopySource(self.bucket_name, src_object))
            self.client.remove_object(self.bucket_name, src_object)
            return True
        except Exception as exc:
            logger.error("移动文件失败 [%s -> %s]: %s", src_object, dst_object, exc)
            return False


storage_service = StorageService()
