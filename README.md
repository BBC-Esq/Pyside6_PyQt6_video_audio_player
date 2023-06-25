## Summary:

A light-weight video and audio player using PyQt6 for the GUI and VLC to play.

Scoured the Internet and was unable to find a script based on PyQt6 (even though Riverbank Computing's website says it's possible).  Found a couple based on PyQt5 but I still couldn't successfully convert to PyQt6.  Just FYI, the most recent "PySide" implementation of the "QT framework" (PyQt being the other if you're unfamiliar) does have a way.  However, I needed one based on PyQt6 because my other scripts use PyQt6...hence my script that uses VLC.

## Requirements:

PyQt6 — python-vlc

pip install PyQt6
pip install python-vlc

**Note: Tested on Python 3.10 and python-vlc 3.0.18122**
**Note: Only for Windows-based systems - Sorry!**

## Instructions:

1. Using the command prompt, type "python gui_viewer_media.py" -- OR
2. Put both the python file and batch file in the computer system PATH and open a command prompt anywhere and type "python_player."  Research online if you don't know how to make sure files are within a computer's "PATH".

## Summary of Scripts:

| Script                   | Description                                                               |
|--------------------------|---------------------------------------------------------------------------|
| "gui_viewer_media.py"    | Loads and runs the player, which can play both video and audio            |
| "python_player.bat"      | Bootstraps the python script so you can run it in any active directory    |

Thank you for visiting!
