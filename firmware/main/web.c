#include "esp_http_server.h"
#include "esp_log.h"
#include "web.h"

static const char *TAG = "web";

static esp_err_t root_get_handler(httpd_req_t *req) {
    httpd_resp_set_type(req, "text/html");
    httpd_resp_send(req, "<h1>Hello from the car</h1>", HTTPD_RESP_USE_STRLEN);
    return ESP_OK;
}

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
    ESP_LOGI(TAG, "server running at http://192.168.4.1");
}
