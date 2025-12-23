#!/usr/bin/env python3
"""
Clientbook scraper - extracts conversation data from Clientbook dashboard
"""

import asyncio
import sqlite3
import argparse
import subprocess
import os
from pathlib import Path
from playwright.async_api import async_playwright, Page
from datetime import datetime
from tqdm import tqdm


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


async def get_inbox_list(page: Page, target_count: int = 50) -> list:
    """Navigate to inbox and get list of conversations, scrolling to load more"""
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
    
    print(f"Loading conversations (target: {target_count})...")
    
    # Wait for the conversation list to appear
    try:
        await page.wait_for_selector('li[id*="chatList"]', timeout=10000)
    except:
        print("⚠️  Couldn't find conversation list elements")
        # Take a screenshot for debugging
        await page.screenshot(path='debug_inbox.png')
        print("📷 Saved screenshot to debug_inbox.png")
    
    # Scroll the conversation list to load more conversations
    prev_count = 0
    attempts = 0
    
    while True:
        # Count current conversations
        current_count = await page.evaluate("""
            () => {
                return document.querySelectorAll('li[id*="chatList"]').length;
            }
        """)
        
        print(f"  Currently loaded: {current_count} conversations")
        
        # Check if we have enough or if no new conversations loaded
        if current_count >= target_count or (current_count == prev_count and attempts > 0):
            break
        
        prev_count = current_count
        
        # Scroll to load more
        scrolled = await page.evaluate("""
            () => {
                // Find the scrollable container with overflow-y: auto
                const allDivs = document.querySelectorAll('div');
                let scrollContainer = null;
                
                for (const div of allDivs) {
                    const style = window.getComputedStyle(div);
                    if (style.overflowY === 'auto' || style.overflowY === 'scroll') {
                        const listItems = div.querySelectorAll('li[id*="chatList"]');
                        if (listItems.length > 0) {
                            scrollContainer = div;
                            break;
                        }
                    }
                }
                
                if (scrollContainer) {
                    const before = scrollContainer.scrollTop;
                    scrollContainer.scrollTop = scrollContainer.scrollHeight;
                    const after = scrollContainer.scrollTop;
                    return { success: true, scrolled: after > before };
                }
                
                return { success: false };
            }
        """)
        
        if not scrolled.get('success'):
            print("⚠️  Could not find scrollable container")
            break
        
        if not scrolled.get('scrolled'):
            print("  Reached bottom of list")
            break
        
        # Wait for new conversations to load
        await asyncio.sleep(2)
        attempts += 1
    
    print(f"✓ Loaded {current_count} conversations total")
    
    print("\nExtracting conversation details...")
    
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


async def search_conversation(page: Page, client_name: str) -> int:
    """Search for a conversation by client name and return number of matches"""
    # Find the search input box using its ID
    search_input = await page.query_selector('#inbox-search')
    
    if search_input:
        # Clear any existing search
        await search_input.click()
        await search_input.fill('')
        
        # Enter the client name
        await search_input.fill(client_name)
        
        # Wait a moment for the list to filter
        await asyncio.sleep(1)
        
        # Count how many conversations match
        match_count = await page.evaluate("""
            () => {
                return document.querySelectorAll('li[id*="chatList"]').length;
            }
        """)
        
        return match_count
    
    return 0


