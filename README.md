# Clientbook Archive Project

This project scrapes conversation data from Clientbook (a CRM system) and provides a local web interface to browse the archived conversations.

## Components

- **`scraper.py`** - Scrapes conversations from Clientbook using Playwright
- **`viewer.py`** - Simple web server for browsing archived conversations
- **`launcher.py`** - GUI launcher for the macOS application
- **`image_downloader.py`** - Downloads images referenced in conversations
- **`build_app.sh`** - Builds a standalone macOS .app bundle

## Quick Start

### Setup

```bash
# Create virtual environment
python3.12 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install dependencies
poetry install
```

### Scraping Data

```bash
# Activate the virtual environment (if not already active)
source venv/bin/activate

# Scrape conversations (will prompt for manual login)
python3 scraper.py

# Download images from scraped conversations
python3 image_downloader.py
```

### Viewing Data

**Option 1: Run the Python script directly**
```bash
python3 viewer.py
# Then visit http://localhost:8080 in your browser
```

**Option 2: Build and use the macOS .app bundle**
```bash
# Build the application (requires PyInstaller)
./build_app.sh

# Double-click the app to launch
open "dist/Clientbook Viewer.app"
```

## Building the macOS App

The `build_app.sh` script automates the entire build process:

1. **Builds** the .app bundle using PyInstaller
2. **Copies** the database and images into the bundle
3. **Includes** viewer.py for manual fallback if needed

```bash
./build_app.sh
```

The resulting `dist/Clientbook Viewer.app` is a standalone application that:
- Shows a simple GUI with a clickable link to the web interface
- Runs a local web server in the background
- Stops the server when you close the window
- Contains all necessary files (no external dependencies needed)

### Manual Fallback

If the .app bundle stops working after macOS updates, you can run the viewer manually:

```bash
cd "dist/Clientbook Viewer.app/Contents/Frameworks"
python3 viewer.py
```

## Technologies

- **Python 3.12+** with standard library only (no external dependencies for viewer)
- **Playwright** for web scraping (scraper only)
- **SQLite** for data storage
- **PyInstaller** for creating the macOS .app bundle

## Database Schema

- **`clients`** - Client information (ID, name)
- **`conversations`** - Conversation metadata
- **`messages`** - Individual messages with sender info and timestamps
- **`images`** - Image attachments linked to messages

## Project History

For detailed development notes, implementation decisions, and scraper usage examples, see [plan/PLAN.md](plan/PLAN.md).

## File Structure

```
.
├── scraper.py              # Main scraper script
├── viewer.py               # Web viewer (runs standalone)
├── launcher.py             # GUI launcher for .app bundle
├── image_downloader.py     # Downloads images from S3
├── build_app.sh            # Build script for .app bundle
├── clientbook.db           # SQLite database (after scraping)
├── clientbook.db-images/   # Downloaded images (after image_downloader.py)
├── dist/
│   ├── Clientbook Viewer.app  # Built macOS application
│   └── Clientbook Viewer - README.txt
└── plan/
    ├── PLAN.md             # Detailed development notes
    └── PLAN-2.md           # .app bundling strategy notes
```
