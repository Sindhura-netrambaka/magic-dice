# SSD1306 I2C driver for MicroPython (Wokwi-safe): no start()/stop() calls
import framebuf

class SSD1306:
    def __init__(self, width, height, external_vcc):
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.pages = self.height // 8
        self.buffer = bytearray(self.pages * self.width)
        self.framebuf = framebuf.FrameBuffer(self.buffer, self.width, self.height, framebuf.MONO_VLSB)
        self.init_display()

    def init_display(self):
        init = (
            0xAE,       # display off
            0x20, 0x00, # horizontal addressing
            0x40,       # start line = 0
            0xA1,       # segment remap
            0xC8,       # COM scan dec
            0xDA, 0x12, # COM pins
            0x81, 0xCF, # contrast
            0xA4,       # display all on resume
            0xA6,       # normal display
            0xD5, 0x80, # clock
            0x8D, 0x14 if not self.external_vcc else 0x10, # charge pump
            0xD9, 0xF1, # pre-charge
            0xDB, 0x40, # VCOM detect
            0xAF        # display on
        )
        for cmd in init:
            self.write_cmd(cmd)
        self.fill(0)
        self.show()

    def poweroff(self): self.write_cmd(0xAE)
    def poweron(self): self.write_cmd(0xAF)
    def contrast(self, c): self.write_cmd(0x81); self.write_cmd(c & 0xFF)
    def invert(self, inv): self.write_cmd(0xA7 if inv else 0xA6)

    def show(self):
        for page in range(self.pages):
            self.write_cmd(0xB0 | page)  # set page
            self.write_cmd(0x02)         # set lower column
            self.write_cmd(0x10)         # set higher column
            start = page * self.width
            end = start + self.width
            self.write_data(self.buffer[start:end])

    # FrameBuffer passthrough
    def fill(self, c): self.framebuf.fill(c)
    def pixel(self, x, y, c): self.framebuf.pixel(x, y, c)
    def text(self, s, x, y, c=1): self.framebuf.text(s, x, y, c)
    def hline(self, x, y, w, c): self.framebuf.hline(x, y, w, c)
    def vline(self, x, y, h, c): self.framebuf.vline(x, y, h, c)
    def line(self, x1, y1, x2, y2, c): self.framebuf.line(x1, y1, x2, y2, c)
    def rect(self, x, y, w, h, c): self.framebuf.rect(x, y, w, h, c)
    def fill_rect(self, x, y, w, h, c): self.framebuf.fill_rect(x, y, w, h, c)

class SSD1306_I2C(SSD1306):
    def __init__(self, width, height, i2c, addr=0x3C, external_vcc=False):
        self.i2c = i2c
        self.addr = addr
        super().__init__(width, height, external_vcc)

    def write_cmd(self, cmd):
        # control byte 0x80 = next byte is a command
        self.i2c.writeto(self.addr, bytes((0x80, cmd & 0xFF)))

    def write_data(self, buf):
        # control byte 0x40 = following bytes are data
        if isinstance(buf, memoryview):
            buf = bytes(buf)
        self.i2c.writeto(self.addr, b'\x40' + buf)
