#!/usr/bin/env python3
"""Full Xbox controller mapping for Reachy Mini.

Maps all major DOFs to an Xbox controller:
- Left Stick:     Head Position X / Y
- Right Stick:    Head Pitch / Yaw
- D-Pad Up/Down:  Head Position Z
- D-Pad Left/Right: Body Yaw
- LB / RB:        Head Roll (decrease / increase)
- LT / RT:        Both Antennas together (decrease / increase)
- X / Y:          Left Antenna alone (decrease / increase)
- A / B:          Right Antenna alone (decrease / increase)
- Back / View:    Reset all to neutral
- Start / Menu:   Quit application

Requirements:
- pip install pygame
"""

import os
import sys
import time

import numpy as np
import pygame

from reachy_mini import ReachyMini, utils

# --- Configuration ---
CONTROL_LOOP_RATE = 0.02  # 50 Hz

# Maximum ranges for absolute-mapped axes (stick -> target)
POS_XY_LIMIT = 0.03  # meters (3 cm)
POS_Z_LIMIT = 0.03  # meters (3 cm)
PITCH_LIMIT = np.deg2rad(25)
YAW_LIMIT = np.deg2rad(45)
BODY_YAW_LIMIT = np.deg2rad(60)

# Maximum ranges for incrementally-controlled DOFs
ROLL_LIMIT = np.deg2rad(25)
ANTENNA_LIMIT = np.deg2rad(140)

# Rates of change per control loop tick (50 Hz)
ROLL_RATE = np.deg2rad(60) * CONTROL_LOOP_RATE      # 60 deg/s
ANTENNA_RATE = np.deg2rad(120) * CONTROL_LOOP_RATE  # 120 deg/s
POS_Z_RATE = 0.02 * CONTROL_LOOP_RATE               # 2 cm/s
BODY_YAW_RATE = np.deg2rad(60) * CONTROL_LOOP_RATE  # 60 deg/s

# Deadzones
STICK_DEADZONE = 0.08
TRIGGER_DEADZONE = 0.1

# To use pygame "headlessly" (without a GUI window).
os.environ["SDL_VIDEODRIVER"] = "dummy"

# --- Button / Axis Indices (Xbox controller via pygame) ---
# Buttons
BTN_A = 0
BTN_B = 1
BTN_X = 2
BTN_Y = 3
BTN_LB = 4
BTN_RB = 5
BTN_BACK = 6
BTN_START = 7

# Axes (typical macOS / SDL Xbox mapping)
AXIS_LSX = 0   # Left stick X
AXIS_LSY = 1   # Left stick Y
AXIS_LT = 2    # Left trigger (0..1)
AXIS_RSX = 3   # Right stick X
AXIS_RSY = 4   # Right stick Y
AXIS_RT = 5    # Right trigger (0..1)

# Hats
HAT_DPAD = 0


