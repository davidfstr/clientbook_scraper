#!/usr/bin/env python3
"""
Clientbook scraper - extracts conversation data from Clientbook dashboard
"""

import asyncio
import sqlite3
from pathlib import Path
from playwright.async_api import async_playwright, Page
from datetime import datetime


# Database setup
DB_PATH = Path(__file__).parent / "clientbook.db"


def init_database():
    """Initialize SQLite database with schema"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Clients table
    c.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            client_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_updated_at TEXT NOT NULL
        )
    """)
    
    # Conversations table (one per client)
    c.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            conversation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT NOT NULL,
            last_message_time TEXT,
            FOREIGN KEY (client_id) REFERENCES clients(client_id)
        )
    """)
    
    # Messages table
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            sender_type TEXT NOT NULL,  -- 'client' or 'associate'
            sender_name TEXT,
            message_text TEXT,
            message_date TEXT,  -- e.g., "December 06, 2025"
            message_time TEXT,  -- e.g., "02:23 pm"
            timestamp TEXT,     -- ISO format for sorting
            FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
        )
    """)
    
    # Images table (images attached to messages)
    c.execute("""
        CREATE TABLE IF NOT EXISTS images (
            image_id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            image_url TEXT NOT NULL,
            image_time TEXT,  -- timestamp when image was sent
            FOREIGN KEY (message_id) REFERENCES messages(message_id)
        )
    """)
    
    conn.commit()
    conn.close()
    print(f"✓ Database initialized at {DB_PATH}")


async def login_to_clientbook(page: Page):
    """Navigate to Clientbook and handle login if needed"""
    print("Navigating to Clientbook...")
    await page.goto('https://dashboard.clientbook.com/')
    await page.wait_for_load_state('domcontentloaded')
    await asyncio.sleep(2)
    
    # Check if we're on login page
    current_url = page.url
    is_login_page = '/login' in current_url
    
    # Also check for login form elements
    try:
        email_input = await page.query_selector('input[type="email"]')
        password_input = await page.query_selector('input[type="password"]')
        has_login_form = email_input is not None and password_input is not None
    except:
        has_login_form = False
    
    if is_login_page or has_login_form:
        print("\n" + "="*60)
        print("⚠️  PLEASE LOG IN")
        print("="*60)
        print("Log in to Clientbook in the browser window that just opened.")
        print("Once you're logged in and see the dashboard, I'll continue...")
        print("="*60 + "\n")
        
        # Wait until we're NOT on a login page anymore
        while True:
            await asyncio.sleep(1)
            current_url = page.url
            if '/login' not in current_url and 'dashboard.clientbook.com' in current_url:
                # Verify we can see dashboard elements
                try:
                    await page.wait_for_selector('[href*="/Messaging/inbox"]', timeout=2000)
                    break
                except:
                    continue
        
        print("✓ Login successful!")
    else:
        print("✓ Already logged in")


async def get_inbox_list(page: Page) -> list:
    """Navigate to inbox and get list of conversations"""
    print("\nNavigating to inbox...")
    
    # Click on the Inbox menu item
    try:
        inbox_link = await page.query_selector('[href*="/Messaging/inbox"]')
        if inbox_link:
            await inbox_link.click()
        else:
            await page.goto('https://dashboard.clientbook.com/Messaging/inbox')
    except:
        await page.goto('https://dashboard.clientbook.com/Messaging/inbox')
    
    await page.wait_for_load_state('domcontentloaded')
    await asyncio.sleep(3)  # Wait for dynamic content
    
    print("Extracting conversation list...")
    
    # Wait for the conversation list to appear
    try:
        await page.wait_for_selector('li[id*="chatList"]', timeout=10000)
    except:
        print("⚠️  Couldn't find conversation list elements")
        # Take a screenshot for debugging
        await page.screenshot(path='debug_inbox.png')
        print("📷 Saved screenshot to debug_inbox.png")
    
    conversations = await page.evaluate("""
        () => {
            const items = [];
            const listItems = document.querySelectorAll('li[id*="chatList"]');
            
            console.log('Found list items:', listItems.length);
            
            for (const item of listItems) {
                // Try multiple selectors to find the name
                const nameEl = item.querySelector('div:nth-child(2) > div:first-child') ||
                              Array.from(item.querySelectorAll('div')).find(d => 
                                  d.textContent.length > 2 && d.textContent.length < 50
                              );
                const name = nameEl ? nameEl.textContent.trim() : '';
                
                console.log('Item:', name);
                
                if (name && !name.match(/^\d+[hd]$/)) {  // Exclude time indicators like "1h", "2d"
                    items.push({ name });
                }
            }
            
            return items;
        }
    """)
    
    print(f"✓ Found {len(conversations)} conversations")
    return conversations