async def scrape_conversation(page: Page, conversation_index: int, minimal_messages: bool = False, verbose: bool = True) -> dict:
    """Click on a conversation and extract all messages"""
    if verbose:
        print(f"\nScraping conversation {conversation_index + 1}...")
    
    # Click on the conversation
    await page.locator(f'li[id^="chatList"]').nth(conversation_index).click()
    
    # Wait less time if we're doing minimal scraping
    wait_time = 1 if minimal_messages else 2
    await asyncio.sleep(wait_time)  # Wait for messages to load
    
    # Prepare JavaScript code with minimal mode flag
    js_code = """
        (minimalMode) => {
            const MINIMAL_MODE = minimalMode;
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
                
                // Get the name from the first span inside the flex-col-left-center div
                // This div contains two spans: first has full name, second has extra info like "FirstName |"
                const nameSpan = headerLink.querySelector('.flex-col-left-center span:first-child');
                if (nameSpan) {
                    result.clientName = nameSpan.textContent.trim();
                }
            }
            
            // Find the message container more precisely
            // It's typically a scrollable div that contains the messages
            const infScrollDivs = document.querySelectorAll('.infinite-scroll-component');
            let messageContainer = infScrollDivs[1];
            
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
                const maxMessages = MINIMAL_MODE ? 1 : 999999;
                let messageCount = 0;
                
                for (let i = 0; i < children.length; i++) {
                    if (messageCount >= maxMessages) break;
                    
                    const child = children[i];
                    const text = child.textContent.trim();
                    
                    // Skip date headers themselves
                    if (text.match(/^\\w+ \\d{2}, \\d{4}$/)) {
                        continue;
                    }
                    
                    // Find which date this message belongs to
                    let messageDate = '';
                    for (const datePos of datePositions) {
                        if (datePos.index > i) {
                            messageDate = datePos.date;
                            break;
                        }
                    }
                    
                    // Check if this is a left-aligned message with sender info (client or other associate)
                    // These have a first child with class flex-row-nospacebetween-nowrap m-top-12
                    const leftAlignedContainer = child.querySelector('.flex-row-nospacebetween-nowrap.m-top-12');
                    
                    if (leftAlignedContainer) {
                        // This is a client or other associate message
                        const senderEl = leftAlignedContainer.querySelector('span.text-light-gray.fs-10.m-left-8');
                        const senderName = senderEl ? senderEl.textContent.trim() : '';
                        
                        const listItems = leftAlignedContainer.querySelectorAll('li');
                        if (listItems.length > 0) {
                            for (const li of listItems) {
                                const messageText = li.innerText.trim();
                                if (messageText.length > 5) {
                                    // Get timestamp
                                    let time = '';
                                    const timeEl = leftAlignedContainer.querySelector('span.fs-10.italic');
                                    if (timeEl) {
                                        const timeText = timeEl.textContent.trim();
                                        const timeMatch = timeText.match(/\\d{1,2}:\\d{2}\\s*[ap]m/i);
                                        if (timeMatch) {
                                            time = timeMatch[0];
                                        }
                                    }
                                    
                                    result.messages.push({
                                        date: messageDate,
                                        text: messageText,
                                        time: time,
                                        type: 'text',
                                        isRightAligned: false,
                                        senderName: senderName
                                    });
                                    messageCount++;
                                }
                            }
                        }
                    } else {
                        // Check if this is a right-aligned message (from associate/account holder)
                        const isRightAligned = child.classList.contains('align-right') || 
                                              child.querySelector('.singleMessageWrapper.align-right') !== null;
                        
                        if (isRightAligned) {
                            // Extract messages from right-aligned container
                            const listItems = child.querySelectorAll('li');
                            if (listItems.length > 0) {
                                for (const li of listItems) {
                                    const messageText = li.innerText.trim();
                                    if (messageText.length > 5) {
                                        // Get timestamp
                                        let time = '';
                                        const timeEl = child.querySelector('span.fs-10.italic, .chatDate');
                                        if (timeEl) {
                                            const timeText = timeEl.textContent.trim();
                                            const timeMatch = timeText.match(/\\d{1,2}:\\d{2}\\s*[ap]m/i);
                                            if (timeMatch) {
                                                time = timeMatch[0];
                                            }
                                        }
                                        
                                        result.messages.push({
                                            date: messageDate,
                                            text: messageText,
                                            time: time,
                                            type: 'text',
                                            isRightAligned: true,
                                            senderName: ''
                                        });
                                        messageCount++;
                                    }
                                }
                            }
                        }
                    }
                    
                    // Check if this is an image container (skip in minimal mode)
                    if (!MINIMAL_MODE) {
                        const imgElement = child.querySelector('img.photoFit, img[src*="amazonaws.com"][src*=".jpg"]');
                        if (imgElement && imgElement.src) {
                            // Determine if this image is from the client/other associate (left-aligned) or associate (right-aligned)
                            // Check for left-aligned container first
                            const leftAlignedImageContainer = child.querySelector('.flex-row-nospacebetween-nowrap.m-top-12');
                            const isRightAligned = !leftAlignedImageContainer && 
                                                   (child.classList.contains('align-right') || 
                                                    child.querySelector('.singleMessageWrapper.align-right') !== null);
                            
                            // Get sender name if left-aligned
                            let senderName = '';
                            if (leftAlignedImageContainer) {
                                const senderEl = leftAlignedImageContainer.querySelector('span.text-light-gray.fs-10.m-left-8');
                                senderName = senderEl ? senderEl.textContent.trim() : '';
                            }
                            
                            // Get the timestamp for the image
                            let time = '';
                            const timeEl = child.querySelector('.singleMessageWrapper span, span.fs-10.italic');
                            if (timeEl) {
                                const timeText = timeEl.textContent.trim();
                                const timeMatch = timeText.match(/\d{1,2}:\d{2}\s*[ap]m/i);
                                if (timeMatch) {
                                    time = timeMatch[0];
                                }
                            }
                            
                            result.messages.push({
                                date: messageDate,
                                imageUrl: imgElement.src,
                                time: time,
                                type: 'image',
                                isRightAligned: isRightAligned,
                                senderName: senderName
                            });
                            messageCount++;
                        }
                    }
                }
                
                result.debug = {
                    containerFound: true,
                    childCount: children.length
                };
            } else {
                result.debug = {
                    containerFound: false,
                    divsChecked: infScrollDivs.length
                };
            }
            
            return result;
        }
    """
    
    # Execute the JavaScript with the minimal mode parameter
    data = await page.evaluate(js_code, minimal_messages)
    
    if verbose:
        print(f"  Client: {data.get('clientName', 'Unknown')} (ID: {data.get('clientId', 'Unknown')})")
        print(f"  Messages found: {len(data.get('messages', []))}")
        if data.get('messages'):
            first_msg_text = data['messages'][0].get('text', data['messages'][0].get('imageUrl', ''))
            print(f"  First message: {str(first_msg_text)[:80]}...")
    return data


