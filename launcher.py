#!/usr/bin/env python3
"""
Clientbook Viewer Launcher - GUI wrapper for the viewer web server
"""

import tkinter as tk
from tkinter import font as tkfont
import webbrowser
import threading
import sys
import os
from pathlib import Path
from datetime import datetime

# Redirect stdout/stderr to a log file when frozen
if getattr(sys, 'frozen', False):
    log_file = Path.home() / "clientbook-viewer-debug.log"
    # Open with line buffering (buffering=1) and text mode
    log = open(log_file, 'w', buffering=1, encoding='utf-8')
    sys.stdout = log
    sys.stderr = log
    print(f"=== Clientbook Viewer Debug Log - {datetime.now()} ===", flush=True)
    print(f"Frozen: {sys.frozen}", flush=True)
    print(f"Executable: {sys.executable}", flush=True)
    print(f"_MEIPASS: {getattr(sys, '_MEIPASS', 'N/A')}", flush=True)
    print(f"Initial CWD: {os.getcwd()}", flush=True)
    print(flush=True)


# Import the viewer server functionality
# We'll run it in a separate thread
def start_viewer_server():
    """Start the viewer server in the background"""
    try:
        # When frozen with PyInstaller, change to the extraction directory
        # where viewer.py and the database symlinks will be located
        if getattr(sys, 'frozen', False):
            # Running in PyInstaller bundle - use the extraction directory
            print(f"Running frozen app, _MEIPASS: {sys._MEIPASS}", flush=True)
            os.chdir(sys._MEIPASS)
            print(f"Changed to CWD: {os.getcwd()}", flush=True)
            print(f"Files in CWD: {list(Path('.').glob('*'))[:20]}", flush=True)  # Limit output
        else:
            # Running in normal Python environment
            os.chdir(Path(__file__).parent)
        
        print("Importing viewer module...", flush=True)
        # Import and run the viewer
        import viewer
        from http.server import HTTPServer
        
        print(f"viewer.DB_PATH: {viewer.DB_PATH}", flush=True)
        print(f"DB exists: {viewer.DB_PATH.exists()}", flush=True)
        print(f"viewer.IMAGES_DIR: {viewer.IMAGES_DIR}", flush=True)
        print(f"IMAGES_DIR exists: {viewer.IMAGES_DIR.exists()}", flush=True)
        
        print(f"Starting HTTP server on port {viewer.PORT}...", flush=True)
        server = HTTPServer(('localhost', viewer.PORT), viewer.ClientbookHandler)
        print(f"Server started on http://localhost:{viewer.PORT}/", flush=True)
        server.serve_forever()
    except Exception as e:
        print(f"ERROR in start_viewer_server: {e}", flush=True)
        import traceback
        traceback.print_exc()
        raise


class ClientbookViewerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Clientbook Viewer")
        self.root.geometry("400x250")
        self.root.resizable(False, False)
        
        # Center the window
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
        # Create main frame
        main_frame = tk.Frame(root, padx=40, pady=40)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title label
        title_label = tk.Label(
            main_frame,
            text="Clientbook Viewer",
            font=tkfont.Font(size=18, weight="bold")
        )
        title_label.pack(pady=(0, 20))
        
        # Instructions label
        instructions = tk.Label(
            main_frame,
            text="Visit Clientbook in your web browser:",
            font=tkfont.Font(size=12)
        )
        instructions.pack()
        
        # URL link
        url = f"http://localhost:{self.get_port()}/"
        link = tk.Label(
            main_frame,
            text=url,
            font=tkfont.Font(size=12, underline=True),
            fg="blue",
            cursor="hand2"
        )
        link.pack(pady=(5, 0))
        link.bind("<Button-1>", lambda e: self.open_browser(url))
        
        # Status label
        self.status_label = tk.Label(
            main_frame,
            text="Starting server...",
            font=tkfont.Font(size=10),
            fg="gray"
        )
        self.status_label.pack(pady=(20, 0))
        
        # Start the server in a background thread
        self.server_thread = threading.Thread(target=start_viewer_server, daemon=True)
        self.server_thread.start()
        
        # Update status after a short delay
        self.root.after(1000, self.update_status)
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def get_port(self):
        """Get the port from viewer module"""
        try:
            import viewer
            return viewer.PORT
        except:
            return 8080
    
    def update_status(self):
        """Update the status label once server is running"""
        self.status_label.config(text="Server running • Close this window to stop", fg="#555")
    
    def open_browser(self, url):
        """Open the URL in the default web browser"""
        webbrowser.open(url)
    
    def on_closing(self):
        """Handle window close event"""
        print("Shutting down...")
        self.root.destroy()
        sys.exit(0)


def main():
    root = tk.Tk()
    app = ClientbookViewerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
