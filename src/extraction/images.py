"""Photo loading: filesystem → base64 image blocks for the vision API."""
from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Literal

from anthropic.types import ImageBlockParam

logger = logging.getLogger(__name__)

# The SDK types media_type as a Literal, not a str: annotate or the values widen to str.
_ImageMediaType = Literal["image/jpeg", "image/png", "image/gif", "image/webp"]

_MEDIA_TYPES: dict[str, _ImageMediaType] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def image_block(path: Path) -> ImageBlockParam:
    """Encode one photo as a base64 image block.

    Photos are deliberately not downscaled: Opus 4.8 reads up to 2576 px on the
    long edge and detail matters on handwriting (~2700 tokens for a WhatsApp photo).
    """
    media_type = _MEDIA_TYPES.get(path.suffix.lower())
    if media_type is None:
        raise ValueError(
            f"{path.name}: format not supported by the vision API "
            f"(accepted: {', '.join(sorted(_MEDIA_TYPES))}). "
            "WhatsApp photos arrive as .jpg; a .heic must be converted first."
        )
    raw = path.read_bytes()
    logger.info("Photo encoded: %s (%s, %.0f KB)", path.name, media_type, len(raw) / 1024)
    data = base64.standard_b64encode(raw).decode()
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}
