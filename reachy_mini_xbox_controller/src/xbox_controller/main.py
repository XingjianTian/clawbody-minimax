"""Xbox Controller App for Reachy Mini.

Complete controller mapping with all inputs mapped independently:
- Head: left stick (yaw/pitch) + LT/RT (roll)
- Body: right stick (yaw)
- Antennas: LB/RB (individual control) + A/B (animations)
- Reset: Back button
- Quit: Start button

Fixes issues in official controller:
- Antennas no longer reset to zero on every input
- Roll control added via LT/RT triggers
- All inputs are independent and additive
"""

import os
import time
import threading
import logging

import numpy as np
from reachy_mini import ReachyMini, utils
from reachy_mini.apps.app import ReachyMiniApp

os.environ["SDL_VIDEODRIVER"] = "dummy"

logger = logging.getLogger("xbox_controller")


class XboxControllerApp(ReachyMiniApp):
    """Xbox controller app."""

    custom_app_url = None
    request_media_backend = "no_media"

    def __init__(self) -> None:
        super().__init__()
        self._running = False

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event) -> None:
        try:
            import pygame
        except ImportError:
            logger.error("pygame not installed. Run: pip install pygame")
            return

        pygame.init()
        pygame.joystick.init()

        if pygame.joystick.get_count() < 1:
            logger.error("No Xbox controller found.")
            return

        joystick = pygame.joystick.Joystick(0)
        joystick.init()
        logger.info(f"Controller: {joystick.get_name()}")

        CONTROL_RATE = 0.02
        DEADZONE = 0.15
        HEAD_YAW_LIMIT = np.deg2rad(45)
        HEAD_PITCH_LIMIT = np.deg2rad(30)
        HEAD_ROLL_LIMIT = np.deg2rad(20)
        BODY_YAW_LIMIT = np.deg2rad(30)
        ANTENNA_SPEED = 0.03

        # Current state (persisted across frames)
        current_antennas = [0.0, 0.0]
        current_roll = 0.0

        logger.info("Controls:")
        logger.info("  Left stick: Head yaw/pitch")
        logger.info("  Right stick: Body yaw")
        logger.info("  LT/RT: Head roll")
        logger.info("  LB/RB: Antennas (hold to move)")
        logger.info("  A/B: Antenna animations")
        logger.info("  Back: Reset all")
        logger.info("  Start: Quit")

        try:
            while not stop_event.is_set() and self._running:
                pygame.event.pump()

                # Left stick - head yaw/pitch
                left_x = self._apply_deadzone(joystick.get_axis(0), DEADZONE)
                left_y = self._apply_deadzone(joystick.get_axis(1), DEADZONE)

                # Right stick - body yaw
                right_x = self._apply_deadzone(
                    joystick.get_axis(3) if joystick.get_numaxes() > 3 else joystick.get_axis(2),
                    DEADZONE
                )

                # LT/RT - head roll (triggers return 0 to -1 or 0 to 1)
                lt = joystick.get_axis(4) if joystick.get_numaxes() > 4 else 0.0
                rt = joystick.get_axis(5) if joystick.get_numaxes() > 5 else 0.0
                # Xbox triggers: LT is positive (rest=0, full=-1 on some), RT is negative
                # Normalize to [-1, 1]
                roll_input = 0.0
                if abs(lt) > 0.1:
                    roll_input -= lt
                if abs(rt) > 0.1:
                    roll_input += rt
                current_roll = np.clip(roll_input * HEAD_ROLL_LIMIT, -HEAD_ROLL_LIMIT, HEAD_ROLL_LIMIT)

                # LB/RB - individual antenna control
                if joystick.get_button(4):  # LB
                    current_antennas[0] = np.clip(current_antennas[0] - ANTENNA_SPEED, -0.8, 0.8)
                if joystick.get_button(5):  # RB
                    current_antennas[1] = np.clip(current_antennas[1] - ANTENNA_SPEED, -0.8, 0.8)

                # A/B - antenna animations
                if joystick.get_button(0):  # A
                    self._antenna_animation(reachy_mini, current_antennas, "happy")
                elif joystick.get_button(1):  # B
                    self._antenna_animation(reachy_mini, current_antennas, "curious")

                # Back - reset all
                if joystick.get_button(6):
                    logger.info("Reset")
                    current_antennas = [0.0, 0.0]
                    current_roll = 0.0

                # Start - quit
                if joystick.get_button(7):
                    logger.info("Quit")
                    break

                # Map to target angles
                head_yaw = left_x * HEAD_YAW_LIMIT
                head_pitch = -left_y * HEAD_PITCH_LIMIT
                body_yaw = right_x * BODY_YAW_LIMIT

                # Send command with explicit antennas (prevents reset)
                try:
                    reachy_mini.set_target(
                        utils.create_head_pose(
                            x=0, y=0, z=0,
                            roll=np.rad2deg(current_roll),
                            pitch=np.rad2deg(head_pitch),
                            yaw=np.rad2deg(head_yaw),
                            degrees=True,
                        ),
                        antennas=tuple(current_antennas),
                        body_yaw=body_yaw,
                    )
                except Exception as e:
                    logger.warning(f"Set target failed: {e}")

                time.sleep(CONTROL_RATE)

        except Exception as e:
            logger.error(f"Controller error: {e}")
        finally:
            logger.info("Controller ended")
            pygame.quit()

    def _apply_deadzone(self, value: float, deadzone: float) -> float:
        if abs(value) < deadzone:
            return 0.0
        sign = 1 if value > 0 else -1
        return sign * (abs(value) - deadzone) / (1 - deadzone)

    def _antenna_animation(self, robot: ReachyMini, antennas: list, style: str) -> None:
        try:
            if style == "happy":
                robot.goto_target(antennas=[0.5, -0.5], duration=0.3)
                time.sleep(0.35)
                robot.goto_target(antennas=[-0.5, 0.5], duration=0.3)
                time.sleep(0.35)
                robot.goto_target(antennas=[0, 0], duration=0.3)
                antennas[0] = 0.0
                antennas[1] = 0.0
            elif style == "curious":
                robot.goto_target(antennas=[0.3, 0.3], duration=0.5)
                time.sleep(0.6)
                robot.goto_target(antennas=[-0.3, -0.3], duration=0.5)
                time.sleep(0.6)
                robot.goto_target(antennas=[0, 0], duration=0.5)
                antennas[0] = 0.0
                antennas[1] = 0.0
        except Exception as e:
            logger.warning(f"Animation failed: {e}")


if __name__ == "__main__":
    app = XboxControllerApp()
    app.wrapped_run()
