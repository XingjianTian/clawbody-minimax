#!/usr/bin/env python3
"""Joystick diagnostic using both polling and events."""

import os
import time
import pygame

# Keep joystick events flowing even when window is not focused
os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"

pygame.init()
pygame.display.set_caption("Joystick test")
pygame.display.set_mode((320, 160))
pygame.joystick.init()

print("pygame:", pygame.version.ver)
print("SDL:", pygame.get_sdl_version())
print("joystick count:", pygame.joystick.get_count())

if pygame.joystick.get_count() < 1:
    print("No joystick found")
    raise SystemExit(1)

sticks = []
for idx in range(pygame.joystick.get_count()):
    j = pygame.joystick.Joystick(idx)
    sticks.append(j)
    print(f"\nindex: {idx}")
    print(f"name: {j.get_name()}")
    print(f"guid: {j.get_guid()}")
    print(f"axes: {j.get_numaxes()}")
    print(f"buttons: {j.get_numbuttons()}")
    print(f"hats: {j.get_numhats()}")

print("\nMove sticks / press buttons. CTRL+C to quit.\n")

prev_axes = {j.get_instance_id(): [0.0] * j.get_numaxes() for j in sticks}
prev_buttons = {j.get_instance_id(): [0] * j.get_numbuttons() for j in sticks}

try:
    while True:
        pygame.event.pump()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                raise KeyboardInterrupt
            if event.type in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP):
                print("EVENT:", event)
            elif event.type == pygame.JOYAXISMOTION:
                if abs(event.value) > 0.08:
                    print("EVENT:", event)
            elif event.type == pygame.JOYHATMOTION:
                print("EVENT:", event)

        for j in sticks:
            iid = j.get_instance_id()
            for i in range(j.get_numaxes()):
                v = j.get_axis(i)
                if abs(v - prev_axes[iid][i]) > 0.1:
                    print(f"POLL: Axis {iid}/{i} = {v:+.3f}")
                    prev_axes[iid][i] = v
            for i in range(j.get_numbuttons()):
                v = j.get_button(i)
                if v != prev_buttons[iid][i]:
                    print(f"POLL: Button {iid}/{i} = {v}")
                    prev_buttons[iid][i] = v

        time.sleep(0.02)
except KeyboardInterrupt:
    print("\nDone")
    pygame.quit()
