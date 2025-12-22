#!/usr/bin/env python3
"""
Image Downloader for Clientbook Database

Downloads images from URLs in the database and stores them locally.
Creates a sibling directory to the database file to store images.
Images are named by their content hash to avoid duplicates.
"""

import argparse
import hashlib
import os
import sqlite3
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse
from tqdm import tqdm


def create_image_downloads_table(conn):
    """Create the image_downloads table if it doesn't exist."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS image_downloads (
            url TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    print("✓ image_downloads table ready")


def get_image_extension(url, content_type=None, data=None):
    """Determine the image file extension."""
    # Try to determine from content type header
    if content_type:
        if 'jpeg' in content_type or 'jpg' in content_type:
            return 'jpg'
        elif 'png' in content_type:
            return 'png'
        elif 'gif' in content_type:
            return 'gif'
        elif 'webp' in content_type:
            return 'webp'
    
    # Try to determine from URL
    parsed = urlparse(url)
    path = parsed.path.lower()
    if path.endswith('.jpg') or path.endswith('.jpeg'):
        return 'jpg'
    elif path.endswith('.png'):
        return 'png'
    elif path.endswith('.gif'):
        return 'gif'
    elif path.endswith('.webp'):
        return 'webp'
    
    # Try to detect from image data magic bytes
    if data:
        if data.startswith(b'\xff\xd8\xff'):
            return 'jpg'
        elif data.startswith(b'\x89PNG\r\n\x1a\n'):
            return 'png'
        elif data.startswith(b'GIF87a') or data.startswith(b'GIF89a'):
            return 'gif'
        elif data.startswith(b'RIFF') and b'WEBP' in data[:12]:
            return 'webp'
    
    # Default to jpg
    return 'jpg'


def download_image(url, images_dir):
    """
    Download an image from URL and save it to images_dir.
    Returns the filename (hash.ext) or None if download fails.
    """
    try:
        # Download the image
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read()
            content_type = response.headers.get('Content-Type', '')
        
        # Calculate hash of content
        content_hash = hashlib.md5(data).hexdigest()
        
        # Determine extension
        extension = get_image_extension(url, content_type, data)
        
        # Create filename
        filename = f"{content_hash}.{extension}"
        filepath = images_dir / filename
        
        # Save the file
        with open(filepath, 'wb') as f:
            f.write(data)
        
        return filename
    
    except Exception as e:
        print(f"  ✗ Failed to download {url}: {e}")
        return None


def get_undownloaded_urls(conn):
    """Get list of image URLs that haven't been downloaded yet."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT i.image_url
        FROM images i
        LEFT JOIN image_downloads d ON i.image_url = d.url
        WHERE d.url IS NULL
        ORDER BY i.image_url
    """)
    return [row[0] for row in cursor.fetchall()]


def download_all_images(db_path, force=False):
    """
    Main function to download all images from the database.
    
    Args:
        db_path: Path to the SQLite database file
        force: If True, re-download all images even if already downloaded
    """
    db_path = Path(db_path)
    
    if not db_path.exists():
        print(f"Error: Database file not found: {db_path}")
        sys.exit(1)
    
    # Create images directory
    images_dir = db_path.parent / f"{db_path.name}-images"
    images_dir.mkdir(exist_ok=True)
    print(f"✓ Images directory: {images_dir}")
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    
    # Create image_downloads table
    create_image_downloads_table(conn)
    
    # Get URLs to download
    if force:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT image_url FROM images ORDER BY image_url")
        urls_to_download = [row[0] for row in cursor.fetchall()]
        print(f"Force mode: will re-download all {len(urls_to_download)} images")
    else:
        urls_to_download = get_undownloaded_urls(conn)
        print(f"Found {len(urls_to_download)} images to download")
    
    if not urls_to_download:
        print("✓ All images already downloaded!")
        conn.close()
        return
    
    # Download each image
    downloaded = 0
    failed = 0
    
    for url in tqdm(urls_to_download, desc="Downloading images", unit="img"):
        filename = download_image(url, images_dir)
        
        if filename:
            # Record the download
            cursor = conn.cursor()
            if force:
                cursor.execute("""
                    INSERT OR REPLACE INTO image_downloads (url, filename)
                    VALUES (?, ?)
                """, (url, filename))
            else:
                cursor.execute("""
                    INSERT INTO image_downloads (url, filename)
                    VALUES (?, ?)
                """, (url, filename))
            conn.commit()
            
            downloaded += 1
        else:
            failed += 1
    
    conn.close()
    
    print(f"\n{'='*60}")
    print(f"Download complete!")
    print(f"  ✓ Successfully downloaded: {downloaded}")
    if failed > 0:
        print(f"  ✗ Failed: {failed}")
    print(f"  📁 Images saved to: {images_dir}")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description="Download images from Clientbook database"
    )
    parser.add_argument(
        'database',
        nargs='?',
        default='clientbook.db',
        help='Path to SQLite database file (default: clientbook.db)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Re-download all images even if already downloaded'
    )
    
    args = parser.parse_args()
    
    download_all_images(args.database, force=args.force)


if __name__ == '__main__':
    main()