async def save_conversation_to_db(c, data, conn) -> None:
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
        is_right = msg.get('isRightAligned', False)
        sender_name = msg.get('senderName', '')
        
        # Determine sender type
        if is_right:
            sender_type = 'associate'  # Account holder (Laura)
        elif sender_name:
            # Check if it's the client or another associate
            if sender_name == data.get('clientName', ''):
                sender_type = 'client'
            else:
                sender_type = 'other_associate'
        else:
            sender_type = 'unknown'
        
        if msg_type == 'text':
            # Insert text message
            c.execute("""
                INSERT INTO messages (
                    conversation_id, sender_type, sender_name, 
                    message_text, message_date, message_time, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                conversation_id,
                sender_type,
                sender_name,
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
                sender_type,
                sender_name,
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


async def main():
    """Main scraper entry point"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Scrape conversation data from Clientbook')
    parser.add_argument('--minimal-messages', action='store_true',
                       help='Fetch only 1 message per conversation for faster name extraction')
    parser.add_argument('--num-conversations', type=int, default=50,
                       help='Number of conversations to scrape (default: 50)')
    parser.add_argument('--verbose', action='store_true',
                       help='Show detailed output for each conversation (default: use progress bar)')
    parser.add_argument('--start-at', type=int, default=None,
                       help='Start scraping at this conversation index (0-based, for resuming after errors)')
    args = parser.parse_args()
    
    print("=" * 60)
    print("CLIENTBOOK SCRAPER")
    print("=" * 60)
    if args.minimal_messages:
        print("⚡ MINIMAL MODE: Fetching only 1 message per conversation")
    print(f"Target: {args.num_conversations} conversations")
    if args.start_at is not None:
        print(f"Starting at index: {args.start_at}")
    print("=" * 60)
    
    # Initialize database
    init_database()
    
    # Start caffeinate to keep computer awake during scraping (macOS only)
    caffeinate_process = None
    try:
        pid = os.getpid()
        caffeinate_process = subprocess.Popen(['caffeinate', '-disu', '-w', str(pid)],
                                              stdout=subprocess.DEVNULL,
                                              stderr=subprocess.DEVNULL)
    except (FileNotFoundError, OSError):
        # Not on macOS or caffeinate not available, silently continue
        pass
    
    async with async_playwright() as p:
        # Launch browser in headed mode so we can see what's happening
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            # Login
            await login_to_clientbook(page)
            
            # Get inbox list (scroll to load target number of conversations)
            conversations = await get_inbox_list(page, target_count=args.num_conversations)
            
            if not conversations:
                print("\n⚠️  No conversations found!")
                return
            
            # Determine how many to scrape
            num_to_scrape = min(args.num_conversations, len(conversations))
            print(f"\nScraping {num_to_scrape} conversations...")
            
            # Save to database
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            
            skipped_count = 0
            scraped_count = 0
            
            # Determine if we should use search-based approach for better performance
            use_search = len(conversations) > 500
            if use_search and args.verbose:
                print(f"\n⚡ Using search-based approach for better performance ({len(conversations)} conversations)")
            
            # Use tqdm progress bar if not in verbose mode
            conversation_indexes = range(num_to_scrape)
            if not args.verbose:
                conversation_indexes = tqdm(conversation_indexes, desc="Scraping conversations", unit="conversation")
            
            for i in conversation_indexes:
                # Skip conversations before start index if specified
                if args.start_at is not None and i < args.start_at:
                    continue
                
                # If using search-based approach, search for this conversation first
                if use_search:
                    client_name = conversations[i]['name']
                    match_count = await search_conversation(page, client_name)
                    
                    if match_count == 0:
                        if args.verbose:
                            print(f"  ⚠️  No matches found for '{client_name}'")
                        continue
                    
                    # Usually exactly 1 match, but could be more
                    # Scrape all matches (typically just index 0)
                    for match_idx in range(match_count):
                        data = await scrape_conversation(page, match_idx, minimal_messages=args.minimal_messages, verbose=args.verbose)
                        
                        # Check if this client already exists in the database
                        existing_client = c.execute(
                            "SELECT client_id FROM clients WHERE client_id = ?",
                            (data['clientId'],)
                        ).fetchone()
                        
                        if existing_client:
                            if args.verbose:
                                print(f"  ⏭️  Skipping - client already exists in database")
                            skipped_count += 1
                            continue
                        
                        # Process this conversation (save to database)
                        scraped_count += 1
                        await save_conversation_to_db(c, data, conn)
                        
                        if args.verbose:
                            print(f"  ✓ Saved to database")
                else:
                    # Direct index-based approach for smaller lists
                    data = await scrape_conversation(page, i, minimal_messages=args.minimal_messages, verbose=args.verbose)
                
                    # Check if this client already exists in the database (non-search mode)
                    existing_client = c.execute(
                        "SELECT client_id FROM clients WHERE client_id = ?",
                        (data['clientId'],)
                    ).fetchone()
                    
                    if existing_client:
                        if args.verbose:
                            print(f"  ⏭️  Skipping - client already exists in database")
                        skipped_count += 1
                        continue
                    
                    # Process this conversation (save to database)
                    scraped_count += 1
                    await save_conversation_to_db(c, data, conn)
                    
                    if args.verbose:
                        print(f"  ✓ Saved to database")
            
            conn.close()
            
            print("\n" + "="*60)
            print("✓ SCRAPING COMPLETE!")
            print("="*60)
            print(f"Total conversations processed: {num_to_scrape}")
            print(f"  New conversations scraped: {scraped_count}")
            print(f"  Existing conversations skipped: {skipped_count}")
            print(f"Database: {DB_PATH}")
            print(f"\nNext: Build a web viewer to browse the data")
            
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
