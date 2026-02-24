import hashlib
from pathlib import Path

import httpx


class IIIFError(Exception):
    pass


def fetch_iiif_image(info_url: str, cache_dir: Path) -> Path:
    """Download a IIIF image and cache it locally. Returns path to cached file."""
    if not info_url.endswith("/info.json"):
        raise IIIFError(f"URL does not end with /info.json: {info_url}")

    cache_dir.mkdir(parents=True, exist_ok=True)

    cache_key = hashlib.sha256(info_url.encode()).hexdigest()
    cached_path = cache_dir / f"{cache_key}.jpg"

    if cached_path.exists():
        return cached_path

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        # Fetch and validate info.json
        resp = client.get(info_url)
        if resp.status_code != 200:
            raise IIIFError(
                f"Failed to fetch {info_url}: HTTP {resp.status_code}"
            )
        try:
            info = resp.json()
        except Exception as e:
            raise IIIFError(f"Invalid JSON from {info_url}: {e}") from e

        if "@context" not in info and "type" not in info:
            raise IIIFError(
                f"Response from {info_url} does not appear to be a valid IIIF info.json"
            )

        # Use the id from info.json as the base URL (may include auth tokens)
        base_url = info.get("id") or info.get("@id")
        if not base_url:
            raise IIIFError(
                f"info.json from {info_url} has no 'id' or '@id' field"
            )

        # Download full image
        image_url = f"{base_url}/full/max/0/default.jpg"
        resp = client.get(image_url)
        if resp.status_code != 200:
            raise IIIFError(
                f"Failed to download image from {image_url}: HTTP {resp.status_code}"
            )

        cached_path.write_bytes(resp.content)

    return cached_path
