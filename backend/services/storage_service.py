import os
from minio import Minio
from minio.error import S3Error
from datetime import timedelta

class StorageService:
    def __init__(self):
        self.endpoint = os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000")
        self.access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
        self.secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
        self.bucket_name = os.getenv("MINIO_BUCKET_NAME", "xintuoyin-data")

        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure,
        )
        self._ensure_bucket()

    def _ensure_bucket(self):
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
        except S3Error as e:
            print(f"MinIO 存储桶检查/创建失败: {e}")

    def upload_file_obj(self, file_obj, object_name: str, content_type: str = "application/octet-stream"):
        """将文件对象流式上传到 MinIO"""
        try:
            # 移动指针到末尾获取文件大小
            file_obj.seek(0, os.SEEK_END)
            size = file_obj.tell()
            file_obj.seek(0)
            self.client.put_object(
                self.bucket_name,
                object_name,
                file_obj,
                size,
                content_type=content_type
            )
            return True
        except S3Error as e:
            print(f"上传文件失败 [{object_name}]: {e}")
            return False

    def download_file(self, object_name: str, local_path: str):
        """将文件从 MinIO 下载到本地路径"""
        try:
            self.client.fget_object(self.bucket_name, object_name, local_path)
            return True
        except S3Error as e:
            print(f"下载文件失败 [{object_name}]: {e}")
            return False

    def read_file_bytes(self, object_name: str) -> bytes:
        """从 MinIO 直接读取文件内容为 bytes"""
        try:
            response = self.client.get_object(self.bucket_name, object_name)
            return response.read()
        except S3Error as e:
            print(f"读取文件内容失败 [{object_name}]: {e}")
            return b""
        finally:
            if 'response' in locals() and hasattr(response, 'close'):
                response.close()
                response.release_conn()

    def delete_file(self, object_name: str):
        """从 MinIO 删除单个对象"""
        try:
            self.client.remove_object(self.bucket_name, object_name)
            return True
        except S3Error as e:
            print(f"删除文件失败 [{object_name}]: {e}")
            return False

    def delete_files_by_prefix(self, prefix: str):
        """批量删除指定前缀的所有对象"""
        try:
            objects_to_delete = self.client.list_objects(self.bucket_name, prefix=prefix, recursive=True)
            for obj in objects_to_delete:
                self.client.remove_object(self.bucket_name, obj.object_name)
            return True
        except S3Error as e:
            print(f"批量删除文件失败 [{prefix}]: {e}")
            return False

    def list_files(self, prefix: str):
        """列出指定前缀的所有对象信息"""
        try:
            objects = self.client.list_objects(self.bucket_name, prefix=prefix, recursive=True)
            return [
                {
                    "object_name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified
                }
                for obj in objects
            ]
        except S3Error as e:
            print(f"列出文件失败 [{prefix}]: {e}")
            return []

    def get_presigned_url(self, object_name: str, expires_in_days: int = 7):
        """获取带有签名的临时可访问 URL"""
        try:
            return self.client.presigned_get_object(
                self.bucket_name, 
                object_name, 
                expires=timedelta(days=expires_in_days)
            )
        except S3Error as e:
            print(f"获取签名 URL 失败 [{object_name}]: {e}")
            return ""

storage_service = StorageService()
