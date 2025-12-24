In this repository I have a viewer.py script which can be run to start a web server that views data from {clientbook.db, clientbook.db-images} in the current directory.

I'd like to make it possible for a macOS end user that does not know how to use the command line and may not have Python installed to run the same program.

Outcomes:
- There exists a "dist/Clientbook Viewer.app" which can be opened to:
  - Start a web server in the background.
  - Show a minimal UI that says something like "Visit Clientbook in your web browser: http://127.0.0.1:8080/", where the URL is a blue link that if clicked opens a web browser.
  - When the (only) window is closed the app exits, stopping the web server.
- It is possible to manually run the viewer.py script inside the .app bundle with a system-installed version of Python, if the .app bundle itself becomes un-runnable after several macOS updates in the future. Perhaps via a CLI command like "python3 'dist/Clientbook Viewer.app/Contents/Resources/viewer.py'"
- There exists a "dist/Clientbook Viewer - README.txt" which says what the app does and mentions how to run with the python3 command manually if needed.

Let's discuss strategies to freeze the .app bundle. I know py2app would work, but it's a bit complicated to use. I've also heard of PyInstaller. There may be other tools too.