async def scrape_conversation(page: Page, conversation_index: int) -> dict:
    """Click on a conversation and extract all messages"""
    print(f"\nScraping conversation {conversation_index + 1}...")
    
    # Click on the conversation
    await page.locator(f'li[id^="chatList"]').nth(conversation_index).click()
    await asyncio.sleep(3)  # Wait for messages to load
    
    # Extract conversation data
    data = await page.evaluate("""
        () => {
            const result = {
                clientName: '',
                clientId: '',
                messages: []
            };
            
            // Get client info from header
            const headerLink = document.querySelector('a[href*="/Clients?client="]');
            if (headerLink) {
                const href = headerLink.getAttribute('href');
                const match = href.match(/client=(\\d+)/);
                if (match) {
                    result.clientId = match[1];
                }
                
                const nameDiv = headerLink.querySelector('div div:first-child');
                if (nameDiv) {
                    result.clientName = nameDiv.textContent.trim();
                }
            }
            
            // Find the message container more precisely
            // It's typically a scrollable div that contains the messages
            const allDivs = document.querySelectorAll('div');
            let messageContainer = null;
            
            // Look for a div that contains date headers like "December 06, 2025"
            for (const div of allDivs) {
                const text = div.textContent;
                if (text.match(/\\w+ \\d{2}, \\d{4}/) && 
                    !text.includes('Inbox') && 
                    !text.includes('Today') &&
                    div.children.length > 5) {  // Has multiple message elements
                    messageContainer = div;
                    break;
                }
            }
            
            if (messageContainer) {
                // Parse messages from the container
                const children = Array.from(messageContainer.children);
                
                // In Clientbook DOM, messages appear newest-first (top to bottom)
                // A date header applies to messages that come BEFORE it in the DOM
                // So we need to scan forward to find dates, then look back to assign them
                
                // First pass: identify date positions
                const datePositions = [];
                for (let i = 0; i < children.length; i++) {
                    const text = children[i].textContent.trim();
                    if (text.match(/^\\w+ \\d{2}, \\d{4}$/)) {
                        datePositions.push({ index: i, date: text });
                    }
                }
                
                // Second pass: extract messages and assign dates
                for (let i = 0; i < children.length; i++) {
                    const child = children[i];
                    const text = child.textContent.trim();
                    
                    // Skip date headers themselves
                    if (text.match(/^\\w+ \\d{2}, \\d{4}$/)) {
                        continue;
                    }
                    
                    // Find which date this message belongs to
                    // It belongs to the first date that comes AFTER it in the DOM
                    let messageDate = '';
                    for (const datePos of datePositions) {
                        if (datePos.index > i) {
                            messageDate = datePos.date;
                            break;
                        }
                    }
                    
                    // Extract messages from this element
                    const listItems = child.querySelectorAll('li');
                    if (listItems.length > 0) {
                        for (const li of listItems) {
                            const messageText = li.textContent.trim();
                            if (messageText.length > 5) {  // Ignore very short text
                                // Get timestamp if available
                                const timeEl = child.querySelector('.chatDate, .singleMessageWrapper span');
                                const time = timeEl ? timeEl.textContent.trim() : '';
                                
                                result.messages.push({
                                    date: messageDate,
                                    text: messageText.slice(0, 500),  // Limit length
                                    time: time,
                                    type: 'text'
                                });
                            }
                        }
                    }
                    
                    // Check if this is an image container
                    const imgElement = child.querySelector('img.photoFit, img[src*="amazonaws.com"][src*=".jpg"]');
                    if (imgElement && imgElement.src) {
                        // Get the timestamp for the image
                        const timeEl = child.querySelector('.singleMessageWrapper span');
                        const time = timeEl ? timeEl.textContent.trim() : '';
                        
                        result.messages.push({
                            date: messageDate,
                            imageUrl: imgElement.src,
                            time: time,
                            type: 'image'
                        });
                    }
                }
                
                result.debug = {
                    containerFound: true,
                    childCount: children.length
                };
            } else {
                result.debug = {
                    containerFound: false,
                    divsChecked: allDivs.length
                };
            }
            
            return result;
        }
    """)
    
    print(f"  Client: {data.get('clientName', 'Unknown')} (ID: {data.get('clientId', 'Unknown')})")
    print(f"  Messages found: {len(data.get('messages', []))}")
    if data.get('messages'):
        print(f"  First message: {data['messages'][0].get('text', '')[:80]}...")
    return data