class XboxController:
    """Handle Xbox controller input using pygame."""

    def __init__(self, deadzone: float = STICK_DEADZONE):
        pygame.init()
        pygame.joystick.init()

        if pygame.joystick.get_count() < 1:
            raise IOError("No joystick controller found.")

        self.joystick = pygame.joystick.Joystick(0)
        self.joystick.init()
        self.deadzone = deadzone
        print(f"Initialized joystick: {self.joystick.get_name()}")
        print(f"  Axes: {self.joystick.get_numaxes()}, Buttons: {self.joystick.get_numbuttons()}, Hats: {self.joystick.get_numhats()}")

    def _apply_deadzone(self, value: float, dz: float = None) -> float:
        dz = dz or self.deadzone
        return value if abs(value) > dz else 0.0

    def poll(self) -> dict:
        """Poll the controller and return a dict of raw/processed inputs."""
        pygame.event.pump()

        # Sticks (with deadzone)
        ls_x = self._apply_deadzone(self.joystick.get_axis(AXIS_LSX))
        ls_y = self._apply_deadzone(self.joystick.get_axis(AXIS_LSY))

        # Right stick axes vary by platform / SDL version
        num_axes = self.joystick.get_numaxes()
        rs_x = 0.0
        rs_y = 0.0
        if num_axes > AXIS_RSX:
            rs_x = self._apply_deadzone(self.joystick.get_axis(AXIS_RSX))
        elif num_axes > AXIS_LT:
            rs_x = self._apply_deadzone(self.joystick.get_axis(AXIS_LT))
        if num_axes > AXIS_RSY:
            rs_y = self._apply_deadzone(self.joystick.get_axis(AXIS_RSY))
        elif num_axes > AXIS_RSX:
            rs_y = self._apply_deadzone(self.joystick.get_axis(AXIS_RSX))

        # Triggers (with deadzone)
        lt = 0.0
        rt = 0.0

        if num_axes > AXIS_RT:
            # Separate LT / RT axes (common on macOS/SDL2)
            lt = max(0.0, self.joystick.get_axis(AXIS_LT))
            rt = max(0.0, self.joystick.get_axis(AXIS_RT))
        elif num_axes > AXIS_LT:
            # Shared axis fallback (LT/RT on same axis, e.g. some Linux configs)
            combined = self.joystick.get_axis(AXIS_LT)
            if combined < -TRIGGER_DEADZONE:
                lt = abs(combined)
            elif combined > TRIGGER_DEADZONE:
                rt = combined

        lt = lt if lt > TRIGGER_DEADZONE else 0.0
        rt = rt if rt > TRIGGER_DEADZONE else 0.0

        # Buttons (True while held)
        buttons = {
            "a": self.joystick.get_button(BTN_A),
            "b": self.joystick.get_button(BTN_B),
            "x": self.joystick.get_button(BTN_X),
            "y": self.joystick.get_button(BTN_Y),
            "lb": self.joystick.get_button(BTN_LB),
            "rb": self.joystick.get_button(BTN_RB),
            "back": self.joystick.get_button(BTN_BACK),
            "start": self.joystick.get_button(BTN_START),
        }

        # D-Pad (hat or button fallback for macOS Xbox controllers)
        hat_x, hat_y = 0, 0
        if self.joystick.get_numhats() > 0:
            hat_x, hat_y = self.joystick.get_hat(HAT_DPAD)
        else:
            # macOS Bluetooth Xbox: D-Pad often appears as buttons 11-14
            num_buttons = self.joystick.get_numbuttons()
            if num_buttons > 14:
                if self.joystick.get_button(11):
                    hat_y = 1   # Up
                if self.joystick.get_button(12):
                    hat_y = -1  # Down
                if self.joystick.get_button(13):
                    hat_x = -1  # Left
                if self.joystick.get_button(14):
                    hat_x = 1   # Right
            elif num_buttons > 11:
                # Some configs map them starting at button 11 with fewer buttons total
                for idx, btn in enumerate(range(11, min(num_buttons, 15))):
                    if self.joystick.get_button(btn):
                        if idx == 0:
                            hat_y = 1
                        elif idx == 1:
                            hat_y = -1
                        elif idx == 2:
                            hat_x = -1
                        elif idx == 3:
                            hat_x = 1

        return {
            "ls_x": ls_x,
            "ls_y": ls_y,
            "rs_x": rs_x,
            "rs_y": rs_y,
            "lt": lt,
            "rt": rt,
            **buttons,
            "hat_x": hat_x,
            "hat_y": hat_y,
        }


def clamp(value: float, limit: float) -> float:
    """Clamp value to [-limit, limit]."""
    return max(-limit, min(limit, value))


