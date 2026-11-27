# Makes docs/guides/main-board-connections.pdf: every connection on the main board and why it is there.
# Holes are checked against design.py, so a moved part breaks this script instead of the document.
#
#   uv run --with matplotlib python kicad/main-board/scripts/make_connections.py
import os, sys, textwrap
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib
matplotlib.use("agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from design import PARTS, check

errors, *_ = check()
if errors:
    sys.exit("design.py has errors:\n" + "\n".join(errors))

OUT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
                                    "docs", "guides", "main-board-connections.pdf"))
plt.rcParams["font.family"] = "Arial"
W, H = 215.9, 279.4
PT = 72 / 25.4
INK = "#111111"

PIN = {f"{ref}.{name}": hole for ref, (_, _, pins) in PARTS.items() for name, hole, _ in pins}
def h(ref_pin):
    """'U1B.5V' -> 'W11'. Fails loudly if the pin is gone."""
    return PIN[ref_pin]

# (heading, [(from, to, why)])
SECTIONS = [
    ("POWER IN", [
        (f"Battery +  {h('J1.+')}", f"Mini360 IN+  {h('U3.IN+')}",
         "The Mini360 turns the 7.4 V battery into 5 V for the ESP32 and servo."),
        (f"Battery +  {h('J1.+')}", f"Driver VCC  {h('U2A.VCC')}",
         "Motors run straight off the battery for full power. The DRV8833 takes 2.7 to 10.8 V."),
        (f"Battery +  {h('J1.+')}", f"47k  {h('R1.1')}",
         "Top of the battery sensor. Lets the ESP32 see how full the battery is."),
        (f"Battery −  {h('J1.-')}", "every GND below",
         "All parts must share one 0 V, or voltages and signals mean nothing."),
    ]),
    ("GROUND (all one wire)", [
        ("GND", f"Mini360 IN−  {h('U3.IN-')}  and  OUT−  {h('U3.OUT-')}", "Return path for the Mini360."),
        ("GND", f"Driver GND  {h('U2A.GND')}", "Return path for the motor current."),
        ("GND", f"ESP32 GND  {h('U1B.GND')}", "Return path for the ESP32."),
        ("GND", f"10k  {h('R2.2')}", "Bottom of the battery sensor."),
        ("GND", f"470 µF −  {h('C1.-')}", "The capacitor sits between 5 V and GND."),
        ("GND", f"Servo GND  {h('J4.GND')}", "Return path for the servo (brown wire)."),
    ]),
    ("5 V", [
        (f"Mini360 OUT+  {h('U3.OUT+')}", f"ESP32 5V  {h('U1B.5V')}",
         "Powers the ESP32. It makes its own 3.3 V from this."),
        (f"Mini360 OUT+  {h('U3.OUT+')}", f"Servo +  {h('J4.5V')}",
         "The servo needs 5 V and more current than an ESP32 pin can give."),
        (f"Mini360 OUT+  {h('U3.OUT+')}", f"470 µF +  {h('C1.+')}",
         "Soaks up the servo's current spikes so the ESP32 does not reset."),
    ]),
    ("3.3 V", [
        (f"ESP32 3V3  {h('U1B.3V3')}", f"Driver EEP  {h('U2B.EEP')}",
         "EEP is the driver's ON switch. Held high, the driver is awake."),
    ]),
    ("BATTERY SENSE", [
        (f"ESP32 G3  {h('U1B.G3')}", f"47k  {h('R1.2')}  and  10k  {h('R2.1')}",
         "47k + 10k shrink 8.4 V to 1.5 V, safe for the pin. G3 can read voltage with Wi-Fi on."),
    ]),
    ("STEERING", [
        (f"ESP32 G0  {h('U1B.G0')}", f"Servo signal  {h('J4.SIG')}",
         "50 Hz pulse that sets the steering angle (orange wire)."),
    ]),
    ("MOTOR CONTROL", [
        (f"ESP32 G7  {h('U1A.G7')}", f"Driver IN1  {h('U2A.IN1')}", "Left motor, forward."),
        (f"ESP32 G10  {h('U1A.G10')}", f"Driver IN2  {h('U2A.IN2')}", "Left motor, reverse."),
        (f"ESP32 G6  {h('U1A.G6')}", f"Driver IN3  {h('U2A.IN3')}", "Right motor, forward."),
        (f"ESP32 G5  {h('U1A.G5')}", f"Driver IN4  {h('U2A.IN4')}", "Right motor, reverse."),
    ]),
    ("MOTORS", [
        (f"Driver OUT1  {h('U2B.OUT1')}", f"Left motor  {h('J2.1')}", "Left motor, one wire."),
        (f"Driver OUT2  {h('U2B.OUT2')}", f"Left motor  {h('J2.2')}", "Left motor, other wire."),
        (f"Driver OUT3  {h('U2B.OUT3')}", f"Right motor  {h('J3.1')}", "Right motor, one wire."),
        (f"Driver OUT4  {h('U2B.OUT4')}", f"Right motor  {h('J3.2')}", "Right motor, other wire."),
    ]),
]

NOT_USED = [
    f"Driver ULT  {h('U2B.ULT')}: fault output, the car does not need it.",
    "ESP32 G8, G9: boot pins. A motor wire here can stop the ESP32 from starting.",
    "ESP32 G20, G21: serial port, kept free for debugging.",
    "ESP32 G1, G2, G4: spare.",
]

TOP_WIRES = [
    "Battery +  L10 to N10: jumps over the GND wire on row M.",
    "3.3 V  T13 to K11: jumps over the GND and battery + wires.",
]


def page():
    fig = plt.figure(figsize=(W / 25.4, H / 25.4))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")
    return fig, ax


def T(ax, x, y, s, size=3.2, weight="normal", ha="left"):
    ax.text(x, y, s, fontsize=size * PT, ha=ha, va="center", weight=weight, color=INK)


X1, X2, X3 = 14, 56, 112           # from, to, why columns (mm)
LINE = 6.2
with PdfPages(OUT) as pdf:
    fig, ax = page()
    y = H - 18
    T(ax, X1, y, "MAIN BOARD CONNECTIONS", 5.0, "bold"); y -= 8
    T(ax, X1, y, "FROM", 2.8, "bold"); T(ax, X2, y, "TO", 2.8, "bold"); T(ax, X3, y, "WHY", 2.8, "bold")
    y -= 3
    for head, rows in SECTIONS:
        if y < 40:
            pdf.savefig(fig); plt.close(fig); fig, ax = page(); y = H - 18
        y -= 3
        T(ax, X1, y, head, 3.4, "bold"); y -= LINE
        for a, b, why in rows:
            T(ax, X1, y, a, 2.8); T(ax, X2, y, b, 2.8)
            for i, part in enumerate(textwrap.wrap(why, 58)):
                T(ax, X3, y - i * 4.2, part, 2.8)
            y -= LINE + 4.2 * (len(textwrap.wrap(why, 58)) - 1)
    for head, rows in [("NOT CONNECTED", NOT_USED), ("INSULATED TOP WIRES", TOP_WIRES)]:
        if y < 40:
            pdf.savefig(fig); plt.close(fig); fig, ax = page(); y = H - 18
        y -= 3
        T(ax, X1, y, head, 3.4, "bold"); y -= LINE
        for s in rows:
            T(ax, X1, y, "•  " + s); y -= LINE
    pdf.savefig(fig); plt.close(fig)
print("wrote", OUT)
