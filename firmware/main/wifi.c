#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "wifi.h"

// The network the phone joins
#define CAR_SSID "rc-car"
#define CAR_PASSWORD "drive1234"
#define CAR_CHANNEL 1
#define MAX_PHONES 1

static const char *TAG = "wifi";

// Called on every Wi-Fi event, like a phone joining
static void on_wifi_event(void *arg, esp_event_base_t base, int32_t id, void *data) {
    if (id == WIFI_EVENT_AP_STACONNECTED) {
        ESP_LOGI(TAG, "phone joined");
    } else if (id == WIFI_EVENT_AP_STADISCONNECTED) {
        ESP_LOGI(TAG, "phone left");
    }
}

void wifi_start(void) {
    // Wi-Fi keeps its settings in NVS. If NVS is full or old, wipe it and retry.
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);

    // Network plumbing: IP layer, event system, access point
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_ap();

    // Wi-Fi driver with default settings
    wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init));

    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, on_wifi_event, NULL));

    // Our network's settings
    wifi_config_t config = {
        .ap = {
            .ssid = CAR_SSID,
            .password = CAR_PASSWORD,
            .channel = CAR_CHANNEL,
            .max_connection = MAX_PHONES,
            .authmode = WIFI_AUTH_WPA2_PSK,
        },
    };

    // Run as an access point
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &config));
    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(TAG, "network \"%s\" is up", CAR_SSID);
}
