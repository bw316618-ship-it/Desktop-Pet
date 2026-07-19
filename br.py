"""Billo Rani — an animated desktop pet built with PyQt5.

She wanders your screen, flies, rolls, gets dizzy or "trapped", falls with
gravity when dropped, and has a right-click menu of extra tricks (dance,
compliments, love notes via Notepad, Bollywood serenades, and more).

Run directly: `python br.py`. Sprite frames are loaded from `assets/`
next to this file (or from the PyInstaller bundle dir when frozen into
an exe) — see assets/README.md for the expected filenames.
"""
import ctypes
import math
import os
import random
import subprocess
import sys
import tempfile
import time
from typing import Optional

from PyQt5 import QtCore, QtGui, QtWidgets

IS_WINDOWS = sys.platform.startswith("win")

# Windows helpers for bringing Notepad forward (best-effort)
if IS_WINDOWS:
    user32 = ctypes.windll.user32
    EnumWindows = user32.EnumWindows
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    GetWindowText = user32.GetWindowTextW
    GetWindowTextLength = user32.GetWindowTextLengthW
    IsWindowVisible = user32.IsWindowVisible
    SetForegroundWindow = user32.SetForegroundWindow


class BilloRani(QtWidgets.QWidget):
    """The desktop pet widget: sprite rendering, physics, moods, and menu."""

    # --- Sprite sizing ---
    SCALE = 4  # sprite frames are drawn at BASE_SIZE and scaled up this much
    BASE_SIZE = 18

    # --- Movement / physics tuning ---
    MAX_SPEED = 3.0
    STEER_SMOOTHING = 0.2          # how quickly velocity chases the target
    FLY_WAVE_AMPLITUDE = 2
    FLY_WAVE_SPEED = 0.12
    EDGE_BOUNCE_DAMPING = 0.6
    CEILING_BOUNCE_DAMPING = 0.5
    SKID_VELOCITY_DROP = 2.5       # vx delta that triggers a skid stop
    SKID_MIN_PREV_SPEED = 2.5
    BUMP_MIN_PREV_SPEED = 2
    GRAVITY = 0.9
    AIR_DRAG = 0.98
    JUMP_IMPULSE = 6
    FLY_KNOCKDOWN_VY = 5
    DROP_START_VY = 4.0
    LANDING_BOUNCE_VY = -6

    # --- Timer intervals (ms) ---
    ANIM_INTERVAL_MS = 110
    MOVE_INTERVAL_MS = 30
    BEHAVIOR_INTERVAL_MS = 4000
    MESSAGE_INTERVAL_MS = 6000
    MESSAGE_DISPLAY_MS = 4000
    DRAG_HOLD_DIZZY_MS = 3000      # how long you must hold-drag to trigger dizzy roll
    DIZZY_ROLL_MS = 2000
    ANNOY_ROLL_MS = 1200
    SELF_DESTRUCT_ROLL_MS = 800
    RESPAWN_DELAY_MS = 2000
    SKID_DURATION_MS = 600
    TINT_DURATION_MS = 5000
    MIRROR_DURATION_MS = 10000
    HURT_BLINK_DURATION_MS = 1800
    HURT_BLINK_INTERVAL_MS = 300
    DANCE_DURATION_S = 5.0
    DANCE_STEP_MS = 100

    # --- Random-event chances (per behavior tick) ---
    PUMP_EVENT_CHANCE = 0.05
    FLY_CHANCE = 0.1
    IDLE_MESSAGE_CHANCE = 0.4

    # Animation key -> sprite filename template(s). A single "{side}" frame
    # (no number) means the animation has one static pose; a range means an
    # animated cycle. This is the single source of truth for which sprite
    # files the pet expects, used both to preload frames and to build the
    # per-state animation lists.
    ANIMATION_DEFS = {
        "idle": ("stand{side}", None),
        "run": ("run{side}", (1, 3)),
        "fly": ("flying{side}", (1, 3)),
        "pump": ("pump{side}", (1, 3)),
        "roll": ("roll", (1, 4)),          # not side-specific
        "jump": ("jump{side}", None),
        "bump": ("bump{side}", None),
        "drop": ("drop{side}", None),
        "skid": ("skid{side}", None),
    }

    def __init__(self):
        super().__init__()

        # --- Paths & sizing ---
        self.sprites_path = self._resolve_sprites_path()
        self.frame_w = self.BASE_SIZE * self.SCALE
        self.frame_h = self.BASE_SIZE * self.SCALE

        # --- Frames dict (load individual images) ---
        self.frames: dict = {}
        self._load_all_frames()

        # --- Anim map (lists of QPixmap) ---
        self.anim = self._build_animation_map()

        # --- State ---
        self.state = "idle_right"
        self.frame_index = 0

        # Movement/physics
        self.vx, self.vy = 0.0, 0.0
        self.is_flying = False
        self.is_rolling = False
        self.falling = False
        self.fly_angle = 0.0
        self.target_x: Optional[int] = None
        self.target_y: Optional[int] = None

        # Dragging/trap
        self.dragging = False
        self.drag_offset = QtCore.QPoint(0, 0)
        self.trap_start: Optional[QtCore.QPoint] = None  # selection-rectangle trapping

        # Mood: one of happy, angry, trapped, flying, sleepy, excited
        self.mood = "happy"

        self._setup_window()
        self._setup_timers()
        self._setup_text_pools()

        print("Billo Rani — cleaned + mood colors + trapping integrated — ready!")

    # -------------------------
    # Setup helpers
    # -------------------------
    @staticmethod
    def _resolve_sprites_path() -> str:
        if getattr(sys, "frozen", False):
            # Running as a PyInstaller-built exe: bundled data files land in
            # sys._MEIPASS (a temp extraction dir), not next to the exe.
            return os.path.join(sys._MEIPASS, "assets")
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

    def _setup_window(self):
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        # sprite label
        self.label = QtWidgets.QLabel(self)
        self.label.setGeometry(0, 0, self.frame_w, self.frame_h)
        self.label.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        # message (speech bubble) label
        self.msg_label = QtWidgets.QLabel()
        self.msg_label.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool
        )
        self.msg_label.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.msg_label.setAlignment(QtCore.Qt.AlignCenter)
        self.msg_label.hide()

        # screen geometry (robust fallback if no primary screen is reported)
        screen = QtWidgets.QApplication.primaryScreen()
        self.screen = screen.availableGeometry() if screen else QtCore.QRect(0, 0, 800, 600)
        self.resize(self.frame_w, self.frame_h)
        self.move(self.screen.width() // 2, self.screen.height() // 2)
        self.show()

    def _setup_timers(self):
        self.anim_timer = QtCore.QTimer(self)
        self.anim_timer.timeout.connect(self.update_frame)
        self.anim_timer.start(self.ANIM_INTERVAL_MS)

        self.move_timer = QtCore.QTimer(self)
        self.move_timer.timeout.connect(self.update_position)
        self.move_timer.start(self.MOVE_INTERVAL_MS)

        self.behavior_timer = QtCore.QTimer(self)
        self.behavior_timer.timeout.connect(self.choose_target)
        self.behavior_timer.start(self.BEHAVIOR_INTERVAL_MS)

        self.message_timer = QtCore.QTimer(self)
        self.message_timer.timeout.connect(lambda: self.show_random_message())
        self.message_timer.start(self.MESSAGE_INTERVAL_MS)

        # roll/dizzy
        self.roll_timer = QtCore.QTimer(self)
        self.roll_timer.setSingleShot(True)
        self.roll_timer.timeout.connect(self.end_roll)

        # drag-dizzy timer
        self.drag_timer = QtCore.QTimer(self)
        self.drag_timer.setSingleShot(True)
        self.drag_timer.timeout.connect(self.trigger_dizzy_roll)

        # hurt blink (freezes movement while active)
        self.hurt_blink_timer = QtCore.QTimer(self)
        self.hurt_blink_timer.timeout.connect(self._hurt_blink_toggle)
        self.hurt_blink_count = 0
        self.hurt_blink_state = False

        # skid timer
        self.skid_timer = QtCore.QTimer(self)
        self.skid_timer.setSingleShot(True)
        self.skid_timer.timeout.connect(self.end_skid)

        # tint/mirror
        self.tint: Optional[str] = None
        self.tint_timer = QtCore.QTimer(self)
        self.tint_timer.setSingleShot(True)
        self.tint_timer.timeout.connect(self.clear_tint)
        self.mirrored = False

    def _setup_text_pools(self):
        self.messages = ["Whee!", "Zoom!", "Walking time!", "Watch out!",
                          "Hehe!", "Here I go!", "Hello there!", "Clicky!"]
        self.angry_messages = ["Grrr!", "I'm falling!", "Don't push me!", "Let me out!"]
        self.sleepy_messages = ["Zzz...", "Yawn...", "So sleepy..."]
        self.excited_messages = ["Yay!", "Jump!", "Woohoo!"]
        self.me_quotes = [
            "me , I love you!",
            "When me  enters the class, even teachers stand at attention.",
            "Billo Rani secretly thinks me  is cool.",
            "Good morning beautiful.",
            "Sunflowers for you.",
        ]
        self.notepad_messages = [
            "Dear me ,\nYou are awesome.\n— Billo Rani",
            "Roses are red\nCode runs green\nOpen Notepad\nAnd live the dream",
            "Hehe, I opened Notepad for you!",
            "If you see this, smile.",
        ]
        self.bollywood_serenade_texts = [
            "Tum hi ho... (Billo sings!)",
            "Tere liye dil...\n— Billo Rani",
        ]
        self.search_queries = ["cute desktop pet", "me ", "python pet widget", "funny gif"]

        # mood -> (message pool, speech-bubble color). Used by show_random_message.
        self.mood_pools = {
            "angry": (self.angry_messages, "red"),
            "trapped": (self.angry_messages, "red"),
            "flying": (self.messages, "blue"),
            "sleepy": (self.sleepy_messages, "gray"),
            "excited": (self.excited_messages, "green"),
            "happy": (self.messages, "yellow"),
        }

    # -------------------------
    # Frame loading utilities
    # -------------------------
    def _load_pm(self, fname: str) -> Optional[QtGui.QPixmap]:
        """Load one sprite PNG, center it on a frame_w x frame_h transparent canvas."""
        path = os.path.join(self.sprites_path, fname)
        if not os.path.exists(path):
            print(f"(warn) missing {fname}")
            return None
        pm = QtGui.QPixmap(path)
        if pm.isNull():
            print(f"(warn) invalid image {fname}")
            return None
        pm = pm.scaled(self.frame_w, self.frame_h, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        canvas = QtGui.QPixmap(self.frame_w, self.frame_h)
        canvas.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(canvas)
        x = (self.frame_w - pm.width()) // 2
        y = (self.frame_h - pm.height()) // 2
        painter.drawPixmap(x, y, pm)
        painter.end()
        return canvas

    def _frame_names_for(self, template: str, frame_range: Optional[tuple], side: str = "") -> list:
        """Expand an ANIMATION_DEFS entry into concrete filenames, e.g.
        ("run{side}", (1, 3)) + side="l" -> ["runl1.png", "runl2.png", "runl3.png"]."""
        name = template.format(side=side)
        if frame_range is None:
            return [f"{name}.png"]
        lo, hi = frame_range
        return [f"{name}{i}.png" for i in range(lo, hi + 1)]

    def _load_all_frames(self):
        """Preload every sprite file referenced by ANIMATION_DEFS plus hurt frames."""
        expected = []
        for template, frame_range in self.ANIMATION_DEFS.values():
            sides = ("l", "r") if "{side}" in template else ("",)
            for side in sides:
                expected.extend(self._frame_names_for(template, frame_range, side))
        expected += ["hurt.png", "hurt2.png"]

        for name in expected:
            self.frames[name] = self._load_pm(name)

    def _build_animation_map(self) -> dict:
        """Build state-key -> [QPixmap, ...] from the frames already loaded."""
        anim = {}
        for key, (template, frame_range) in self.ANIMATION_DEFS.items():
            if "{side}" in template:
                for side, suffix in (("l", "left"), ("r", "right")):
                    names = self._frame_names_for(template, frame_range, side)
                    anim[f"{key}_{suffix}"] = [self.frames[n] for n in names if self.frames.get(n)]
            else:
                # not side-specific (currently only "roll") — same frames both ways
                names = self._frame_names_for(template, frame_range)
                frames = [self.frames[n] for n in names if self.frames.get(n)]
                anim[f"{key}_left"] = frames
                anim[f"{key}_right"] = frames
        anim["hurt_frames"] = [f for f in (self.frames.get("hurt.png"), self.frames.get("hurt2.png")) if f]
        return anim

    # -------------------------
    # Drawing & tint helpers
    # -------------------------
    def _apply_tint(self, pixmap: Optional[QtGui.QPixmap], color: str) -> Optional[QtGui.QPixmap]:
        if pixmap is None:
            return pixmap
        img = pixmap.toImage().convertToFormat(QtGui.QImage.Format_ARGB32)
        canvas = QtGui.QPixmap(img.width(), img.height())
        canvas.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(canvas)
        painter.drawImage(0, 0, img)
        painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceAtop)
        painter.fillRect(canvas.rect(), QtGui.QColor(color))
        painter.end()
        return canvas

    def set_tint(self, color: str, duration_ms: int = TINT_DURATION_MS):
        self.tint = color
        self.tint_timer.start(duration_ms)

    def clear_tint(self):
        self.tint = None

    def _current_pixmap(self, pix: QtGui.QPixmap) -> QtGui.QPixmap:
        """Apply mirror/tint transforms consistently everywhere a frame is drawn."""
        if self.mirrored:
            pix = pix.transformed(QtGui.QTransform().scale(-1, 1))
        if self.tint:
            pix = self._apply_tint(pix, self.tint)
        return pix

    # -------------------------
    # Frame update (animation)
    # -------------------------
    def update_frame(self):
        # if hurting (blink timer) -> do not run other animations
        if self.hurt_blink_timer.isActive():
            return
        frames = self.anim.get(self.state, self.anim.get("idle_right", []))
        frames = [f for f in frames if isinstance(f, QtGui.QPixmap)]
        if not frames:
            return
        pix = frames[0] if len(frames) == 1 else frames[self.frame_index % len(frames)]
        self.label.setPixmap(self._current_pixmap(pix))
        self.label.adjustSize()
        self.frame_index += 1

    # -------------------------
    # Message display with mood-color map
    # -------------------------
    def show_random_message(self, force: bool = False, angry: bool = False,
                             text: Optional[str] = None, color: Optional[str] = None):
        if not (force or random.random() < self.IDLE_MESSAGE_CHANCE) and not text:
            return

        if text:
            msg, col = text, (color or "black")
        elif angry or self.mood in ("angry", "trapped"):
            pool, col = self.mood_pools["angry"]
            msg = random.choice(pool)
        else:
            pool, col = self.mood_pools.get(self.mood, self.mood_pools["happy"])
            msg = random.choice(pool)

        self.msg_label.setText(msg)
        self.msg_label.setStyleSheet(
            f"background-color: rgba(255,255,255,230); color: {col}; font-size: 13pt; font-weight: bold;"
        )
        self.msg_label.adjustSize()
        pet_pos = self.mapToGlobal(QtCore.QPoint(0, 0))
        self.msg_label.move(
            pet_pos.x() + self.width() // 2 - self.msg_label.width() // 2,
            pet_pos.y() - self.msg_label.height() - 20,
        )
        self.msg_label.show()
        self.msg_label.raise_()
        QtCore.QTimer.singleShot(self.MESSAGE_DISPLAY_MS, self.msg_label.hide)

    # -------------------------
    # Right-click menu (organized)
    # -------------------------
    def contextMenuEvent(self, event):
        menu = QtWidgets.QMenu(self)

        fun = menu.addMenu("Fun && Movement")
        fun.addAction("Dance Party", self.action_dance)
        fun.addAction("Self-Destruct", self.action_self_destruct)
        fun.addAction("Mirror Mode", self.action_mirror_mode)

        learn = menu.addMenu("Think && Learn")
        learn.addAction("Compliment Me", self.action_compliment)
        learn.addAction("Lecture Mode", self.action_lecture)
        learn.addAction("Think Deeply", self.action_think_deeply)
        learn.addAction("Search Something", self.action_search)

        love = menu.addMenu("Love && Letters")
        love.addAction("Write Note", self.action_write_note)
        love.addAction("Send Love Letter", self.action_send_love)
        love.addAction("Bollywood Serenade", self.action_bollywood_serenade)

        tricks = menu.addMenu("Moods && Tricks")
        tricks.addAction("Annoy Her", self.action_annoy)
        tricks.addAction("Change Color", self.action_change_color)

        util = menu.addMenu("Utilities")
        util.addAction("Open Chrome", self.open_chrome)
        util.addAction("Reset Mood", self.reset_mood)
        util.addAction("Exit", QtWidgets.QApplication.instance().quit)

        menu.exec_(event.globalPos())

    # -------------------------
    # Actions
    # -------------------------
    def action_dance(self):
        end = time.time() + self.DANCE_DURATION_S
        self.mood = "excited"
        orig_state = self.state

        def step():
            if time.time() >= end:
                self.dance_timer.stop()
                self.state = orig_state
                self.mood = "happy"
                return
            self.state = "run_right" if random.random() < 0.5 else "run_left"
            self.frame_index = 0

        self.dance_timer = QtCore.QTimer(self)
        self.dance_timer.timeout.connect(step)
        self.dance_timer.start(self.DANCE_STEP_MS)

    def action_self_destruct(self):
        self.state = "roll_right" if random.random() < 0.5 else "roll_left"
        self.is_rolling = True
        self.roll_timer.start(self.SELF_DESTRUCT_ROLL_MS)
        QtCore.QTimer.singleShot(
            self.SELF_DESTRUCT_ROLL_MS,
            lambda: (self.hide(), QtCore.QTimer.singleShot(self.RESPAWN_DELAY_MS, self._respawn_self))
        )

    def _respawn_self(self):
        self.show()
        self.move(
            random.randint(0, max(0, self.screen.width() - self.width())),
            random.randint(0, max(0, self.screen.height() - self.height())),
        )
        self.is_rolling = False
        self.state = "idle_right"
        self.mood = "happy"

    def action_mirror_mode(self):
        self.mirrored = True
        QtCore.QTimer.singleShot(self.MIRROR_DURATION_MS, lambda: setattr(self, "mirrored", False))

    def action_compliment(self):
        self.show_random_message(force=True, text=random.choice([
            "me , you are amazing.",
            "You're doing great today!",
            "Keep shining, superstar!",
        ]), color="pink")
        self.mood = "happy"

    def action_lecture(self):
        self.show_random_message(force=True, text=random.choice(self.me_quotes), color="purple")

    def action_think_deeply(self):
        self.show_random_message(force=True, text=random.choice([
            "Hmm... what is the meaning of life?",
            "Is code art or craft?",
            "If a sprite falls in the forest...",
        ]), color="navy")

    def _launch_chrome(self, url: Optional[str] = None):
        """Best-effort launch of Chrome, optionally pointed at a search URL."""
        try:
            if IS_WINDOWS:
                args = ["start", "chrome"] + ([url] if url else [])
                subprocess.Popen(args, shell=True)
            else:
                args = ["google-chrome"] + ([url] if url else [])
                subprocess.Popen(args)
            return True
        except Exception as e:
            print("open chrome fail:", e)
            return False

    def action_search(self):
        query = random.choice(self.search_queries)
        url = f"https://www.google.com/search?q={query}"
        if self._launch_chrome(url):
            self.show_random_message(force=True, text=f"Searching: {query}", color="blue")

    def open_chrome(self):
        if self._launch_chrome():
            self.show_random_message(force=True)

    def action_write_note(self):
        self.pump_event(note_text=random.choice(self.notepad_messages))

    def action_send_love(self):
        self.pump_event(note_text="Dear me ,\nYou are the best.\n— Billo Rani")

    def action_bollywood_serenade(self):
        self.pump_event(note_text=random.choice(self.bollywood_serenade_texts))
        self.show_random_message(force=True, text="*romantic chirp*", color="magenta")

    def action_annoy(self):
        self.mood = "angry"
        self.state = "roll_left" if random.random() < 0.5 else "roll_right"
        self.is_rolling = True
        self.roll_timer.start(self.ANNOY_ROLL_MS)
        self.show_random_message(force=True, text="Stop it!", color="red")

    def action_change_color(self):
        color = random.choice(["#ff9999", "#99ff99", "#9999ff", "#ffd699", "#d699ff"])
        self.set_tint(color, duration_ms=self.TINT_DURATION_MS)
        self.show_random_message(force=True, text="Sparkle!", color="black")

    def reset_mood(self):
        self.mood = "happy"
        self.show_random_message(force=True, text="Reset!", color="black")

    # -------------------------
    # Pump / Notepad event
    # -------------------------
    def pump_event(self, note_text: Optional[str] = None, show_line: Optional[str] = None):
        # don't interrupt falling/rolling/dragging
        if self.falling or self.is_rolling or self.dragging:
            return
        self.state = "pump_right" if random.random() < 0.5 else "pump_left"
        self.frame_index = 0
        self.mood = "excited"
        if show_line:
            self.show_random_message(force=True, text=show_line, color="magenta")
        else:
            self.show_random_message(force=True)

        txt = note_text if note_text else random.choice(self.notepad_messages)
        tmp = os.path.join(tempfile.gettempdir(), f"billo_note_{random.randint(1000, 9999)}.txt")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(txt)
            subprocess.Popen(["notepad.exe", tmp])
            if IS_WINDOWS:
                QtCore.QTimer.singleShot(400, lambda p=tmp: self._bring_notepad_to_front(p))
        except Exception as e:
            print("Notepad open error:", e)

    def _bring_notepad_to_front(self, filepath: str):
        if not IS_WINDOWS:
            return
        basename = os.path.basename(filepath)
        found = None

        @EnumWindowsProc
        def enum_proc(hwnd, lParam):
            try:
                if not IsWindowVisible(hwnd):
                    return True
                length = GetWindowTextLength(hwnd)
                if length <= 0:
                    return True
                buf = ctypes.create_unicode_buffer(length + 1)
                GetWindowText(hwnd, buf, length + 1)
                if basename in buf.value:
                    nonlocal found
                    found = hwnd
                    return False
            except Exception:
                pass
            return True

        EnumWindows(enum_proc, 0)
        if found:
            try:
                SetForegroundWindow(found)
            except Exception:
                pass

    # -------------------------
    # Dizzy/roll/hurt/skid
    # -------------------------
    def trigger_dizzy_roll(self):
        self.is_rolling = True
        self.mood = "angry"
        self.state = "roll_right" if random.random() < 0.5 else "roll_left"
        self.roll_timer.start(self.DIZZY_ROLL_MS)
        self.show_random_message(force=True, text="Dizzy!", color="red")

    def end_roll(self):
        self.is_rolling = False
        self.state = "idle_right" if self.state.endswith("right") else "idle_left"
        self.frame_index = 0
        if self.mood == "angry":
            self.mood = "happy"

    def start_skid(self, right: bool = True):
        self.state = "skid_right" if right else "skid_left"
        self.frame_index = 0
        self.skid_timer.start(self.SKID_DURATION_MS)

    def end_skid(self):
        self.state = "idle_right" if self.state.endswith("right") else "idle_left"
        self.frame_index = 0

    def _start_hurt_blink(self, duration_ms: int = HURT_BLINK_DURATION_MS,
                           interval_ms: int = HURT_BLINK_INTERVAL_MS):
        """Freezes movement and blinks between hurt frames until finished."""
        hurt = self.anim.get("hurt_frames", [])
        if not hurt:
            return
        self.hurt_blink_count = int(duration_ms / interval_ms)
        self.hurt_blink_state = False
        self.hurt_blink_timer.start(interval_ms)
        self._hurt_blink_toggle()

    def _hurt_blink_toggle(self):
        hurt = self.anim.get("hurt_frames", [])
        if not hurt:
            self.hurt_blink_timer.stop()
            return
        self.hurt_blink_state = not self.hurt_blink_state
        pix = hurt[1] if self.hurt_blink_state and len(hurt) > 1 else hurt[0]
        self.label.setPixmap(self._current_pixmap(pix))
        self.label.adjustSize()
        self.hurt_blink_count -= 1
        if self.hurt_blink_count <= 0:
            self.hurt_blink_timer.stop()
            self.state = "idle_right" if self.state.endswith("right") else "idle_left"
            self.frame_index = 0
            self.mood = "happy"

    # -------------------------
    # choose target (wandering + occasional pump)
    # -------------------------
    def choose_target(self):
        if random.random() < self.PUMP_EVENT_CHANCE:
            self.pump_event()
            return
        self.target_x = random.randint(0, max(0, self.screen.width() - self.width()))
        if random.random() < self.FLY_CHANCE:
            self.target_y = random.randint(0, max(0, self.screen.height() - self.height()))
            self.is_flying = True
            self.mood = "flying"
        else:
            y = self.y()
            self.target_y = max(0, min(self.screen.height() - self.height(), y + random.randint(-40, 40)))
            self.is_flying = False
            self.mood = "happy"
        self.frame_index = 0

    # -------------------------
    # Movement & physics
    # -------------------------
    def update_position(self):
        # If hurt blink active -> freeze everything
        if self.hurt_blink_timer.isActive():
            return

        # Falling (gravity) after being dropped
        if self.falling:
            self._handle_falling()
            return

        # If trapped (selection rectangle) -> freeze movement and stay angry/trapped
        if self.mood == "trapped":
            self.vx = 0.0
            self.vy = 0.0
            return

        # Skip automated movement while dragging
        if self.dragging:
            return

        # Trapping detection: if a selection rectangle is active and intersects pet -> trapped
        if self.trap_start is not None:
            cursor = QtGui.QCursor.pos()
            rect = QtCore.QRect(self.trap_start, cursor).normalized()
            if rect.intersects(self.geometry()):
                if self.mood != "trapped":
                    self.mood = "trapped"
                    self.show_random_message(force=True, angry=True)
                return  # movement frozen next tick via the mood == "trapped" branch above
            elif self.mood == "trapped":
                self.mood = "happy"

        # Normal wandering movement
        if self.target_x is None or self.target_y is None:
            self.choose_target()

        dx = self.target_x - self.x()
        dy = self.target_y - self.y()
        prev_vx = self.vx

        desired_vx = max(-self.MAX_SPEED, min(self.MAX_SPEED, dx))
        desired_vy = max(-self.MAX_SPEED, min(self.MAX_SPEED, dy))
        self.vx += (desired_vx - self.vx) * self.STEER_SMOOTHING
        self.vy += (desired_vy - self.vy) * self.STEER_SMOOTHING

        wave = math.sin(self.fly_angle) * (self.FLY_WAVE_AMPLITUDE if self.is_flying else 0)
        if self.is_flying:
            self.fly_angle += self.FLY_WAVE_SPEED

        nx = self.x() + self.vx
        ny = self.y() + self.vy + wave

        bumped = False
        if nx < 0:
            nx = 0
            self.vx = -self.vx * self.EDGE_BOUNCE_DAMPING
            bumped = True
        if nx > self.screen.width() - self.width():
            nx = self.screen.width() - self.width()
            self.vx = -self.vx * self.EDGE_BOUNCE_DAMPING
            bumped = True
        if bumped and abs(prev_vx) > self.BUMP_MIN_PREV_SPEED:
            self.state = "bump_right" if prev_vx > 0 else "bump_left"
            self.frame_index = 0

        if ny < 0:
            ny = 0
            self.vy = -self.vy * self.CEILING_BOUNCE_DAMPING

        self.move(int(nx), int(ny))

        # skid detection: sudden loss of horizontal speed
        if abs(prev_vx) > self.SKID_MIN_PREV_SPEED and abs(self.vx) < 0.6:
            self.start_skid(right=(prev_vx > 0))
            return

        # Animation selection
        if self.is_rolling:
            return
        if self.is_flying:
            self.state = "fly_right" if self.vx >= 0 else "fly_left"
        elif abs(self.vx) < 0.5 and abs(self.vy) < 0.5:
            self.state = "idle_right" if self.state.endswith("right") else "idle_left"
        elif abs(dx) >= abs(dy):
            self.state = "run_right" if self.vx >= 0 else "run_left"
        else:
            self.state = "idle_right" if self.state.endswith("right") else "idle_left"

    # -------------------------
    # Mouse events: drag -> drop
    # -------------------------
    def mousePressEvent(self, event):
        if event.button() != QtCore.Qt.LeftButton:
            return
        self.dragging = True
        self.drag_offset = event.pos()
        self.trap_start = QtGui.QCursor.pos()  # start selection-trap detection
        self.drag_timer.start(self.DRAG_HOLD_DIZZY_MS)  # held for 3s -> dizzy roll

        if self.is_flying:
            # clicked while flying -> force fall and get angry
            self.is_flying = False
            self.falling = True
            self.vy = self.FLY_KNOCKDOWN_VY
            self.mood = "angry"
            self.show_random_message(force=True, angry=True)
        else:
            # small jump when clicked while on ground
            self.vy -= self.JUMP_IMPULSE
            self.state = "jump_right" if self.vx >= 0 else "jump_left"
            self.mood = "happy"

    def mouseMoveEvent(self, event):
        if self.dragging:
            new_pos = self.mapToGlobal(event.pos() - self.drag_offset)
            self.move(new_pos)

    def mouseReleaseEvent(self, event):
        if event.button() != QtCore.Qt.LeftButton:
            return
        self.dragging = False
        self.trap_start = None  # stop trap detection
        self.drag_timer.stop()
        # Drop and fall to the ground, hurt on landing
        self.falling = True
        self.vy = self.DROP_START_VY
        self.state = "drop_right" if self.vx >= 0 else "drop_left"
        self.frame_index = 0
        self.mood = "angry"

    def _handle_falling(self):
        """Applies gravity while falling and triggers hurt-blink on landing."""
        if not self.falling:
            return
        self.vy += self.GRAVITY
        self.vx *= self.AIR_DRAG
        nx = self.x() + self.vx
        ny = self.y() + self.vy
        self.state = "drop_right" if self.vx >= 0 else "drop_left"
        self.frame_index = 0
        nx = max(0, min(self.screen.width() - self.width(), nx))
        ny = min(self.screen.height() - self.height(), ny)
        self.move(int(nx), int(ny))
        if self.y() >= self.screen.height() - self.height() - 1:
            self.falling = False
            self.state = "bump_right" if self.vx >= 0 else "bump_left"
            self.frame_index = 0
            self.vy = self.LANDING_BOUNCE_VY
            self._start_hurt_blink()


# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    pet = BilloRani()
    sys.exit(app.exec_())
