#include "esp_adc/adc_oneshot.h"
#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"
#include "esp_log.h"
#include "battery.h"

static const char *TAG = "battery";

#define BATT_CHANNEL ADC_CHANNEL_3   // G3 is ADC1 channel 3
#define R_TOP 47                     // k ohm, battery + to G3
#define R_BOTTOM 10                  // k ohm, G3 to GND
#define EMPTY_MV 6600                // 3.3V per cell
#define FULL_MV 8400                 // 4.2V per cell
#define SAMPLES 16                   // Average 16 reads to smooth noise

static adc_oneshot_unit_handle_t adc;   // The ADC
static adc_cali_handle_t cali;          // Turns raw readings into mV

int battery_mv(void) {
    int sum = 0;
    for (int i = 0; i < SAMPLES; i++) {
        int mv = 0;
        adc_oneshot_get_calibrated_result(adc, cali, BATT_CHANNEL, &mv);
        sum += mv;
    }
    int pin_mv = sum / SAMPLES;                       // Voltage on G3
    return pin_mv * (R_TOP + R_BOTTOM) / R_BOTTOM;    // Undo the divider (x5.7)
}

int battery_percent(void) {
    int pct = (battery_mv() - EMPTY_MV) * 100 / (FULL_MV - EMPTY_MV);
    if (pct < 0) pct = 0;
    if (pct > 100) pct = 100;
    return pct;
}

void battery_start(void) {
    adc_oneshot_unit_init_cfg_t unit = { .unit_id = ADC_UNIT_1 };
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&unit, &adc));

    adc_oneshot_chan_cfg_t chan = {
        .atten = ADC_ATTEN_DB_12,           // G3 reads up to about 2.5V
        .bitwidth = ADC_BITWIDTH_DEFAULT,
    };
    ESP_ERROR_CHECK(adc_oneshot_config_channel(adc, BATT_CHANNEL, &chan));

    adc_cali_curve_fitting_config_t cal = {
        .unit_id = ADC_UNIT_1,
        .chan = BATT_CHANNEL,
        .atten = ADC_ATTEN_DB_12,
        .bitwidth = ADC_BITWIDTH_DEFAULT,
    };
    ESP_ERROR_CHECK(adc_cali_create_scheme_curve_fitting(&cal, &cali));

    ESP_LOGI(TAG, "ready on G3, %d mV", battery_mv());
}
