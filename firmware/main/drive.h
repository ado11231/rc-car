#pragma once

// Sets up the servo, motors and auto-stop. Call once before web_start.
void drive_start(void);

// x from the joystick, -100 (full left) to 100 (full right)
void drive_steer(int x);

// y from the joystick, -100 (full back) to 100 (full forward)
void drive_speed(int y);
