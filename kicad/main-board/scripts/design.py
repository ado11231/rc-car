"""Aliftmobile main board: perf board layout.

Board: 5 x 7 cm perf board, 2.54 mm holes.
Rows A-X run along the 7 cm side (A = back of the car, X = front).
Columns 1-18 run along the 5 cm side (1 = car's left, seen from the top).

Every wire is listed as a path of holes. "bottom" = bare wire soldered
under the board. "top" = insulated wire on the top side. Run this file
to check the layout: every pin of a net must be reached, and no hole
may be used by two different nets on the same side.
"""
ROWS = "ABCDEFGHIJKLMNOPQRSTUVWX"

def rc(hole):
    return ROWS.index(hole[0]), int(hole[1:])

def line(*corners):
    """Holes on a straight-line path through the given corners."""
    out = [corners[0]]
    for a, b in zip(corners, corners[1:]):
        (r1, c1), (r2, c2) = rc(a), rc(b)
        assert r1 == r2 or c1 == c2, f"{a}->{b} is not straight"
        n = max(abs(r2 - r1), abs(c2 - c1))
        for i in range(1, n + 1):
            r = r1 + (r2 - r1) * i // n
            c = c1 + (c2 - c1) * i // n
            out.append(f"{ROWS[r]}{c}")
    return out

# ---- Parts: ref -> (kind, label, [(pin name, hole, net)]) --------------
# Every module is placed the way it really sits, parts side up, seen from the top.
# Checked against the working breadboard (2026-11-23) by turning it on the table:
#   breadboard rows 11-18 / columns c,g  ->  perf columns, rows Q,W.
# ESP32-C3 SuperMini: chip up, USB toward column 11. 5V side on row W, G5 side on row Q.
ESP_W = ["5V", "GND", "3V3", "G4", "G3", "G2", "G1", "G0"]     # W11 .. W18
ESP_Q = ["G5", "G6", "G7", "G8", "G9", "G10", "G20", "G21"]   # Q11 .. Q18
ESP_NET = {"5V": "+5V", "GND": "GND", "3V3": "+3V3", "G3": "BATT_SENSE", "G0": "SERVO_SIG",
           "G7": "IN1", "G10": "IN2", "G6": "IN3", "G5": "IN4"}    # firmware motor_pins = {7, 10, 6, 5}

PARTS = {
    "U1A": ("socket8", "ESP32-C3", [(p, f"Q{11 + i}", ESP_NET.get(p)) for i, p in enumerate(ESP_Q)]),
    "U1B": ("socket8", "ESP32-C3", [(p, f"W{11 + i}", ESP_NET.get(p)) for i, p in enumerate(ESP_W)]),
    # HW-627 (DRV8833): chip up, labels underneath. IN side on row N (IN1 at column 16),
    # OUT side on row H (EEP at column 11).
    "U2A": ("socket6", "HW-627", list(zip(["IN4", "IN3", "GND", "VCC", "IN2", "IN1"],
                                         [f"N{c}" for c in range(11, 17)],
                                         ["IN4", "IN3", "GND", "VBAT", "IN2", "IN1"]))),
    "U2B": ("socket6", "HW-627", list(zip(["EEP", "OUT1", "OUT2", "OUT3", "OUT4", "ULT"],
                                         [f"H{c}" for c in range(11, 17)],
                                         ["+3V3", "OUT1", "OUT2", "OUT3", "OUT4", None]))),
    # Mini360 (adjustable, set to 5.1 V first). Screw up, IN end toward the back.
    # Pins measured on the breadboard: 4 holes apart across, 6 holes apart lengthwise.
    "U3":  ("mini360", "Mini360", [("IN+", "F7", "VBAT"), ("IN-", "F3", "GND"),
                                    ("OUT+", "L7", "+5V"), ("OUT-", "L3", "GND")]),
    "J1":  ("term2", "BATTERY", [("-", "B1", "GND"), ("+", "B3", "VBAT")]),
    "J2":  ("term2", "LEFT MOTOR", [("1", "B10", "OUT1"), ("2", "B12", "OUT2")]),
    "J3":  ("term2", "RIGHT MOTOR", [("1", "B14", "OUT3"), ("2", "B16", "OUT4")]),
    # Servo plug: brown GND (back), red 5V (middle), orange signal (front).
    "J4":  ("header3", "SERVO", [("GND", "T2", "GND"), ("5V", "U2", "+5V"), ("SIG", "V2", "SERVO_SIG")]),
    "C1":  ("cap", "470uF", [("+", "P3", "+5V"), ("-", "P1", "GND")]),
    # Battery sense: both resistors lie flat under the ESP and form one chain:
    # VBAT -> 47k (down column 15) -> G3 node at U15/V15 -> 10k (along row V) -> GND.
    # 10k already soldered at V12-V15 (2026-11-24).
    "R1":  ("res", "47k", [("1", "R15", "VBAT"), ("2", "U15", "BATT_SENSE")]),
    "R2":  ("res", "10k", [("1", "V15", "BATT_SENSE"), ("2", "V12", "GND")]),
}

