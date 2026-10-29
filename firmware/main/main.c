#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "wifi.h"
#include "web.h"
#include "drive.h"

// Onboard blue LED, on when the pin is low
#define LED_PIN GPIO_NUM_8

static const char *TAG = "car";

void app_main(void)
{
    ESP_LOGI(TAG, "hello from the car");
    wifi_start();
    drive_start();
    web_start();

    gpio_reset_pin(LED_PIN);
    gpio_set_direction(LED_PIN, GPIO_MODE_OUTPUT);

    // Blinks once a second
    int on = 0;
    while (1) {
        on = !on;
        gpio_set_level(LED_PIN, on ? 0 : 1);
        ESP_LOGI(TAG, "led %s", on ? "on" : "off");
        vTaskDelay(pdMS_TO_TICKS(500));
    }
}