async def main():
    """Main scraper entry point"""
    print("=" * 60)
    print("CLIENTBOOK SCRAPER")
    print("=" * 60)
    
    # Initialize database
    init_database()
    
    async with async_playwright() as p:
        # Launch browser in headed mode so we can see what's happening
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            # Login
            await login_to_clientbook(page)
            
            # Get inbox list
            conversations = await get_inbox_list(page)
            
            if not conversations:
                print("\n⚠️  No conversations found!")
                return
            
            # Ask user how many to scrape
            print(f"\nFound {len(conversations)} conversations total.")
            print(f"How many would you like to scrape? (Enter a number, or 'all' for all)")
            print(f"Press Ctrl+C to cancel at any time.")
            
            # For now, let's scrape first 5 as default
            num_to_scrape = min(5, len(conversations))
            print(f"\nScraping first {num_to_scrape} conversations...")
            
            # Save to database
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            
            for i in range(num_to_scrape):
                data = await scrape_conversation(page, i)
                
                # Save client
                c.execute("""
                    INSERT OR REPLACE INTO clients (client_id, name, first_seen_at, last_updated_at)
                    VALUES (?, ?, ?, ?)
                """, (
                    data['clientId'],
                    data['clientName'],
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))
                
                # Save conversation
                c.execute("""
                    INSERT OR IGNORE INTO conversations (client_id)
                    VALUES (?)
                """, (data['clientId'],))
                
                conversation_id = c.execute(
                    "SELECT conversation_id FROM conversations WHERE client_id = ?",
                    (data['clientId'],)
                ).fetchone()[0]
                
                # Save messages
                for msg in data.get('messages', []):
                    msg_type = msg.get('type', 'text')
                    
                    if msg_type == 'text':
                        # Insert text message
                        c.execute("""
                            INSERT INTO messages (
                                conversation_id, sender_type, sender_name, 
                                message_text, message_date, message_time, timestamp
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            conversation_id,
                            'unknown',  # We'll need to detect this better
                            '',
                            msg.get('text', ''),
                            msg.get('date', ''),
                            msg.get('time', ''),
                            datetime.now().isoformat()
                        ))
                    
                    elif msg_type == 'image':
                        # Create a placeholder message for the image
                        c.execute("""
                            INSERT INTO messages (
                                conversation_id, sender_type, sender_name, 
                                message_text, message_date, message_time, timestamp
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            conversation_id,
                            'unknown',
                            '',
                            '[Image]',  # Placeholder text
                            msg.get('date', ''),
                            msg.get('time', ''),
                            datetime.now().isoformat()
                        ))
                        
                        # Get the message_id we just inserted
                        message_id = c.lastrowid
                        
                        # Insert the image record
                        c.execute("""
                            INSERT INTO images (message_id, image_url, image_time)
                            VALUES (?, ?, ?)
                        """, (
                            message_id,
                            msg.get('imageUrl', ''),
                            msg.get('time', '')
                        ))
                
                conn.commit()
                print(f"  ✓ Saved to database")
            
            conn.close()
            
            print("\n" + "="*60)
            print("✓ SCRAPING COMPLETE!")
            print("="*60)
            print(f"Scraped {num_to_scrape} conversations")
            print(f"Database: {DB_PATH}")
            print(f"\nNext: Build a web viewer to browse the data")
            
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
