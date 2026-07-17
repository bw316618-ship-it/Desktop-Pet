# Sprite frames

All 34 sprite PNGs Billo Rani needs live in this folder, and `br.py` is
already pointed here (`self.sprites_path` resolves to `assets/` next to
the script — or to the bundled data folder when running as the built
`.exe`). Nothing to configure — just run the script or the exe.

```
standl.png   standr.png
runl1.png    runl2.png    runl3.png
runr1.png    runr2.png    runr3.png
flyingl1.png flyingl2.png flyingl3.png
flyingr1.png flyingr2.png flyingr3.png
pumpl1.png   pumpl2.png   pumpl3.png
pumpr1.png   pumpr2.png   pumpr3.png
roll1.png    roll2.png    roll3.png    roll4.png
jumpl.png    jumpr.png
bumpl.png    bumpr.png
dropl.png    dropr.png
skidl.png    skidr.png
hurt.png     hurt2.png
```

Frames are loaded at their native size and scaled up 4x at runtime
(`BilloRani.SCALE`). If you want to swap in your own art, just replace a
file — keep the same filename and roughly the same aspect ratio (18x18px
originals) and it'll drop right in. Missing files are handled gracefully:
the script prints a `(warn) missing <file>` line and skips that frame
instead of crashing.
