# br.py — Billo Rani (final: merged mood colors + trapping + cleaned)
import sys
import os
import random
import math
import subprocess
import time
import ctypes
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
    SCALE = 4  # consistent scale (you chose 4)

    def __init__(self):
        super().__init__()

        # --- Paths & sizing ---
        self.sprites_path = os.path.dirname(os.path.abspath(__file__))
        self.base_w, self.base_h = 18, 18
        self.scale = BilloRani.SCALE
        self.frame_w = self.base_w * self.scale
        self.frame_h = self.base_h * self.scale

        # --- Frames dict (load individual images) ---
        self.frames = {}
        self._load_all_frames()

        # --- Anim map (lists of QPixmap) ---
        self.anim = self._build_animation_map()

        # --- State ---
        self.state = "idle_right"
        self.frame_index = 0

        # Movement/physics
        self.vx, self.vy = 0.0, 0.0
        self.max_speed = 3.0
        self.is_flying = False
        self.is_rolling = False
        self.falling = False
        self.fly_angle = 0.0
        self.target_x, self.target_y = None, None

        # Dragging/trap
        self.dragging = False
        self.drag_offset = QtCore.QPoint(0, 0)
        self.trap_start = None  # used to detect selection-rectangle trapping

        # Mood
        self.mood = "happy"  # happy, angry, trapped, flying, sleepy, excited

        # --- UI setup ---
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

        # message label
        self.msg_label = QtWidgets.QLabel()
        self.msg_label.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool
        )
        self.msg_label.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.msg_label.setAlignment(QtCore.Qt.AlignCenter)
        self.msg_label.hide()

        # screen geometry (robust)
        screen = QtWidgets.QApplication.primaryScreen()
        self.screen = screen.availableGeometry() if screen else QtCore.QRect(0, 0, 800, 600)
        self.resize(self.frame_w, self.frame_h)
        self.move(self.screen.width() // 2, self.screen.height() // 2)
        self.show()

        # --- Timers ---
        self.anim_timer = QtCore.QTimer(self)
        self.anim_timer.timeout.connect(self.update_frame)
        self.anim_timer.start(110)

        self.move_timer = QtCore.QTimer(self)
        self.move_timer.timeout.connect(self.update_position)
        self.move_timer.start(30)

        self.behavior_timer = QtCore.QTimer(self)
        self.behavior_timer.timeout.connect(self.choose_target)
        self.behavior_timer.start(4000)

        self.message_timer = QtCore.QTimer(self)
        self.message_timer.timeout.connect(lambda: self.show_random_message())
        self.message_timer.start(6000)

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
        self.tint = None
        self.tint_timer = QtCore.QTimer(self)
        self.tint_timer.setSingleShot(True)
        self.tint_timer.timeout.connect(self.clear_tint)
        self.mirrored = False

        # --- Text pools ---
        self.messages = ["Whee!", "Zoom!", "Walking time!", "Watch out!",
                          "Hehe!", "Here I go!", "Hello there!", "Clicky!"]
        self.angry_messages = ["Grrr!", "I'm falling!", "Don't push me!", "Let me out!"]
        self.sleepy_messages = ["Zzz...", "Yawn...", "So sleepy..."]
        self.excited_messages = ["Yay!", "Jump!", "Woohoo!"]
        self.saxena_quotes = [
            "Saxena Ji, I love you!",
            "When Saxena Ji enters the class, even teachers stand at attention.",
            "Billo Rani secretly thinks Saxena Ji is cool.",
            "Good morning beautiful.",
            "Sunflowers for you.",
        ]
        self.notepad_messages = [
            "Dear Saxena Ji,\nYou are awesome.\n— Billo Rani",
            "Roses are red\nCode runs green\nOpen Notepad\nAnd live the dream",
            "Hehe, I opened Notepad for you!",
            "If you see this, smile.",
        ]
        self.bollywood_serenade_texts = [
            "Tum hi ho... (Billo sings!)",
            "Tere liye dil...\n— Billo Rani",
        ]
        self.search_queries = ["cute desktop pet", "Saxena Ji", "python pet widget", "funny gif"]

        print("Billo Rani — cleaned + mood colors + trapping integrated — ready!")

    # -------------------------
    # Frame loading utilities
    # -------------------------
    def _load_pm(self, fname):
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

    def _load_all_frames(self):
        expected = [
            "bumpl.png", "bumpr.png", "dropl.png", "dropr.png",
            "flyingl1.png", "flyingl2.png", "flyingl3.png",
            "flyingr1.png", "flyingr2.png", "flyingr3.png",
            "hurt.png", "hurt2.png", "jumpl.png", "jumpr.png",
            "pumpl1.png", "pumpl2.png", "pumpl3.png",
            "pumpr1.png", "pumpr2.png", "pumpr3.png",
            "roll1.png", "roll2.png", "roll3.png", "roll4.png",
            "runl1.png", "runl2.png", "runl3.png",
            "runr1.png", "runr2.png", "runr3.png",
            "skidl.png", "skidr.png",
            "standl.png", "standr.png",
        ]
        for n in expected:
            self.frames[n] = self._load_pm(n)

    def _build_animation_map(self):
        A = {}
        A["idle_left"] = [self.frames.get("standl.png")] if self.frames.get("standl.png") else []
        A["idle_right"] = [self.frames.get("standr.png")] if self.frames.get("standr.png") else []
        A["run_left"] = [self.frames.get(f"runl{i}.png") for i in (1, 2, 3) if self.frames.get(f"runl{i}.png")]
        A["run_right"] = [self.frames.get(f"runr{i}.png") for i in (1, 2, 3) if self.frames.get(f"runr{i}.png")]
        A["fly_left"] = [self.frames.get(f"flyingl{i}.png") for i in (1, 2, 3) if self.frames.get(f"flyingl{i}.png")]
        A["fly_right"] = [self.frames.get(f"flyingr{i}.png") for i in (1, 2, 3) if self.frames.get(f"flyingr{i}.png")]
        A["pump_left"] = [self.frames.get(f"pumpl{i}.png") for i in (1, 2, 3) if self.frames.get(f"pumpl{i}.png")]
        A["pump_right"] = [self.frames.get(f"pumpr{i}.png") for i in (1, 2, 3) if self.frames.get(f"pumpr{i}.png")]
        A["roll_left"] = [self.frames.get(f"roll{i}.png") for i in (1, 2, 3, 4) if self.frames.get(f"roll{i}.png")]
        A["roll_right"] = A["roll_left"]
        A["jump_left"] = [self.frames.get("jumpl.png")] if self.frames.get("jumpl.png") else []
        A["jump_right"] = [self.frames.get("jumpr.png")] if self.frames.get("jumpr.png") else []
        A["bump_left"] = [self.frames.get("bumpl.png")] if self.frames.get("bumpl.png") else []
        A["bump_right"] = [self.frames.get("bumpr.png")] if self.frames.get("bumpr.png") else []
        A["drop_left"] = [self.frames.get("dropl.png")] if self.frames.get("dropl.png") else []
        A["drop_right"] = [self.frames.get("dropr.png")] if self.frames.get("dropr.png") else []
        A["skid_left"] = [self.frames.get("skidl.png")] if self.frames.get("skidl.png") else []
        A["skid_right"] = [self.frames.get("skidr.png")] if self.frames.get("skidr.png") else []
        A["hurt_frames"] = [f for f in (self.frames.get("hurt.png"), self.frames.get("hurt2.png")) if f]
        return A

    # -------------------------
    # Drawing & tint helpers
    # -------------------------
    def _apply_tint(self, pixmap, color):
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

    def set_tint(self, color, duration_ms=3000):
        self.tint = color
        self.tint_timer.start(duration_ms)

    def clear_tint(self):
        self.tint = None

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
        if len(frames) == 1:
            pix = frames[0]
        else:
            pix = frames[self.frame_index % len(frames)]
        if self.mirrored:
            pix = pix.transformed(QtGui.QTransform().scale(-1, 1))
        if self.tint:
            pix = self._apply_tint(pix, self.tint)
        self.label.setPixmap(pix)
        self.label.adjustSize()
        self.frame_index += 1

    # -------------------------
    # Message display with mood-color map
    # -------------------------
    def show_random_message(self, force=False, angry=False, text=None, color=None):
        # mood -> color mapping (kept from your smaller code)
        mood_colors = {
            "happy": "yellow",
            "angry": "red",
            "trapped": "red",
            "flying": "blue",
            "sleepy": "gray",
            "excited": "green",
            "saxena": "purple",
        }
        if not (force or random.random() < 0.4) and not text:
            return
        if text:
            msg = text
            col = color or "black"
        else:
            if angry or self.mood in ["angry", "trapped"]:
                msg = random.choice(self.angry_messages)
                col = "red"
            elif self.mood == "flying":
                msg = random.choice(self.messages)
                col = "blue"
            elif self.mood == "sleepy":
                msg = random.choice(self.sleepy_messages)
                col = "gray"
            elif self.mood == "excited":
                msg = random.choice(self.excited_messages)
                col = "green"
            else:
                msg = random.choice(self.messages)
                col = "yellow"

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
        QtCore.QTimer.singleShot(4000, self.msg_label.hide)

    # -------------------------
    # Right-click menu (organized)
    # -------------------------
    def contextMenuEvent(self, event):
        menu = QtWidgets.QMenu(self)

        # Fun & Movement
        fun = menu.addMenu("Fun & Movement")
        fun.addAction("Dance Party", lambda: self.action_dance())
        fun.addAction("Self-Destruct", lambda: self.action_self_destruct())
        fun.addAction("Mirror Mode", lambda: self.action_mirror_mode())

        # Think & Learn
        learn = menu.addMenu("Think & Learn")
        learn.addAction("Compliment Me", lambda: self.action_compliment())
        learn.addAction("Lecture Mode", lambda: self.action_lecture())
        learn.addAction("Think Deeply", lambda: self.action_think_deeply())
        learn.addAction("Search Something", lambda: self.action_search())

        # Love & Letters
        love = menu.addMenu("Love & Letters")
        love.addAction("Write Note", lambda: self.action_write_note())
        love.addAction("Send Love Letter", lambda: self.action_send_love())
        love.addAction("Bollywood Serenade", lambda: self.action_bollywood_serenade())

        # Moods & Tricks
        tricks = menu.addMenu("Moods & Tricks")
        tricks.addAction("Annoy Her", lambda: self.action_annoy())
        tricks.addAction("Change Color", lambda: self.action_change_color())

        # Utilities
        util = menu.addMenu("Utilities")
        util.addAction("Open Chrome", lambda: self.open_chrome())
        util.addAction("Reset Mood", lambda: self.reset_mood())
        util.addAction("Exit", lambda: QtWidgets.qApp.quit())

        menu.exec_(event.globalPos())

    # -------------------------
    # Actions (kept / cleaned)
    # -------------------------
    def action_dance(self):
        duration_s = 5.0
        end = time.time() + duration_s
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
        self.dance_timer.start(100)

    def action_self_destruct(self):
        self.state = "roll_right" if random.random() < 0.5 else "roll_left"
        self.is_rolling = True
        self.roll_timer.start(800)
        QtCore.QTimer.singleShot(
            800,
            lambda: (self.hide(), QtCore.QTimer.singleShot(2000, self._respawn_self))
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
        QtCore.QTimer.singleShot(10000, lambda: setattr(self, "mirrored", False))

    def action_compliment(self):
        self.show_random_message(force=True, text=random.choice([
            "Saxena Ji, you are amazing.",
            "You're doing great today!",
            "Keep shining, superstar!",
        ]), color="pink")
        self.mood = "happy"

    def action_lecture(self):
        self.show_random_message(force=True, text=random.choice(self.saxena_quotes), color="purple")

    def action_think_deeply(self):
        self.show_random_message(force=True, text=random.choice([
            "Hmm... what is the meaning of life?",
            "Is code art or craft?",
            "If a sprite falls in the forest...",
        ]), color="navy")

    def action_search(self):
        query = random.choice(self.search_queries)
        try:
            if IS_WINDOWS:
                subprocess.Popen(["start", "chrome", f"https://www.google.com/search?q={query}"], shell=True)
            else:
                subprocess.Popen(["google-chrome", f"https://www.google.com/search?q={query}"])
            self.show_random_message(force=True, text=f"Searching: {query}", color="blue")
        except Exception as e:
            print("search open failed:", e)

    def open_chrome(self):
        try:
            if IS_WINDOWS:
                subprocess.Popen(["start", "chrome"], shell=True)
            else:
                subprocess.Popen(["google-chrome"])
            self.show_random_message(force=True)
        except Exception as e:
            print("open chrome fail:", e)

    def action_write_note(self):
        self.pump_event(note_text=random.choice(self.notepad_messages))

    def action_send_love(self):
        txt = "Dear Saxena Ji,\nYou are the best.\n— Billo Rani"
        self.pump_event(note_text=txt)

    def action_bollywood_serenade(self):
        txt = random.choice(self.bollywood_serenade_texts)
        self.pump_event(note_text=txt)
        self.show_random_message(force=True, text="*romantic chirp*", color="magenta")

    def action_annoy(self):
        self.mood = "angry"
        self.state = "roll_left" if random.random() < 0.5 else "roll_right"
        self.is_rolling = True
        self.roll_timer.start(1200)
        self.show_random_message(force=True, text="Stop it!", color="red")

    def action_change_color(self):
        color = random.choice(["#ff9999", "#99ff99", "#9999ff", "#ffd699", "#d699ff"])
        self.set_tint(color, duration_ms=5000)
        self.show_random_message(force=True, text="Sparkle!", color="black")

    def reset_mood(self):
        self.mood = "happy"
        self.show_random_message(force=True, text="Reset!", color="black")

    # -------------------------
    # Pump / Notepad event
    # -------------------------
    def pump_event(self, note_text=None, show_line=None):
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
        tmp = os.path.join(os.getenv("TEMP", "."), f"billo_note_{random.randint(1000, 9999)}.txt")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(txt)
            subprocess.Popen(["notepad.exe", tmp])
            if IS_WINDOWS:
                QtCore.QTimer.singleShot(400, lambda p=tmp: self._bring_notepad_to_front(p))
        except Exception as e:
            print("Notepad open error:", e)

    def _bring_notepad_to_front(self, filepath):
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
                title = buf.value
                if basename in title:
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
        self.roll_timer.start(2000)
        self.show_random_message(force=True, text="Dizzy!", color="red")

    def end_roll(self):
        self.is_rolling = False
        self.state = "idle_right" if self.state.endswith("right") else "idle_left"
        self.frame_index = 0
        if self.mood == "angry":
            self.mood = "happy"

    def start_skid(self, right=True):
        self.state = "skid_right" if right else "skid_left"
        self.frame_index = 0
        self.skid_timer.start(600)

    def end_skid(self):
        self.state = "idle_right" if self.state.endswith("right") else "idle_left"
        self.frame_index = 0

    # Hurt blink: freezes movement until finished
    def _start_hurt_blink(self, duration_ms=1800, interval_ms=300):
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
        if self.mirrored:
            pix = pix.transformed(QtGui.QTransform().scale(-1, 1))
        if self.tint:
            pix = self._apply_tint(pix, self.tint)
        self.label.setPixmap(pix)
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
        if random.random() < 0.05:
            self.pump_event()
            return
        self.target_x = random.randint(0, max(0, self.screen.width() - self.width()))
        if random.random() < 0.1:
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
            # ensure velocity zeroed so she doesn't drift
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
                    # show angry/trapped message in red
                    self.show_random_message(force=True, angry=True)
                # freeze movement handled above by early return on mood == "trapped"
                return
            else:
                # if no longer intersecting, clear trap mood
                if self.mood == "trapped":
                    self.mood = "happy"

        # Normal wandering movement (same as earlier)
        if self.target_x is None or self.target_y is None:
            self.choose_target()

        dx = self.target_x - self.x()
        dy = self.target_y - self.y()
        prev_vx, prev_vy = self.vx, self.vy

        desired_vx = max(-self.max_speed, min(self.max_speed, dx))
        desired_vy = max(-self.max_speed, min(self.max_speed, dy))
        self.vx += (desired_vx - self.vx) * 0.2
        self.vy += (desired_vy - self.vy) * 0.2

        wave = math.sin(self.fly_angle) * (2 if self.is_flying else 0)
        if self.is_flying:
            self.fly_angle += 0.12

        nx = self.x() + self.vx
        ny = self.y() + self.vy + wave

        bumped = False
        if nx < 0:
            nx = 0
            self.vx = -self.vx * 0.6
            bumped = True
        if nx > self.screen.width() - self.width():
            nx = self.screen.width() - self.width()
            self.vx = -self.vx * 0.6
            bumped = True
        if bumped and abs(prev_vx) > 2:
            self.state = "bump_right" if prev_vx > 0 else "bump_left"
            self.frame_index = 0

        if ny < 0:
            ny = 0
            self.vy = -self.vy * 0.5

        self.move(int(nx), int(ny))

        # skid detection
        if abs(prev_vx) > 2.5 and abs(self.vx) < 0.6:
            self.start_skid(right=(prev_vx > 0))
            return

        # Animation selection
        if self.is_rolling:
            return
        if self.is_flying:
            self.state = "fly_right" if self.vx >= 0 else "fly_left"
        else:
            if abs(self.vx) < 0.5 and abs(self.vy) < 0.5:
                self.state = "idle_right" if self.state.endswith("right") else "idle_left"
            else:
                if abs(dx) >= abs(dy):
                    self.state = "run_right" if self.vx >= 0 else "run_left"
                else:
                    self.state = "idle_right" if self.state.endswith("right") else "idle_left"

    # -------------------------
    # Mouse events: drag -> drop
    # -------------------------
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.dragging = True
            self.drag_offset = event.pos()
            self.trap_start = QtGui.QCursor.pos()  # start selection-trap detection
            self.drag_timer.start(3000)  # if held for 3s -> dizzy roll

            # If clicked while flying -> force fall and angry
            if self.is_flying:
                self.is_flying = False
                self.falling = True
                self.vy = 5
                self.mood = "angry"
                self.show_random_message(force=True, angry=True)
            else:
                # small jump when clicked while on ground
                self.vy -= 6
                self.state = "jump_right" if self.vx >= 0 else "jump_left"
                self.mood = "happy"

    def mouseMoveEvent(self, event):
        if self.dragging:
            new_pos = self.mapToGlobal(event.pos() - self.drag_offset)
            self.move(new_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.dragging = False
            # release selection trap — stop detecting
            self.trap_start = None
            self.drag_timer.stop()
            # If she was angry (e.g., because clicked while flying) keep the mood until hurt
            # otherwise minor behavior: drop and hurt sequence
            # Start falling-to-bottom
            self.falling = True
            self.vy = 4.0
            self.state = "drop_right" if self.vx >= 0 else "drop_left"
            self.frame_index = 0
            self.mood = "angry"

    def _handle_falling(self):
        """Applies gravity while falling and triggers hurt-blink on landing."""
        if not self.falling:
            return
        self.vy += 0.9
        self.vx *= 0.98
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
            self.vy = -6
            self._start_hurt_blink(duration_ms=1800, interval_ms=300)


# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    pet = BilloRani()
    sys.exit(app.exec_())
