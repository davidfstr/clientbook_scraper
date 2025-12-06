#!/usr/bin/env python3
"""
Clientbook viewer - simple web interface to browse scraped conversations
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import sqlite3
import json
import urllib.parse
from pathlib import Path


DB_PATH = Path(__file__).parent / "clientbook.db"
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
            overflow-y: auto;
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
        .message-date {
            font-weight: 600;
            margin-bottom: 10px;
            color: #2c5aa0;
        }
        .message-text {
            line-height: 1.5;
            white-space: pre-wrap;
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
            <div id="clients-list" class="loading">Loading...</div>
        </div>
        <div class="main">
            <div id="conversation" class="empty-state">
                Select a client to view conversation
            </div>
        </div>
    </div>
    
    <script>
        let clients = [];
        let activeClientId = null;
        
        // Load clients list
        fetch('/api/clients')
            .then(r => r.json())
            .then(data => {
                clients = data;
                renderClientsList();
            });
        
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
            
            for (const [date, messages] of Object.entries(byDate)) {
                html += `<div class="message-date">${escapeHtml(date)}</div>`;
                messages.forEach(m => {
                    html += `
                        <div class="message">
                            <div class="message-text">${escapeHtml(m.message_text)}</div>
                        </div>
                    `;
                });
            }
            
            container.innerHTML = html;
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
        """Return JSON list of all clients"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        rows = c.execute("""
            SELECT client_id, name 
            FROM clients 
            ORDER BY name
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
                SELECT message_text, message_date, message_time
                FROM messages
                WHERE conversation_id = ?
                ORDER BY timestamp
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
    print(f"Starting server at http://localhost:{PORT}")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    
    server = HTTPServer(('localhost', PORT), ClientbookHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
