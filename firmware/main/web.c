#include <stdio.h>
#include "esp_http_server.h"
#include "esp_log.h"
#include "web.h"
#include "drive.h"
#include "battery.h"

static const char *TAG = "web";

// index.html, baked into flash by CMake (EMBED_TXTFILES)
extern const char index_html[] asm("_binary_index_html_start");

// GET / sends the joystick page
static esp_err_t root_handler(httpd_req_t *req) {
    httpd_resp_set_type(req, "text/html");
    httpd_resp_send(req, index_html, HTTPD_RESP_USE_STRLEN);
    return ESP_OK;
}

static const httpd_uri_t root = {
    .uri = "/",
    .method = HTTP_GET,
    .handler = root_handler,
};

// /ws gets joystick messages like "-40,100" (steer, speed) 20 times a second
static esp_err_t ws_handler(httpd_req_t *req) {
    // The first call is the phone opening the connection
    if (req->method == HTTP_GET) {
        ESP_LOGI(TAG, "joystick connected");
        return ESP_OK;
    }

    char buf[16];
    httpd_ws_frame_t frame = {
        .type = HTTPD_WS_TYPE_TEXT,
        .payload = (uint8_t *)buf,
    };

    // Leave one byte for the '\0'
    esp_err_t err = httpd_ws_recv_frame(req, &frame, sizeof(buf) - 1);
    if (err != ESP_OK) {
        return err;
    }
    buf[frame.len] = '\0';

    int x, y;
    if (sscanf(buf, "%d,%d", &x, &y) == 2) {
        drive_steer(x);
        drive_speed(y);
    }
    return ESP_OK;
}

static const httpd_uri_t ws = {
    .uri = "/ws",
    .method = HTTP_GET,
    .handler = ws_handler,
    .is_websocket = true,
};

// GET /battery sends "87,7920" (percent, mV)
static esp_err_t battery_handler(httpd_req_t *req) {
    char buf[16];
    snprintf(buf, sizeof(buf), "%d,%d", battery_percent(), battery_mv());
    httpd_resp_set_type(req, "text/plain");
    httpd_resp_send(req, buf, HTTPD_RESP_USE_STRLEN);
    return ESP_OK;
}

static const httpd_uri_t battery = {
    .uri = "/battery",
    .method = HTTP_GET,
    .handler = battery_handler,
};

void web_start(void) {
    httpd_handle_t server = NULL;
    httpd_config_t conf = HTTPD_DEFAULT_CONFIG();

    if (httpd_start(&server, &conf) != ESP_OK) {
        ESP_LOGE(TAG, "server failed to start");
        return;
    }

    httpd_register_uri_handler(server, &root);
    httpd_register_uri_handler(server, &ws);
    httpd_register_uri_handler(server, &battery);
    ESP_LOGI(TAG, "server running at http://192.168.4.1");
}
