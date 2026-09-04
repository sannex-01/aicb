from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from app.core.rate_limit import limiter
from app.core.security import verify_dashboard_auth
from app.commerce.storage.manager import StorageManager
from app.core.logger import logger

router = APIRouter(prefix="/catalog", tags=["Catalog"])

MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8MB
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


@router.post("/upload-image")
@limiter.limit("20/minute")
async def upload_product_image(
    request: Request,
    file: UploadFile = File(...),
    _: None = Depends(verify_dashboard_auth),
) -> dict:
    """Uploads a product image to this instance's configured storage
    provider (Cloudinary or Cloudflare R2) and returns its hosted URL.
    Called by agentOS's catalog form — never exposed to end customers."""
    if not StorageManager.is_configured():
        raise HTTPException(
            status_code=400,
            detail="No storage provider is configured on this instance. Configure Cloudinary or Cloudflare R2 first.",
        )

    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {content_type}. Allowed: JPEG, PNG, WebP, GIF.")

    file_bytes = await file.read()
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {MAX_UPLOAD_BYTES // (1024 * 1024)}MB.")
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file.")

    safe_filename = (file.filename or "product-image").replace("/", "_").replace("\\", "_")

    try:
        result = await StorageManager.upload_image(
            file_bytes=file_bytes,
            filename=safe_filename,
            content_type=content_type,
            folder="products",
        )
        return {"url": result["url"], "provider": result.get("provider")}
    except Exception as e:
        logger.error(f"Product image upload failed: {e}")
        raise HTTPException(status_code=502, detail="Image upload to storage provider failed.")