# ---- Wires: net -> list of (side, [holes]) ------------------------------
# Found with a grid router (bottom first, insulated top wire only where a crossing is unavoidable).
WIRES = {
    "VBAT": [
        ("bottom", line("N14", "L14", "L10")),
        ("top", line("L10", "N10")),
        ("bottom", line("N10", "R10", "R15")),
        ("bottom", line("L10", "F10", "F7")),
        ("bottom", line("F7", "B7", "B3")),
    ],
    "GND": [
        ("bottom", line("W12", "T12", "T9", "M9", "M13", "N13")),
        ("bottom", line("M9", "K9", "K2", "T2")),
        ("bottom", line("P2", "P1")),
        ("bottom", line("L2", "L3")),
        ("bottom", line("K3", "F3")),
        ("bottom", line("F3", "F1", "B1")),
    ],
    "+5V": [
        ("bottom", line("W11", "U11", "U2")),
        ("bottom", line("U7", "L7")),
        ("bottom", line("P7", "P3")),
    ],
    "+3V3": [
        ("bottom", line("W13", "T13")),
        ("top", line("T13", "T9", "K9", "K11")),
        ("bottom", line("K11", "H11")),
    ],
    "BATT_SENSE": [
        ("bottom", line("W15", "U15")),
    ],
    "SERVO_SIG": [
        ("bottom", line("W18", "X18", "X2", "V2")),
    ],
    "IN1": [
        ("bottom", line("Q13", "O13", "O16", "N16")),
    ],
    "IN2": [
        ("bottom", line("Q16", "P16", "P17", "M17", "M15", "N15")),
    ],
    "IN3": [
        ("bottom", line("Q12", "N12")),
    ],
    "IN4": [
        ("bottom", line("Q11", "N11")),
    ],
    "OUT1": [
        ("bottom", line("H12", "C12", "C10", "B10")),
    ],
    "OUT2": [
        ("bottom", line("H13", "B13", "B12")),
    ],
    "OUT3": [
        ("bottom", line("H14", "B14")),
    ],
    "OUT4": [
        ("bottom", line("H15", "B15", "B16")),
    ],
}

def check():
    pad = {}
    for ref, (_, _, pins) in PARTS.items():
        for name, hole, net in pins:
            assert hole not in pad, f"{hole} has two pins"
            pad[hole] = (net, f"{ref}.{name}")
    errors = []
    side_use = {"bottom": {}, "top": {}}
    vias = {}
    for net, runs in WIRES.items():
        for side, holes in runs:
            for hole in holes:
                if hole in pad and pad[hole][0] != net:
                    errors.append(f"{net} {side} wire goes through {hole} ({pad[hole][1]}, net {pad[hole][0]})")
                other = side_use[side].get(hole)
                if other and other != net:
                    errors.append(f"{net} and {other} both use {hole} on the {side}")
                side_use[side][hole] = net
            if side == "top":
                for end in (holes[0], holes[-1]):
                    if end not in pad: vias[end] = net
    # bottom wires may not run through a hole where a top wire goes down
    for hole, net in vias.items():
        if side_use["bottom"].get(hole) not in (None, net):
            errors.append(f"top wire end {hole} lands on another net")
    # connectivity: union-find over holes
    parent = {}
    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for net, runs in WIRES.items():
        for side, holes in runs:
            for a, b in zip(holes, holes[1:]):
                parent[find(a)] = find(b)
    for net in {n for n, _ in pad.values() if n}:
        holes = [hh for hh, (n, _) in pad.items() if n == net]
        groups = {find(hh) for hh in holes}
        if len(groups) != 1:
            errors.append(f"{net} is split into {len(groups)} pieces: {sorted(holes)}")
    # unconnected pins must not touch any wire
    for hole, (net, who) in pad.items():
        if net is None and (hole in side_use["bottom"] or hole in side_use["top"]):
            errors.append(f"wire touches unused pin {who} at {hole}")
    bottom_len = sum(len(h) - 1 for runs in WIRES.values() for s, h in runs if s == "bottom")
    top_len = sum(len(h) - 1 for runs in WIRES.values() for s, h in runs if s == "top")
    return errors, bottom_len, top_len, vias

if __name__ == "__main__":
    errors, b, t, v = check()
    print("\n".join(errors) if errors else "OK: every net connected, no shared holes")
    print(f"bare wire: {b} hole steps ({b * 2.54 / 10:.1f} cm), insulated top wire: {t} steps ({t * 2.54 / 10:.1f} cm), top wire ends: {sorted(v)}")
