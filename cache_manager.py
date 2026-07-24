
import os
import hashlib
import json
import shutil

CACHE_DIR = os.path.join(os.getcwd(), ".pdfx_cache")

def _get_pdf_hash(pdf_path: str) -> str:
    """Generates a SHA256 hash of the PDF file content."""
    hasher = hashlib.sha256()
    with open(pdf_path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()

def get_cached_content(pdf_path: str) -> dict or None:
    """Retrieves cached content for a given PDF path if available and valid."""
    pdf_hash = _get_pdf_hash(pdf_path)
    cache_entry_dir = os.path.join(CACHE_DIR, pdf_hash)
    cache_file = os.path.join(cache_entry_dir, "content.json")

    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
            # Optionally, add a check for cache freshness or versioning here
            print(f"Cache hit for {pdf_path}")
            return cached_data
        except Exception as e:
            print(f"Error reading cache for {pdf_path}: {e}")
            # Invalidate corrupted cache entry
            shutil.rmtree(cache_entry_dir, ignore_errors=True)
    print(f"Cache miss for {pdf_path}")
    return None

def set_cached_content(pdf_path: str, content: dict):
    """Stores processed content in the cache for a given PDF path."""
    pdf_hash = _get_pdf_hash(pdf_path)
    cache_entry_dir = os.path.join(CACHE_DIR, pdf_hash)
    os.makedirs(cache_entry_dir, exist_ok=True)
    cache_file = os.path.join(cache_entry_dir, "content.json")

    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
        print(f"Content cached for {pdf_path}")
    except Exception as e:
        print(f"Error writing cache for {pdf_path}: {e}")
        shutil.rmtree(cache_entry_dir, ignore_errors=True)

# Ensure cache directory exists on startup
os.makedirs(CACHE_DIR, exist_ok=True)
