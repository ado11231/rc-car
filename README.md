<h3 align="center">Aliftmobile</h3>

#### Overview

A small 3D-printed RC car you drive from your phone. Final project for BE1200 CAD, Section 2, Team 8.

* The car makes its own Wi-Fi. Join it, open a web page, and drive with two on-screen joysticks. No app needed.
* Two rear motors drive the car and a servo steers the front wheels.
* If the phone stops talking to the car for half a second, the car stops.
* 7 printed parts. The motors, servo, battery and boards are bought.

#### Usage

1. Turn the car on.
2. On your phone, join the Wi-Fi network **rc-car** (password **drive1234**).
3. Open **http://192.168.4.1**.
4. Hold the phone sideways. The left stick controls speed and the right stick controls steering.

#### Team

| Name | Role |
| --- | --- |
| Adnan Alagic | Electronics, wiring, main board, firmware, control page |
| Kai McEachern | Chassis plate, front bumper, assembly |
| Alif Ahmed | Steering beam, antenna, assembly |
| Mohanad Thabet | Battery tray, servo box, tow hook |

#### Repository Layout

| Folder | Contents |
| --- | --- |
| `firmware/` | Car firmware |
| `nx/` | NX part files (.prt) |
| `nx/pdf/` | Part drawings |
| `nx/assembly/` | Assembly and exploded view (.prt and .pdf) |
| `stl/` | Print files |
| `docs/` | Wiring and build documentation |

#### Building the Firmware

Written in C with [ESP-IDF](https://docs.espressif.com/projects/esp-idf/en/stable/esp32c3/get-started/index.html) v6.0 or newer.

```sh
. ~/esp/esp-idf/export.sh   # once per terminal
cd firmware
idf.py build flash monitor
```

* Connect the board over USB. Press Ctrl+] to exit the monitor.
* Never connect USB while the battery is on.

#### Documentation

* [Architecture](docs/architecture.md): wiring, pin assignments and how the parts fit together.
* [Printed Parts](docs/printed-parts/README.md): what each printed part does.
