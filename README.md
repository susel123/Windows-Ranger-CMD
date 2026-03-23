# Windows-Ranger-CMD

Minimalist terminal file manager inspired by ranger, built in Python for Windows.

## Features

- Browse files and folders in a ranger-style interface
- Three-column layout (parent / current / preview)
- Fuzzy search for quick file finding
- File preview:
  - Text files preview
  - Image preview (ASCII / terminal rendering)
- Play MP3 files directly in terminal
- Multi-selection (select multiple files)
- File operations:
  - Copy
  - Move
  - Paste
  - Delete (with confirmation)
- History navigation (back / forward)
- Sorting (by name, size, date)
- Filter files by extension
- Bookmarks (quick access to folders)
- Handles long file names (scrolling display)
- File info panel (size, path, date)
- Works in standard Windows terminal (no external tools required)


## Preview

![preview]

<img width="957" height="475" alt="Zrzut ekranu (443)" src="https://github.com/user-attachments/assets/d6f50bd1-1108-4359-9807-6bf6f74ee2bc" />


<img width="1920" height="1008" alt="Zrzut ekranu (444)" src="https://github.com/user-attachments/assets/598756b2-9d25-4150-a47e-244024ac4534" />


## Controls

| Key        | Action                     |
|-----------|----------------------------|
| ↑ / ↓     | Move up / down             |
| ←         | Go to parent directory     |
| →         | Open file (system default) |
| Enter     | Open in terminal action    |
| Space     | Select / unselect file     |
| d         | Delete (with confirmation) |
| c         | Copy                       |
| m         | Move                       |
| p         | Paste                      |
| /         | Fuzzy search               |
| s         | Sort files                 |
| f         | Filter by extension        |
| b         | Add bookmark               |
| Tab       | Go to bookmark             |
| h         | Back (history)             |
| l         | Forward (history)          |
| q         | Quit                       |


## OPTIONAL:

for MP3 audio in terminal need pygame 

```pip install pygame```

for Image preview (ASCII) need pillow 

```pip install pillow```
