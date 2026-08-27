"""Virtual gamepad over /dev/uinput, for ES-DE attract mode.

ES-DE runs with SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS=1, so SDL polls joysticks
regardless of window focus — which is why a controller drives ES-DE while you
type elsewhere, but synthetic keystrokes do not. Emitting gamepad events instead
of keystrokes lets attract mode run while you work in another window.

The device deliberately mimics the real 8BitDo's vendor/product/name so SDL
applies the same controller mapping ES-DE already knows. That means the watcher
cannot tell them apart by name — it excludes this device by its event node path,
which we resolve after creation.
"""
import os, fcntl, struct, ctypes, time, glob

UINPUT = "/dev/uinput"
EV_SYN, EV_KEY, EV_ABS = 0x00, 0x01, 0x03
SYN_REPORT = 0
UI_SET_EVBIT, UI_SET_KEYBIT, UI_SET_ABSBIT = 0x40045564, 0x40045565, 0x40045567
UI_DEV_CREATE, UI_DEV_DESTROY = 0x5501, 0x5502
UI_GET_SYSNAME = 0x8040552C          # _IOC(READ, 'U', 44, len)

BTN_SOUTH, BTN_EAST, BTN_NORTH, BTN_WEST = 0x130, 0x131, 0x133, 0x134
BTN_START, BTN_SELECT = 0x13b, 0x13a
ABS_HAT0X, ABS_HAT0Y = 0x10, 0x11

# A generic, honestly-named device. SDL derives its GUID from bus+name-CRC+
# vendor+product+version, so a distinct name yields a distinct GUID and ES-DE
# falls back to "default configuration" — which navigates fine, as tested.
# 0x1209 is pid.codes, the USB vendor ID reserved for open-source projects,
# so this device claims to be exactly what it is. Borrowing a real vendor's
# ID (e.g. Microsoft's 045E) makes SDL substitute that vendor's product name,
# which would misrepresent the device in ES-DE's controller list.
VENDOR, PRODUCT, VERSION = 0x1209, 0xE5DE, 0x0001
NAME = b"ES-DE Attract Virtual Pad"

class AbsInfo(ctypes.Structure):
    _fields_ = [("value", ctypes.c_int32), ("minimum", ctypes.c_int32),
                ("maximum", ctypes.c_int32), ("fuzz", ctypes.c_int32),
                ("flat", ctypes.c_int32), ("resolution", ctypes.c_int32)]

class UinputUserDev(ctypes.Structure):
    _fields_ = [("name", ctypes.c_char * 80),
                ("id_bustype", ctypes.c_uint16), ("id_vendor", ctypes.c_uint16),
                ("id_product", ctypes.c_uint16), ("id_version", ctypes.c_uint16),
                ("ff_effects_max", ctypes.c_uint32),
                ("absmax", ctypes.c_int32 * 64), ("absmin", ctypes.c_int32 * 64),
                ("absfuzz", ctypes.c_int32 * 64), ("absflat", ctypes.c_int32 * 64)]

class VirtualPad:
    def __init__(self):
        self.fd = os.open(UINPUT, os.O_WRONLY | os.O_NONBLOCK)
        for b in (BTN_SOUTH, BTN_EAST, BTN_NORTH, BTN_WEST, BTN_START, BTN_SELECT):
            fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_KEY)
            fcntl.ioctl(self.fd, UI_SET_KEYBIT, b)
        fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_ABS)
        for a in (ABS_HAT0X, ABS_HAT0Y):
            fcntl.ioctl(self.fd, UI_SET_ABSBIT, a)
        dev = UinputUserDev()
        dev.name = NAME[:79]
        dev.id_bustype, dev.id_vendor = 0x03, VENDOR      # 0x03 = USB
        dev.id_product, dev.id_version = PRODUCT, VERSION
        for a in (ABS_HAT0X, ABS_HAT0Y):
            dev.absmin[a], dev.absmax[a] = -1, 1
        os.write(self.fd, bytes(dev))
        fcntl.ioctl(self.fd, UI_DEV_CREATE)
        time.sleep(0.4)                                   # let udev create the node
        self.sysname = self._sysname()
        self.event_path = self._event_path()

    def _sysname(self):
        buf = ctypes.create_string_buffer(64)
        try:
            fcntl.ioctl(self.fd, UI_GET_SYSNAME, buf)
            return buf.value.decode()
        except OSError:
            return ""

    def _event_path(self):
        """Resolve OUR event node so the input watcher can ignore it.

        The name is distinct from any real device, so the watcher could also
        filter by name — the path is kept as the primary key because it is
        unambiguous even if a user renames the device.
        """
        if self.sysname:
            for p in glob.glob(f"/sys/devices/virtual/input/{self.sysname}/event*"):
                return "/dev/input/" + os.path.basename(p)
        # fall back: newest virtual input event node
        cands = sorted(glob.glob("/sys/devices/virtual/input/input*/event*"),
                       key=lambda p: os.stat(p).st_mtime)
        return "/dev/input/" + os.path.basename(cands[-1]) if cands else ""

    def _emit(self, etype, code, value):
        # struct input_event: two longs (timeval), u16, u16, s32
        os.write(self.fd, struct.pack("llHHi", 0, 0, etype, code, value))

    def _syn(self):
        self._emit(EV_SYN, SYN_REPORT, 0)

    def dpad(self, dx=0, dy=0, hold=0.06):
        if dx: self._emit(EV_ABS, ABS_HAT0X, dx)
        if dy: self._emit(EV_ABS, ABS_HAT0Y, dy)
        self._syn(); time.sleep(hold)
        if dx: self._emit(EV_ABS, ABS_HAT0X, 0)
        if dy: self._emit(EV_ABS, ABS_HAT0Y, 0)
        self._syn()

    def press(self, btn, hold=0.06):
        self._emit(EV_KEY, btn, 1); self._syn(); time.sleep(hold)
        self._emit(EV_KEY, btn, 0); self._syn()

    def close(self):
        try:
            fcntl.ioctl(self.fd, UI_DEV_DESTROY)
        except OSError:
            pass
        os.close(self.fd)

if __name__ == "__main__":
    p = VirtualPad()
    print(f"  created virtual pad: sysname={p.sysname or '?'} node={p.event_path or '?'}")
    time.sleep(1)
    print("  sending 3 x dpad-down")
    for _ in range(3):
        p.dpad(dy=1); time.sleep(0.4)
    time.sleep(1)
    p.close()
    print("  destroyed")
