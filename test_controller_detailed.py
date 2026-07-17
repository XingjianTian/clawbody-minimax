#!/usr/bin/env python3
"""Detailed Xbox controller diagnostic — prints every button/axis/hat state."""

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
print("\nPress CTRL+C to quit. Press buttons / move sticks to see changes.\n")

prev_axes = [0.0] * joy.get_numaxes()
prev_buttons = [False] * joy.get_numbuttons()
prev_hats = [(0, 0)] * joy.get_numhats()

try:
    while True:
        pygame.event.pump()
        changed = False

        # Axes
        axes = [joy.get_axis(i) for i in range(joy.get_numaxes())]
        for i, v in enumerate(axes):
            if abs(v - prev_axes[i]) > 0.05 or (abs(v) > 0.1 and abs(prev_axes[i]) <= 0.1):
                print(f"  Axis {i}: {v:+.3f}")
                changed = True
        prev_axes = axes[:]

        # Buttons
        buttons = [joy.get_button(i) for i in range(joy.get_numbuttons())]
        for i, v in enumerate(buttons):
            if v != prev_buttons[i]:
                print(f"  Button {i}: {'PRESSED' if v else 'released'}")
                changed = True
        prev_buttons = buttons[:]

        # Hats
        for i in range(joy.get_numhats()):
            h = joy.get_hat(i)
            if h != prev_hats[i]:
                print(f"  Hat {i}: {h}")
                changed = True
            prev_hats[i] = h

        if changed:
            print("-" * 40)

        time.sleep(0.02)
except KeyboardInterrupt:
    print("\nDone")
    pygame.quit()
