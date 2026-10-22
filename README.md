<h1 align="center">BE1200 CAD rc-car</h1>

* A small 3D printed RC car you drive from your phone.
* The brain is an ESP32-C3. It makes its own Wi-Fi. Join it, open the page, drive with the joystick. No app.
* Rear motors drive, a servo steers the front wheels.
* Underglow in any color, red when braking. Battery level shows on the phone.
* 7 printed parts. Everything else is bought.
* Code is plain C on ESP-IDF.

## Build The Code

* Needs [ESP-IDF](https://docs.espressif.com/projects/esp-idf/en/stable/esp32c3/get-started/index.html) v6.0 or newer.

```sh
# load the ESP-IDF tools (once per terminal)
. ~/esp/esp-idf/export.sh

cd firmware
idf.py build
idf.py flash monitor
```

* Plug the board in with USB. Press Ctrl+] to leave the monitor.
* Never plug in USB while the battery is on.

## Docs

* [Architecture](docs/architecture.md): how the car is built, wired and coded.
* [Printed parts](docs/printed-parts/README.md): drawings and pictures for each print.
