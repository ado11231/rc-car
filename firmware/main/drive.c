#include <stdbool.h>
#include "driver/gpio.h"
#include "driver/ledc.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "drive.h"

static const char *TAG = "drive";

#define SERVO_PIN GPIO_NUM_0
#define SERVO_HZ 50              // one pulse every 20 ms
#define SERVO_PERIOD_US 20000
#define SERVO_BITS 14            // duty goes from 0 to 16383

#define STEER_CENTER_US 1500
#define STEER_RANGE_US 400       // 1100..1900 µs, tune later on the car

#define TIMEOUT_US 500000        // No message after .5 means phone disconnected.

#define CHECK_US 100000          // Check every .1/s 

static int64_t last_msg_us = 0;  // Last joystick message.

static bool stopped = true;      // True once when already centered.

// Sends a pulse that is `us` microseconds long
static void set_pulse_us(int us) {
    uint32_t duty = (uint32_t)us * (1 << SERVO_BITS) / SERVO_PERIOD_US;
    ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, duty);
    ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0);
}

void drive_steer(int x) {
    last_msg_us = esp_timer_get_time();
    stopped = false;
    if (x < -100) x = -100;
    if (x > 100) x = 100;
    set_pulse_us(STEER_CENTER_US + x * STEER_RANGE_US / 100);
}


// Runs every 100 ms. Centers the wheels if the phone went quiet.
static void watchdog(void *arg) {
    if (!stopped && esp_timer_get_time() - last_msg_us > TIMEOUT_US) {
        stopped = true;
        set_pulse_us(STEER_CENTER_US);
        ESP_LOGW(TAG, "no signal, steering centered");
    }
}

void drive_start(void) {
    ledc_timer_config_t timer = {
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .timer_num = LEDC_TIMER_0,
        .duty_resolution = SERVO_BITS,
        .freq_hz = SERVO_HZ,
        .clk_cfg = LEDC_AUTO_CLK,
    };
    ESP_ERROR_CHECK(ledc_timer_config(&timer));

    ledc_channel_config_t channel = {
        .gpio_num = SERVO_PIN,
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .channel = LEDC_CHANNEL_0,
        .timer_sel = LEDC_TIMER_0,
        .duty = 0,
        .hpoint = 0,
    };
    ESP_ERROR_CHECK(ledc_channel_config(&channel));

    set_pulse_us(STEER_CENTER_US);

    const esp_timer_create_args_t check_args = {
        .callback = watchdog,
        .name = "drive_watchdog",
    };
    esp_timer_handle_t check_timer;
    ESP_ERROR_CHECK(esp_timer_create(&check_args, &check_timer));
    ESP_ERROR_CHECK(esp_timer_start_periodic(check_timer, CHECK_US));

    ESP_LOGI(TAG, "servo ready on G%d", SERVO_PIN);
}