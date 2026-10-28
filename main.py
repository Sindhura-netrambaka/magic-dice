# Spin-Wheel Dice — Wokwi (Pico W, MicroPython)
# Hardware in your diagram.json:
# - SSD1306 I2C OLED: SDA=GP6, SCL=GP7 (addr 0x3C)
# - LED ring (wokwi-led-ring): DIN=GP10, VBUS/GND as wired
# - KY-040 rotary encoder: CLK=GP2, DT=GP3, SW=GP4  (SW unused)
# - Touch pushbutton: GP8 -> GND

import time, math, urandom
from machine import Pin, I2C
import neopixel
from ssd1306 import SSD1306_I2C

# ---------- Pins / devices ----------
I2C_SDA, I2C_SCL = 6, 7
LED_PIN, LED_NUM = 10, 24
ENC_A, ENC_B, ENC_SW = 2, 3, 4
TOUCH_PIN = 8

i2c  = I2C(1, sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=400000)
oled = SSD1306_I2C(128, 64, i2c)
np   = neopixel.NeoPixel(Pin(LED_PIN, Pin.OUT), LED_NUM)

enc_a = Pin(ENC_A, Pin.IN, Pin.PULL_UP)
enc_b = Pin(ENC_B, Pin.IN, Pin.PULL_UP)
enc_sw = Pin(ENC_SW, Pin.IN, Pin.PULL_UP)
touch_btn = Pin(TOUCH_PIN, Pin.IN, Pin.PULL_UP)

# ---------- LED helpers ----------
def leds_clear():
    for i in range(LED_NUM):
        np[i] = (0,0,0)
    np.write()

def leds_idle(level=0.05):
    """Dim static halo (no rotation in idle)."""
    lvl = int(255 * max(0.02, min(0.2, level)))
    for i in range(LED_NUM):
        np[i] = (lvl, lvl, lvl)
    np.write()

def leds_sweep(level, direction=1):
    """Rotating sweep proportional to spin speed."""
    n = LED_NUM
    lit = max(1, min(n, int(n * max(0.08, min(1.0, level)))))
    base = (time.ticks_ms() // 30) % n
    for i in range(n):
        on = 90 if ((i - direction*base) % n) < lit else 0
        np[i] = (on,on,on)
    np.write()

def leds_pulse(times=2, hold_ms=120):
    for _ in range(times):
        for i in range(LED_NUM): np[i]=(160,160,160)
        np.write(); time.sleep_ms(hold_ms)
        leds_idle()

# ---------- OLED dice gfx (simple) ----------
def draw_die(x, y, s, v):
    oled.fill_rect(x, y, s, s, 0); oled.rect(x, y, s, s, 1)
    cx, cy, off = x+s//2, y+s//2, s//4
    def pip(px, py): oled.fill_rect(px-1, py-1, 3, 3, 1)
    if v in (1,3,5): pip(cx, cy)
    if v in (2,3,4,5,6): pip(x+off, y+off); pip(x+s-off, y+s-off)
    if v in (4,5,6): pip(x+off, y+s-off); pip(x+s-off, y+off)
    if v==6: pip(x+off, cy); pip(x+s-off, cy)

def show_result(d1, d2):
    oled.fill(0)
    w,h=128,64; s=24; g=8
    x1=(w-(2*s+g))//2; y=(h-s)//2; x2=x1+s+g
    draw_die(x1,y,s,d1); draw_die(x2,y,s,d2)
    total=d1+d2
    oled.fill_rect(10, h-10, int((w-20)*total/12), 6, 1)
    oled.show()

def animate_roll(ms=800, vigor=1.0):
    t0=time.ticks_ms()
    w,h=128,64; s=24; g=8
    x1=(w-(2*s+g))//2; y=(h-s)//2; x2=x1+s+g
    while time.ticks_diff(time.ticks_ms(), t0)<ms:
        d1=(urandom.getrandbits(8)%6)+1
        d2=(urandom.getrandbits(8)%6)+1
        dx=(urandom.getrandbits(3)-4); dy=(urandom.getrandbits(3)-4)
        oled.fill(0)
        draw_die(x1+dx,y+dy,s,d1); draw_die(x2-dx,y-dy,s,d2)
        oled.show()
        time.sleep_ms(30 if vigor>=0.6 else 45)

def splash():
    oled.fill(0)
    oled.text("Spin Wheel Dice", 6, 10, 1)
    oled.text("Rotate encoder", 10, 28, 1)
    oled.text("or press TOUCH", 6, 40, 1)
    oled.show()

# ---------- KY-040 polling (quadrature) ----------
# Robust state machine (no IRQ). Sample every 1–2 ms.
prev_ab = (enc_a.value()<<1) | enc_b.value()
enc_pos = 0

def poll_encoder():
    """Return delta counts since last call (+/-)."""
    global prev_ab, enc_pos
    a = enc_a.value(); b = enc_b.value()
    ab = (a<<1)|b
    delta = 0
    if ab != prev_ab:
        # CW sequence: 00->01->11->10->00 ; CCW is reverse
        cw  = (prev_ab==0 and ab==1) or (prev_ab==1 and ab==3) or (prev_ab==3 and ab==2) or (prev_ab==2 and ab==0)
        ccw = (prev_ab==0 and ab==2) or (prev_ab==2 and ab==3) or (prev_ab==3 and ab==1) or (prev_ab==1 and ab==0)
        if cw:  delta = +1
        elif ccw: delta = -1
        prev_ab = ab
        enc_pos += delta
    return delta

# ---------- Spin energy model ----------
E = 0.0                 # accumulated energy
last_roll = -10_000
ROLL_LOCK_MS = 1500

def fair_dice():
    return (urandom.getrandbits(8)%6)+1, (urandom.getrandbits(8)%6)+1

# ---------- Main loop ----------
splash()
leds_idle()

dt_ms = 1    # 500 Hz loop
scale = 0.06 # encoder counts -> "rev/s" feel scaler
deadband = 0.01
trigger_E = 0.000020

while True:
    t0 = time.ticks_ms()

    # 1) Read encoder (quadrature)
    dp = poll_encoder()
    omega = dp * scale             # pseudo rev/s
    aomega = abs(omega)

    # 2) LED behaviour
    if aomega > deadband:
        leds_sweep(min(1.0, aomega/5.0), 1 if omega>0 else -1)
        E += (aomega*aomega) * (dt_ms/1000.0)
    else:
        leds_idle(0.06)

    # 3) Touch button = gentle throw when idle
    touch_pressed = (touch_btn.value() == 0)

    # 4) Trigger logic
    now = time.ticks_ms()
    do_throw = False
    if (E > trigger_E) and (now - last_roll > ROLL_LOCK_MS):
        do_throw = True
    if touch_pressed and (now - last_roll > ROLL_LOCK_MS):
        E = max(E, 0.25)  # small assist for light animation
        do_throw = True

    # 5) Execute throw
    if do_throw:
        last_roll = now
        vigor = min(1.0, E/1.2)
        anim_ms = int(600 + min(700, E*900))
        animate_roll(anim_ms, vigor)
        d1,d2 = fair_dice()
        show_result(d1,d2)
        print({"d1":d1,"d2":d2,"total":d1+d2,"E":round(E,3)})
        leds_pulse(2,120)
        E = 0.0

    # pace loop
    elapsed = time.ticks_ms() - t0
    if elapsed < dt_ms:
        time.sleep_ms(dt_ms - elapsed)
