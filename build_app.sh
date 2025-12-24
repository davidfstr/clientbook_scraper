#!/bin/bash
set -e  # Exit on error

echo "=== Building Clientbook Viewer.app ==="

# Activate virtual environment
if [ ! -d "venv" ]; then
    echo "Error: venv directory not found. Please create it first."
    exit 1
fi

echo "Activating virtual environment..."
source venv/bin/activate

# Check for required files
if [ ! -f "clientbook.db" ]; then
    echo "Error: clientbook.db not found. Please run scraper.py first."
    exit 1
fi

if [ ! -d "clientbook.db-images" ]; then
    echo "Warning: clientbook.db-images directory not found."
fi

if [ ! -f "launcher.py" ]; then
    echo "Error: launcher.py not found."
    exit 1
fi

if [ ! -f "viewer.py" ]; then
    echo "Error: viewer.py not found."
    exit 1
fi

# Build the .app with PyInstaller
echo "Building .app bundle with PyInstaller..."
pyinstaller --windowed --name "Clientbook Viewer" launcher.py --noconfirm --log-level ERROR

# Copy database files to Frameworks directory
echo "Copying database files..."
cp clientbook.db "dist/Clientbook Viewer.app/Contents/Frameworks/clientbook.db"

if [ -d "clientbook.db-images" ]; then
    cp -R clientbook.db-images "dist/Clientbook Viewer.app/Contents/Frameworks/clientbook.db-images"
fi

# Copy viewer.py for manual fallback
echo "Copying viewer.py for manual execution fallback..."
cp viewer.py "dist/Clientbook Viewer.app/Contents/Frameworks/viewer.py"

# Make viewer.py executable
chmod +x "dist/Clientbook Viewer.app/Contents/Frameworks/viewer.py"

# Remove intermediate build directory (only .app is needed for distribution)
echo "Cleaning up intermediate files..."
rm -rf "dist/Clientbook Viewer"

echo ""
echo "=== Build Complete! ==="
echo ""
echo "The application is ready at: dist/Clientbook Viewer.app"
echo ""
echo "To use:"
echo "  1. Double-click 'dist/Clientbook Viewer.app' to launch"
echo "  2. A window will open with a link to http://127.0.0.1:8080/"
echo "  3. Click the link to view your Clientbook archive"
echo ""
echo "Manual fallback (if .app stops working):"
echo "  cd 'dist/Clientbook Viewer.app/Contents/Frameworks'"
echo "  python3 viewer.py"
