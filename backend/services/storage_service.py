import os
from datetime import timedelta

from minio import Minio
from minio.error import MinioException, S3Error


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
                f"MinIO 不可用或存储桶初始化失败: endpoint={self.endpoint}, bucket={self.bucket_name}, reason={exc}"
            ) from exc

    def upload_file_obj(self, file_obj, object_name: str, content_type: str = "application/octet-stream"):
        try:
            self.ensure_ready()
            file_obj.seek(0, os.SEEK_END)
            size = file_obj.tell()
            file_obj.seek(0)
            self.client.put_object(
                self.bucket_name,
                object_name,
                file_obj,
                size,
                content_type=content_type,
            )
            return True
        except (S3Error, MinioException, OSError, ValueError) as exc:
            print(f"上传文件失败 [{object_name}]: {exc}")
            return False
        except Exception as exc:
            print(f"上传文件失败 [{object_name}]: {exc}")
            return False

    def download_file(self, object_name: str, local_path: str):
        try:
            self.ensure_ready()
            self.client.fget_object(self.bucket_name, object_name, local_path)
            return True
        except (S3Error, MinioException, OSError, ValueError) as exc:
            print(f"下载文件失败 [{object_name}]: {exc}")
            return False
        except Exception as exc:
            print(f"下载文件失败 [{object_name}]: {exc}")
            return False

    def read_file_bytes(self, object_name: str) -> bytes:
        response = None
        try:
            self.ensure_ready()
            response = self.client.get_object(self.bucket_name, object_name)
            return response.read()
        except (S3Error, MinioException, OSError, ValueError) as exc:
            print(f"读取文件内容失败 [{object_name}]: {exc}")
            return b""
        except Exception as exc:
            print(f"读取文件内容失败 [{object_name}]: {exc}")
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
        except (S3Error, MinioException, OSError, ValueError) as exc:
            print(f"删除文件失败 [{object_name}]: {exc}")
            return False
        except Exception as exc:
            print(f"删除文件失败 [{object_name}]: {exc}")
            return False

    def delete_files_by_prefix(self, prefix: str):
        try:
            self.ensure_ready()
            objects = list(self.client.list_objects(self.bucket_name, prefix=prefix, recursive=True))
            for obj in objects:
                self.client.remove_object(self.bucket_name, obj.object_name)
            return True
        except (S3Error, MinioException, OSError, ValueError) as exc:
            print(f"批量删除文件失败 [{prefix}]: {exc}")
            return False
        except Exception as exc:
            print(f"批量删除文件失败 [{prefix}]: {exc}")
            return False

    def list_files(self, prefix: str):
        try:
            self.ensure_ready()
            return [
                {
                    "object_name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified,
                }
                for obj in self.client.list_objects(self.bucket_name, prefix=prefix, recursive=True)
            ]
        except (S3Error, MinioException, OSError, ValueError) as exc:
            print(f"列出文件失败 [{prefix}]: {exc}")
            return []
        except Exception as exc:
            print(f"列出文件失败 [{prefix}]: {exc}")
            return []

    def get_presigned_url(self, object_name: str, expires_in_days: int = 7):
        try:
            self.ensure_ready()
            return self.client.presigned_get_object(
                self.bucket_name,
                object_name,
                expires=timedelta(days=expires_in_days),
            )
        except (S3Error, MinioException, OSError, ValueError) as exc:
            print(f"获取签名 URL 失败 [{object_name}]: {exc}")
            return ""
        except Exception as exc:
            print(f"获取签名 URL 失败 [{object_name}]: {exc}")
            return ""


storage_service = StorageService()
