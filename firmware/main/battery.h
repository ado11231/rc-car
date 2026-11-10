#pragma once

// Sets up the battery reading on G3. Call once in app_main.
void battery_start(void);

// Battery voltage in mV (8400 = full)
int battery_mv(void);

// 0 (empty, 6.6V) to 100 (full, 8.4V)
int battery_percent(void);
