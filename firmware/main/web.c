#include "esp_http_server.h"
#include "esp_log.h"
#include "web.h"
#include <stdio.h>

static const char *TAG = "web";

// index.html, baked into flash by CMake (EMBED_TXTFILES)
extern const char index_html[] asm("_binary_index_html_start");

static esp_err_t root_get_handler(httpd_req_t *req) {
    httpd_resp_set_type(req, "text/html");
    httpd_resp_send(req, index_html, HTTPD_RESP_USE_STRLEN);
    return ESP_OK;
}

// Phone joystick page that talks to the car here
static esp_err_t ws_handler(httpd_req_t *req) {
    if (req->method == HTTP_GET) {
        ESP_LOGI(TAG, "joystick connected");
        return ESP_OK;
    }

    // Every call after that is one message from the phone
    char buf[16];
    httpd_ws_frame_t frame = {
        .type = HTTPD_WS_TYPE_TEXT,
        .payload = (uint8_t *)buf,
    };

    // Read the message, leaving one byte for the '\0'
    esp_err_t err = httpd_ws_recv_frame(req, &frame, sizeof(buf) - 1);
    if (err != ESP_OK) {
        return err;
    }
    buf[frame.len] = '\0';

    // Message looks like "-40,100": steering, then speed
    int x, y;
    if (sscanf(buf, "%d,%d", &x, &y) == 2) {
        ESP_LOGI(TAG, "x %d  y %d", x, y);
    }
    return ESP_OK;
}

static const httpd_uri_t ws = {
    .uri = "/ws",
    .method = HTTP_GET,
    .handler = ws_handler,
    .is_websocket = true
};

static const httpd_uri_t root = {
    .uri = "/",
    .method = HTTP_GET,
    .handler = root_get_handler
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
    ESP_LOGI(TAG, "server running at http://192.168.4.1");
}
