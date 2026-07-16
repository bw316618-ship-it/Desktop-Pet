# Sprite frames

`br.py` loads its animation frames from PNG files sitting **next to the
script** (not from this `assets/` folder by default — see note below).
The PDF this project was recovered from didn't include the actual image
files, only the code that references them, so you'll need to supply your
own 18x18px sprite PNGs (they get scaled up 4x at runtime) with these
exact names:

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

Missing files are handled gracefully — the script prints a `(warn) missing
<file>` line and simply skips that frame — so it will still run without
any art, you just won't see the pet.

If you'd rather keep sprites in this `assets/` folder, change this line
near the top of `BilloRani.__init__`:

```python
self.sprites_path = os.path.dirname(os.path.abspath(__file__))
```

to:

```python
self.sprites_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
```
