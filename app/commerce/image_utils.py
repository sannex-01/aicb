import io
from PIL import Image

def optimize_image(file_bytes: bytes, max_dimension: int = 1000, quality: int = 80) -> bytes:
    """Optimizes an image by resizing it proportionally if it exceeds max_dimension, and compressing it."""
    try:
        image = Image.open(io.BytesIO(file_bytes))

        # Convert to RGB if it's RGBA (for JPEG compatibility, though we can save as WEBP or JPEG)
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        # Resize if too large
        if max(image.width, image.height) > max_dimension:
            # Thumbnail preserves aspect ratio
            image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

        output = io.BytesIO()
        # Save as JPEG with optimized compression
        image.save(output, format="JPEG", quality=quality, optimize=True)
        return output.getvalue()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Image optimization failed: {e}. Returning original bytes.")
        return file_bytes
