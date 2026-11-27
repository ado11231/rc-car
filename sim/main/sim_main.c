// Fake phone: plays a joystick pattern into the real drive.c, then goes quiet
// so the 0.5 s auto-stop kicks in. Battery % is read from the slider on G3.
// Wokwi project: https://wokwi.com/projects/481590401519528961 (wiring = diagram.json, then F1 -> Upload Firmware -> sim/rc-car-sim.bin)
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "drive.h"
#include "battery.h"

static const char *TAG = "sim";

typedef struct { int x, y, ms; const char *what; } step_t;

static const step_t steps[] = {
    {   0,    0, 2000, "centered, stopped" },
    {   0,   50, 3000, "forward 50%" },
    {   0,  100, 3000, "forward 100% (70% duty cap)" },
    { -100,  60, 3000, "forward + full left" },
    {  100,  60, 3000, "forward + full right" },
    {   0,  -60, 3000, "back 60%" },
    {   0,    0, 2000, "let go (stick back to 0)" },
};

void app_main(void) {
    drive_start();
    battery_start();
    while (1) {
        for (int i = 0; i < sizeof steps / sizeof steps[0]; i++) {
            const step_t *s = &steps[i];
            ESP_LOGI(TAG, "x=%d y=%d  %s  | battery %d mV, %d%%",
                     s->x, s->y, s->what, battery_mv(), battery_percent());
            for (int t = 0; t < s->ms; t += 50) {   // like the phone: every 50 ms
                drive_steer(s->x);
                drive_speed(s->y);
                vTaskDelay(pdMS_TO_TICKS(50));
            }
        }
        ESP_LOGW(TAG, "phone goes quiet at full forward -> auto-stop should fire");
        drive_steer(0);
        drive_speed(100);
        vTaskDelay(pdMS_TO_TICKS(3000));
    }
}
