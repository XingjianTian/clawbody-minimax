#!/usr/bin/env python3
"""Test Xbox controller axis mapping.

Run this to see which axis/button your controller uses.
"""

import os
import time
import pygame

os.environ["SDL_VIDEODRIVER"] = "dummy"

pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() < 1:
    print("No joystick found!")
    exit(1)

joy = pygame.joystick.Joystick(0)
joy.init()

print(f"Controller: {joy.get_name()}")
print(f"Axes: {joy.get_numaxes()}")
print(f"Buttons: {joy.get_numbuttons()}")
print(f"Hats: {joy.get_numhats()}")
print()
print("Move sticks and press buttons to see mappings:")
print("Press CTRL+C to quit")
print()

try:
    while True:
        pygame.event.pump()
        
        axes = [joy.get_axis(i) for i in range(joy.get_numaxes())]
        buttons = [joy.get_button(i) for i in range(joy.get_numbuttons())]
        
        axis_str = " | ".join([f"A{i}:{v:+.2f}" for i, v in enumerate(axes) if abs(v) > 0.1])
        btn_str = " | ".join([f"B{i}" for i, v in enumerate(buttons) if v])
        
        if axis_str or btn_str:
            print(f"\r{axis_str}  {btn_str}", end=" " * 20)
        
        time.sleep(0.05)
except KeyboardInterrupt:
    print("\nDone")
    pygame.quit()
