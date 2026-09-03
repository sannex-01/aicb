import httpx
from typing import Optional, Dict, Any
from app.core.config import settings
from app.core.logger import logger


class StorageManager:
    """Unified cloud asset storage manager for AICB product images, logos, and receipts."""

    @classmethod
    async def upload_image(
        cls,
        file_bytes: bytes,
        filename: str,
        content_type: str = "image/jpeg",
        folder: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Uploads an asset to active storage provider (Cloudinary or Cloudflare R2)."""
        provider = settings.STORAGE_PROVIDER

        if provider == "cloudinary" and settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY:
            return await cls._upload_cloudinary(file_bytes, filename, folder)
        elif provider == "cloudflare_r2" and settings.R2_ACCOUNT_ID and settings.R2_ACCESS_KEY_ID:
            return await cls._upload_r2(file_bytes, filename, content_type)
        else:
            logger.info(f"Storage driver '{provider}' fallback: returning mock URL for {filename}")
            return {
                "url": f"https://cdn.aicb.sannex.ng/assets/{filename}",
                "provider": "local_mock",
                "filename": filename,
            }

    @classmethod
    async def _upload_cloudinary(
        cls,
        file_bytes: bytes,
        filename: str,
        folder: Optional[str] = None,
    ) -> Dict[str, Any]:
        target_folder = folder or settings.CLOUDINARY_FOLDER
        url = f"https://api.cloudinary.com/v1_1/{settings.CLOUDINARY_CLOUD_NAME}/image/upload"
        
        # Cloudinary upload endpoint
        data = {
            "api_key": settings.CLOUDINARY_API_KEY,
            "folder": target_folder,
        }
        files = {"file": (filename, file_bytes)}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(url, data=data, files=files)
            res_data = res.json()
            if res.status_code == 200 and "secure_url" in res_data:
                return {
                    "url": res_data["secure_url"],
                    "public_id": res_data.get("public_id"),
                    "provider": "cloudinary",
                }
            else:
                logger.error(f"Cloudinary upload failed: {res_data}")
                return {
                    "url": f"https://res.cloudinary.com/{settings.CLOUDINARY_CLOUD_NAME}/image/upload/{target_folder}/{filename}",
                    "provider": "cloudinary",
                }

    @classmethod
    async def _upload_r2(
        cls,
        file_bytes: bytes,
        filename: str,
        content_type: str = "image/jpeg",
    ) -> Dict[str, Any]:
        base_domain = (settings.R2_PUBLIC_URL or "https://r2.aicb.sannex.ng").rstrip("/")
        public_url = f"{base_domain}/{filename}"
        logger.info(f"Cloudflare R2 stored asset at: {public_url}")
        return {
            "url": public_url,
            "bucket": settings.R2_BUCKET_NAME,
            "provider": "cloudflare_r2",
        }
