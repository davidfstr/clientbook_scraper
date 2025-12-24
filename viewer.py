#!/usr/bin/env python3
"""
Clientbook viewer - simple web interface to browse scraped conversations
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import sqlite3
import json
import urllib.parse
import mimetypes
from pathlib import Path


DB_PATH = Path(__file__).parent / "clientbook.db"
IMAGES_DIR = Path(__file__).parent / "clientbook.db-images"
PORT = 8080


class ClientbookHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        query = urllib.parse.parse_qs(parsed_path.query)
        
        if path == '/':
            self.serve_index()
        elif path == '/api/clients':
            self.serve_clients_list()
        elif path == '/api/conversation':
            client_id = query.get('client_id', [None])[0]
            self.serve_conversation(client_id)
        elif path.startswith('/images/'):
            filename = path[8:]  # Remove '/images/' prefix
            self.serve_image(filename)
        else:
            self.send_error(404)
    
    def serve_index(self):
        """Serve the main HTML page"""
        html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Clientbook Archive</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            margin: 0;
            padding: 0;
            background: #f5f5f5;
        }
        .container {
            display: flex;
            height: 100vh;
        }
        .sidebar {
            width: 320px;
            background: white;
            border-right: 1px solid #ddd;
            display: flex;
            flex-direction: column;
        }
        .main {
            flex: 1;
            background: white;
            overflow-y: auto;
            padding: 20px;
        }
        .header {
            padding: 20px;
            background: #2c5aa0;
            color: white;
            font-size: 24px;
            font-weight: 600;
        }
        .search-box {
            padding: 15px 20px;
            border-bottom: 1px solid #ddd;
            background: #fafafa;
        }
        .search-input {
            width: 100%;
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
            box-sizing: border-box;
        }
        .search-input::placeholder {
            color: #999;
        }
        .clients-list-container {
            flex: 1;
            overflow-y: auto;
        }
        .client-item {
            padding: 15px 20px;
            border-bottom: 1px solid #f0f0f0;
            cursor: pointer;
            transition: background 0.2s;
        }
        .client-item:hover {
            background: #f8f8f8;
        }
        .client-item.active {
            background: #e8f0ff;
        }
        .client-name {
            font-weight: 600;
            margin-bottom: 5px;
        }
        .client-id {
            font-size: 12px;
            color: #666;
        }
        .message {
            margin-bottom: 20px;
            padding: 15px;
            background: #f9f9f9;
            border-radius: 8px;
        }
        .message.from-associate {
            background: #e8f0ff;
            margin-left: auto;
            max-width: 70%;
        }
        .message.from-client {
            background: #f0f0f0;
            max-width: 70%;
        }
        .message.from-other {
            background: #fff8e1;
            max-width: 70%;
        }
        .sender-name {
            font-size: 11px;
            color: #666;
            margin-bottom: 5px;
            font-weight: 600;
            text-align: left;
        }
        .message-date {
            text-align: center;
            font-weight: 500;
            font-size: 13px;
            margin: 25px 0 15px;
            color: #999;
        }
        .message-text {
            line-height: 1.5;
            white-space: pre-wrap;
            text-align: left;
        }
        .message-time {
            font-size: 10px;
            color: #999;
            text-align: right;
            margin-top: 8px;
            font-style: italic;
        }
        .message-image {
            margin-top: 10px;
            max-width: 300px;
            border-radius: 8px;
            display: block;
            cursor: pointer;
        }
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #999;
        }
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="sidebar">
            <div class="header">Clientbook Archive</div>
            <div class="search-box">
                <input type="text" id="search-input" class="search-input" placeholder="Search by first or last name...">
            </div>
            <div class="clients-list-container">
                <div id="clients-list" class="loading">Loading...</div>
            </div>
        </div>
        <div class="main">
            <div id="conversation" class="empty-state">
                Select a client to view conversation
            </div>
        </div>
    </div>
    
    <script>
        let clients = [];
        let allClients = [];
        let activeClientId = null;
        let searchTimeout = null;
        
        // Load clients list
        fetch('/api/clients')
            .then(r => r.json())
            .then(data => {
                allClients = data;
                clients = data;
                renderClientsList();
                setupSearch();
            });
        
        function setupSearch() {
            const searchInput = document.getElementById('search-input');
            searchInput.addEventListener('input', function(e) {
                const query = e.target.value;
                
                // Clear existing timeout
                if (searchTimeout) {
                    clearTimeout(searchTimeout);
                }
                
                // Only search if at least 2 characters or empty (to show all)
                if (query.length >= 2) {
                    // Wait 300ms after user stops typing
                    searchTimeout = setTimeout(() => {
                        filterClients(query);
                    }, 300);
                } else if (query.length === 0) {
                    // Show all clients when search is cleared
                    clients = allClients;
                    renderClientsList();
                }
            });
        }
        
        function filterClients(query) {
            const lowerQuery = query.toLowerCase();
            clients = allClients.filter(c => {
                const nameParts = c.name.split(' ');
                const firstName = nameParts[0].toLowerCase();
                const lastName = nameParts.length > 1 ? nameParts[nameParts.length - 1].toLowerCase() : '';
                return firstName.startsWith(lowerQuery) || lastName.startsWith(lowerQuery);
            });
            renderClientsList();
        }
        
        function renderClientsList() {
            const container = document.getElementById('clients-list');
            if (clients.length === 0) {
                container.innerHTML = '<div class="empty-state">No clients found</div>';
                return;
            }
            
            container.innerHTML = clients.map(c => `
                <div class="client-item ${c.client_id === activeClientId ? 'active' : ''}" 
                     onclick="loadConversation('${c.client_id}')">
                    <div class="client-name">${escapeHtml(c.name)}</div>
                    <div class="client-id">ID: ${c.client_id}</div>
                </div>
            `).join('');
        }
        
        function loadConversation(clientId) {
            activeClientId = clientId;
            renderClientsList();
            
            const container = document.getElementById('conversation');
            container.innerHTML = '<div class="loading">Loading conversation...</div>';
            
            fetch('/api/conversation?client_id=' + clientId)
                .then(r => r.json())
                .then(data => {
                    renderConversation(data);
                });
        }
        
        function renderConversation(data) {
            const container = document.getElementById('conversation');
            
            if (data.messages.length === 0) {
                container.innerHTML = '<div class="empty-state">No messages found</div>';
                return;
            }
            
            // Group messages by date
            const byDate = {};
            data.messages.forEach(m => {
                const date = m.message_date || 'Unknown Date';
                if (!byDate[date]) byDate[date] = [];
                byDate[date].push(m);
            });
            
            let html = `<h2>${escapeHtml(data.client_name)}</h2>`;
            
            // Preserve message order and show dates before their messages
            let lastDate = '';
            data.messages.forEach(m => {
                const date = m.message_date || 'Unknown Date';
                if (date !== lastDate) {
                    html += `<div class="message-date">${escapeHtml(date)}</div>`;
                    lastDate = date;
                }
                
                // Determine message class based on sender
                let messageClass = 'message';
                if (m.sender_type === 'associate') {
                    messageClass += ' from-associate';
                } else if (m.sender_type === 'client') {
                    messageClass += ' from-client';
                } else if (m.sender_type === 'other_associate') {
                    messageClass += ' from-other';
                }
                
                html += `<div class="${messageClass}">`;
                
                // Show sender name for non-associate messages
                if (m.sender_name) {
                    html += `<div class="sender-name">${escapeHtml(m.sender_name)}</div>`;
                }
                
                // Show message text (skip if it's just the placeholder "[Image]")
                if (m.message_text && m.message_text !== '[Image]') {
                    html += `<div class="message-text">${escapeHtml(m.message_text)}</div>`;
                }
                
                // Show image if present
                if (m.image_url) {
                    // Use local image if downloaded, otherwise fallback to remote URL
                    const imageUrl = m.local_filename ? `/images/${m.local_filename}` : m.image_url;
                    html += `<a href="${escapeHtml(imageUrl)}" target="_blank" rel="noopener noreferrer">`;
                    html += `<img src="${escapeHtml(imageUrl)}" class="message-image" alt="Message attachment">`;
                    html += `</a>`;
                }
                
                // Show message time
                if (m.message_time) {
                    html += `<div class="message-time">${escapeHtml(m.message_time)}</div>`;
                }
                
                html += `</div>`;
            });
            
            container.innerHTML = html;
            
            // Scroll to bottom to show most recent messages
            container.scrollTop = container.scrollHeight;
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    </script>
</body>
</html>"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))
    
    def serve_clients_list(self):
        """Return JSON list of all clients with messages"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        rows = c.execute("""
            SELECT c.client_id, c.name 
            FROM clients c
            LEFT JOIN conversations cv ON c.client_id = cv.client_id
            LEFT JOIN messages m ON cv.conversation_id = m.conversation_id
            GROUP BY c.client_id
            HAVING COUNT(m.message_id) > 0
            ORDER BY MIN(m.message_id) ASC
        """).fetchall()
        
        clients = [dict(row) for row in rows]
        conn.close()
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(clients).encode('utf-8'))
    
    def serve_conversation(self, client_id):
        """Return JSON conversation data for a client"""
        if not client_id:
            self.send_error(400, "Missing client_id")
            return
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Get client info
        client = c.execute("""
            SELECT client_id, name 
            FROM clients 
            WHERE client_id = ?
        """, (client_id,)).fetchone()
        
        if not client:
            self.send_error(404, "Client not found")
            conn.close()
            return
        
        # Get conversation and messages
        conversation = c.execute("""
            SELECT conversation_id 
            FROM conversations 
            WHERE client_id = ?
        """, (client_id,)).fetchone()
        
        messages = []
        if conversation:
            rows = c.execute("""
                SELECT m.message_text, m.message_date, m.message_time, m.message_id,
                       m.sender_type, m.sender_name,
                       i.image_url, i.image_id, d.filename as local_filename
                FROM messages m
                LEFT JOIN images i ON m.message_id = i.message_id
                LEFT JOIN image_downloads d ON i.image_url = d.url
                WHERE m.conversation_id = ?
                ORDER BY m.message_id DESC
            """, (conversation['conversation_id'],)).fetchall()
            messages = [dict(row) for row in rows]
        
        conn.close()
        
        result = {
            'client_id': client['client_id'],
            'client_name': client['name'],
            'messages': messages
        }
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(result).encode('utf-8'))
    
    def serve_image(self, filename):
        """Serve an image from the local images directory"""
        # Sanitize filename to prevent directory traversal
        filename = Path(filename).name
        
        image_path = IMAGES_DIR / filename
        
        if not image_path.exists() or not image_path.is_file():
            self.send_error(404, "Image not found")
            return
        
        # Determine content type
        content_type, _ = mimetypes.guess_type(str(image_path))
        if not content_type:
            content_type = 'application/octet-stream'
        
        try:
            with open(image_path, 'rb') as f:
                content = f.read()
            
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'public, max-age=31536000')  # Cache for 1 year
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Error reading image: {e}")
    
    def log_message(self, format, *args):
        """Suppress default logging"""
        pass


def main():
    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        print("Please run scraper.py first to create and populate the database.")
        return
    
    print("=" * 60)
    print("CLIENTBOOK VIEWER")
    print("=" * 60)
    print(f"Database: {DB_PATH}")
    print(f"Starting server at http://127.0.0.1:{PORT}")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    
    server = HTTPServer(('127.0.0.1', PORT), ClientbookHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
