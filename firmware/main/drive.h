#pragma once

// Sets up the steering servo. Call once before web_start.
void drive_start(void);

// x from the joystick, -100 (full left) to 100 (full right)
void drive_steer(int x);