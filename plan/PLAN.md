# Clientbook Scrape & Serve Project

## Goals

There is a website called Clientbook <https://dashboard.clientbook.com/> that contains a list of conversations with a number of clients. I will be losing access to this website soon because my employer is migrating to use a different CRM system. I want to retain access to the content of conversations that I've had with clients in the past so that I can remember what I've said to them.

Unfortunately Clientbook's HTML and JS structure is too complex to download with Crystal, the tool available in this repository, and I don't have enough time to enhance Crystal with the necessary capabilities before I lose access to Clientbook.

1. I want to build a tool that scrapes conversation data from my Clientbook account, storing scraped data in a SQLite database. I want to build this tool with you interactively, to discover exactly what data is available to save and what data is actually valuable to save.

2. I want to build a tool which serves an interactive website for exploring the scraped data. It would be nice if the visual appearance of the served website was similar to Clientbook's interface, so that it's easy for me to use with my prior knowledge of how Clientbook's UI works.

## Technologies

- Use Python, both to build the scraper and serve the website for data browsing
- For website serving use a very lightweight framework (like bottle.py) or no framewwork at all (like just http.server)
- Create files related to this project inside the `plan/clientbook2` directory.
- Use the Playwright MCP tools to interactively explore the Clientbook web interface and discover its structure
- Write the scraper such that it also uses Playwright to extract data from the browser DOM. The API endpoints in Clientbook are complex and time-consuming to try to use directly.

## Notes

Save notes you want to remember between sessions to this section:

### Session 1: Initial Exploration (2025-12-06)

**Discoveries:**
- Clientbook interface has an Inbox view at `/Messaging/inbox`
- Left side shows list of conversations with client names, initials, preview text, and time
- Right side shows full conversation when a client is selected
- Conversations have:
  - Client name and ID (visible in URL: `/Clients?client=<client_id>`)
  - Messages grouped by date (e.g., "December 06, 2025")
  - Each message has sender info (client vs associate), message text, timestamp (e.g., "02:23 pm")
  - Messages include both outbound (from associates) and inbound (from clients)
  - Some messages have attachments/images
  - Some messages are automated (repair complete, payment confirmations, etc.)

**Implementation:**

1. **Scraper (`scraper.py`)**: ✓ Complete
   - Uses Playwright to automate Chromium browser
   - Logs into Clientbook (manual login, then automation continues)
   - Navigates to inbox and extracts conversation list
   - Clicks through conversations and extracts messages from DOM
   - Saves to SQLite database
   - Usage: `python scraper.py`

2. **Database (`clientbook.db`)**: ✓ Complete
   - SQLite with 3 tables: `clients`, `conversations`, `messages`
   - Currently has 5 clients, 5 conversations, 475 messages

3. **Web Viewer (`viewer.py`)**: ✓ Complete
   - Simple HTTP server (no external dependencies)
   - Left sidebar shows list of clients
   - Right side shows conversation messages grouped by date
   - Usage: `python3 viewer.py` then open http://localhost:8080

**Status:** Basic scraping and viewing is working!

**Key Technical Learnings:**

*DOM Structure Understanding:*
- In Clientbook's UI, messages are displayed oldest at the top, newest at the bottom.
- Date headers appear in the UI above the messages they label.
- The DOM is in *reverse order* compared with the appearance in the UI.
   - The first message in the DOM is the newest message,
     which appears at the bottom of the UI.
- A date header in the DOM applies to all messages that come BEFORE it (until the previous date)
- The scraper extracts messages in the order they appear in DOM (newest→oldest)
- Therefore message_id reflects reverse-chronological order
- The viewer must use `ORDER BY message_id DESC` to get chronological order (oldest→newest)

*Scraper Logic:*
- Two-pass approach: First identify all date positions, then assign dates to messages
- For each message at position i in the DOM, find the first date at position j where j > i
- That date applies to that message (since dates come after their messages in the DOM)
- Messages before the first date header get no date (edge case to handle later)

*Testing Workflow:*
- Delete `clientbook.db` before re-running scraper to test changes
- Check database with: `sqlite3 clientbook.db "SELECT message_id, message_date, substr(message_text, 1, 70) FROM messages WHERE conversation_id = X ORDER BY message_id;"`
- Compare against original Clientbook UI by opening same conversation in both
- Restart viewer after database changes

**Image Capture Implementation (Session 2.1: 2025-12-21):**

Images in Clientbook are:
- Stored as separate DOM elements from text messages
- Have class `photoFit` and are wrapped in `div.border-r4.pos-rel.pointer.m-right-9`
- Source URLs are S3 links: `https://s3.amazonaws.com/ec2-static.giftry.com/[uuid].jpg`
- Appear in DOM immediately after their associated text message
- Share the same timestamp as the preceding text message

Implementation:
- Added `images` table to database with `message_id`, `image_url`, `image_time`
- Updated scraper's JS to detect both text messages AND image containers
- Messages with images create a placeholder message with text `[Image]`
- Viewer's SQL query joins messages with images table
- Viewer displays images inline using `<img>` tags with class `message-image`

**Sender Detection Implementation (Session 2.2: 2025-12-21):**

Messages in Clientbook have different alignments and structures based on sender:

**Right-aligned messages** (from account holder associate):
- Class: `singleMessageWrapper align-right`
- No sender name displayed
- Blue tail indicator
- Stored as `sender_type='associate'` with empty `sender_name`

**Left-aligned messages** (from client or other associates):
- Wrapped in `<div>` with no class, containing child with `flex-row-nospacebetween-nowrap m-top-12`
- Display sender name in `span.text-light-gray.fs-10.m-left-8`
- Gray bubble, left-aligned
- Stored as `sender_type='client'` or `sender_type='other_associate'` with `sender_name` populated

Implementation:
- Updated scraper to detect both right-aligned and left-aligned message containers
- Right-aligned: Check for `.singleMessageWrapper.align-right`
- Left-aligned: Check for child element `.flex-row-nospacebetween-nowrap.m-top-12`
- Extract sender name from left-aligned messages
- Classify sender as client (matches conversation client name) vs other associate
- Fixed client name extraction to use `div:nth-child(2)` to skip initials div
- Updated viewer CSS with different background colors per sender type:
  - `.from-associate` (blue background) - account holder messages
  - `.from-client` (gray background) - client messages  
  - `.from-other` (yellow background) - other associate messages
- Display sender name above message text for non-associate messages

✅ **Status:** Sender detection working! Messages correctly classified and styled by sender type.

**Next Steps:**
- Get a conversation to scrape/view perfectly (in terms of information content):
    - Scroll through long conversations in scraper to get all messages (may be paginated)
- Scrape all conversations (not just first 5). The conversation view is paginated, so will need to scroll it to reveal new conversations.
- Add search (by client name) functionality to viewer
- Style viewer to look more like Clientbook UI (message bubbles, colors, layout)
