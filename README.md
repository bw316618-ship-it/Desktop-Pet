# Billo Rani 🐾

A tiny animated desktop pet for Windows (also runs on Linux/macOS with
reduced features), built with Python and PyQt5. She wanders your screen,
reacts to being dragged/dropped, gets "trapped" if you draw a selection
box over her, and has a right-click menu full of extra tricks (dance,
compliments, love notes via Notepad, Bollywood serenades, and more).

![Billo Rani](screenshots/billo_rani.png)


## Features

- Idle / run / fly / roll / jump / bump / drop / skid animations
- Drag-and-drop physics with gravity, "hurt" blink on landing, and skid-stop
- Get her "trapped" by dragging a selection rectangle over her
- Right-click menu, organized into submenus:
  - **Fun & Movement** — Dance Party, Self-Destruct, Mirror Mode
  - **Think & Learn** — Compliment Me, Lecture Mode, Think Deeply, Search Something
  - **Love & Letters** — Write Note, Send Love Letter, Bollywood Serenade
  - **Moods & Tricks** — Annoy Her, Change Color
  - **Utilities** — Open Chrome, Reset Mood, Exit
- Mood-colored speech bubbles (happy/angry/flying/sleepy/excited)
- Sprite frames included in [`assets/`](assets) — works out of the box

## Quick start (double-click exe)

Every push to `master` builds a Windows `BilloRani.exe` automatically via
GitHub Actions. To get it:

1. Go to the repo's **Actions** tab → latest **Build Windows exe** run →
   download the `BilloRani-windows-exe` artifact (it's a zip containing
   `BilloRani.exe`).
2. Or, for tagged releases (`v1.0`, etc.), grab `BilloRani.exe` directly
   from the **Releases** page — no zip, no download from Actions needed.
3. Double-click `BilloRani.exe`. That's it — sprites are bundled inside,
   nothing else to install.

Windows may show a SmartScreen warning ("Windows protected your PC")
since the exe isn't code-signed — click **More info → Run anyway**.

## Running from source

```bash
pip install -r requirements.txt
python br.py
```

Requires Python 3.8+ and PyQt5.

Notepad-related features (Write Note, Send Love Letter, Bollywood Serenade)
and window-focusing use `notepad.exe` and Win32 APIs, so they only fully
work on **Windows**. On other platforms the script still runs — those
actions will just fail quietly (errors are caught and printed to the
console) — everything else (movement, dragging, menu, moods) works
cross-platform.

## Building the exe yourself

If you're on Windows and want to build it locally instead of using the
Actions artifact:

```bash
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --onefile --windowed --name BilloRani --add-data "assets;assets" br.py
```

The exe will be in `dist/BilloRani.exe`.

## License

MIT — see [LICENSE](LICENSE).
