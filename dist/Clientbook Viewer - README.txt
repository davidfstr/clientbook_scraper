Clientbook Viewer
=================

This application provides a simple web interface to browse your archived 
Clientbook conversations.

How to Use
----------

1. Double-click "Clientbook Viewer.app" to launch it.

2. A small window will appear with a link to http://localhost:8080/

3. Click the link (or visit it manually in your browser) to view your data.

4. Close the window when you're done to stop the server.


Troubleshooting
---------------

If the .app bundle stops working after macOS updates (this can happen 
with frozen Python applications), you can run the viewer directly with 
Python from the Frameworks directory inside the .app bundle.

Example (from the directory with your .app bundle):

  cd 'Clientbook Viewer.app/Contents/Frameworks'
  python3 viewer.py

This will start the same web server. Then visit http://localhost:8080/ 
in your web browser.


Requirements
------------

For the manual Python method, you need Python 3.6 or later installed. 
Python 3 comes pre-installed on modern macOS versions.


About
-----

This is a standalone viewer application that runs a local web server
to display your Clientbook archive data. No data is sent over the 
network - everything runs locally on your computer.