def main() -> None:
    try:
        controller = XboxController()
    except IOError as e:
        print(f"Error: {e}", file=sys.stderr)
        return

    print("\nConnecting to Reachy Mini...")
    try:
        with ReachyMini(automatic_body_yaw=True) as mini:
            print("Robot connected.\n")

            # --- Target state (persistent across frames) ---
            pos_x = 0.0
            pos_y = 0.0
            pos_z = 0.0
            roll = 0.0
            pitch = 0.0
            yaw = 0.0
            body_yaw = 0.0
            ant_r = 0.0
            ant_l = 0.0

            print("=" * 60)
            print("  Reachy Mini — Full Xbox Controller")
            print("=" * 60)
            print("  Left Stick  : Head Position X/Y")
            print("  Right Stick : Head Pitch/Yaw")
            print("  D-Pad U/D   : Head Position Z")
            print("  D-Pad L/R   : Body Yaw")
            print("  LB / RB     : Roll (- / +)")
            print("  LT / RT     : Both Antennas (- / +)")
            print("  X / Y       : Left Antenna (- / +)")
            print("  A / B       : Right Antenna (- / +)")
            print("  Back        : Reset to neutral")
            print("  Start       : Quit")
            print("=" * 60 + "\n")

            while True:
                inp = controller.poll()

                # Quit
                if inp["start"]:
                    print("\nStart button pressed. Quitting...")
                    break

                # Reset to neutral
                if inp["back"]:
                    pos_x = pos_y = pos_z = 0.0
                    roll = pitch = yaw = 0.0
                    body_yaw = 0.0
                    ant_r = ant_l = 0.0

                # --- Absolute mappings (sticks) ---
                # Left stick -> Position X/Y
                # axis 1 up is -1, so invert for intuitive "up = forward/+x"
                pos_x = -inp["ls_y"] * POS_XY_LIMIT
                pos_y = inp["ls_x"] * POS_XY_LIMIT

                # Right stick -> Pitch / Yaw
                # axis 4 up is -1, invert so "up = look up" (pitch negative in docs)
                pitch = -inp["rs_y"] * PITCH_LIMIT
                yaw = inp["rs_x"] * YAW_LIMIT

                # --- Incremental mappings (buttons, triggers, d-pad) ---
                # Roll (LB / RB)
                if inp["lb"]:
                    roll -= ROLL_RATE
                if inp["rb"]:
                    roll += ROLL_RATE
                roll = clamp(roll, ROLL_LIMIT)

                # Position Z (D-Pad Up / Down)
                if inp["hat_y"] == 1:    # Up
                    pos_z += POS_Z_RATE
                if inp["hat_y"] == -1:   # Down
                    pos_z -= POS_Z_RATE
                pos_z = clamp(pos_z, POS_Z_LIMIT)

                # Body Yaw (D-Pad Left / Right)
                if inp["hat_x"] == -1:   # Left
                    body_yaw += BODY_YAW_RATE
                if inp["hat_x"] == 1:    # Right
                    body_yaw -= BODY_YAW_RATE
                body_yaw = clamp(body_yaw, BODY_YAW_LIMIT)

                # Antennas — both (LT / RT)
                if inp["lt"]:
                    delta = -ANTENNA_RATE * (1.0 if inp["lt"] >= 1.0 else inp["lt"])
                    ant_r += delta
                    ant_l += delta
                if inp["rt"]:
                    delta = ANTENNA_RATE * (1.0 if inp["rt"] >= 1.0 else inp["rt"])
                    ant_r += delta
                    ant_l += delta

                # Antennas — left alone (X / Y)
                if inp["x"]:
                    ant_l -= ANTENNA_RATE
                if inp["y"]:
                    ant_l += ANTENNA_RATE

                # Antennas — right alone (A / B)
                if inp["a"]:
                    ant_r -= ANTENNA_RATE
                if inp["b"]:
                    ant_r += ANTENNA_RATE

                # Clamp antennas
                ant_r = clamp(ant_r, ANTENNA_LIMIT)
                ant_l = clamp(ant_l, ANTENNA_LIMIT)

                # --- Send command ---
                mini.set_target(
                    head=utils.create_head_pose(
                        x=pos_x,
                        y=pos_y,
                        z=pos_z,
                        roll=roll,
                        pitch=pitch,
                        yaw=yaw,
                        degrees=False,
                    ),
                    antennas=[ant_r, ant_l],
                    body_yaw=body_yaw,
                )

                # --- Status line ---
                status = (
                    f"\rPos({pos_x*1000:+.0f},{pos_y*1000:+.0f},{pos_z*1000:+.0f})mm | "
                    f"RPY({np.rad2deg(roll):+.0f},{np.rad2deg(pitch):+.0f},{np.rad2deg(yaw):+.0f})deg | "
                    f"BodyYaw({np.rad2deg(body_yaw):+.0f})deg | "
                    f"Ant[{np.rad2deg(ant_r):+.0f},{np.rad2deg(ant_l):+.0f}]deg"
                )
                print(status, end=" " * 10)
                sys.stdout.flush()

                time.sleep(CONTROL_LOOP_RATE)

    except KeyboardInterrupt:
        print("\nCTRL+C detected. Shutting down...")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
    finally:
        print("\n\nApplication finished. Robot will go to sleep.")
        pygame.quit()


if __name__ == "__main__":
    main()
