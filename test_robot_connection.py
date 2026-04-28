#!/usr/bin/env python3
"""Test Reachy Mini robot connection and basic movements.

Usage:
    conda activate reachy_mini_env
    cd /path/to/clawbody-minimax
    python test_robot_connection.py

Prerequisites:
    - Reachy Mini robot powered on and reachable
    - Or simulator running: reachy-mini-daemon --sim
    - reachy-mini SDK installed in the environment

Tests:
1. Connect to robot
2. Enable motors
3. Move to neutral position
4. Test head movements (left, right, up, down)
5. Test camera capture
6. Test audio playback
"""

import os
import sys
import time
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def test_connection(use_usb=True):
    """Test basic robot connection.
    
    Args:
        use_usb: If True, use default ReachyMini() for USB-connected Lite.
                If False, use host/port from .env for simulator or wireless.
    """
    logger.info("=" * 50)
    logger.info("Test 1: Robot Connection")
    logger.info("=" * 50)

    try:
        from reachy_mini import ReachyMini

        if use_usb:
            logger.info("Connecting via USB (Reachy Mini Lite)...")
            robot = ReachyMini(media_backend="no_media")
        else:
            host = os.getenv("ROBOT_HOST", "reachy-mini.local")
            port = int(os.getenv("ROBOT_PORT", "8000"))
            logger.info("Connecting to %s:%d...", host, port)
            robot = ReachyMini(host=host, port=port, media_backend="no_media")

        status = robot.client.get_status()
        logger.info("Connected! Robot status: %s", status)

        return robot

    except Exception as e:
        logger.error("Connection failed: %s", e)
        if use_usb:
            logger.error("Make sure the robot is powered on and USB is connected")
            logger.error("For wireless/simulator, set use_usb=False")
        else:
            logger.error("Make sure the robot is powered on and reachable")
            logger.error("For simulator, run: reachy-mini-daemon --sim")
        raise


def test_motors(robot):
    """Test motor enable/disable."""
    logger.info("=" * 50)
    logger.info("Test 2: Motors")
    logger.info("=" * 50)

    logger.info("Enabling motors...")
    robot.enable_motors()
    logger.info("Motors enabled")

    time.sleep(1)

    logger.info("Checking joint positions...")
    joints = robot.get_current_joint_positions()
    logger.info("Current joints: %s", joints)


def test_head_movement(robot):
    """Test head movements in different directions."""
    logger.info("=" * 50)
    logger.info("Test 3: Head Movements")
    logger.info("=" * 50)

    from reachy_mini.utils import create_head_pose

    directions = [
        ("neutral", (0, 0, 0, 0, 0, 0)),
        ("left", (0, 0, 0, 0, 0, 30)),
        ("right", (0, 0, 0, 0, 0, -30)),
        ("up", (0, 0, 10, 0, 15, 0)),
        ("down", (0, 0, -5, 0, -15, 0)),
        ("neutral", (0, 0, 0, 0, 0, 0)),
    ]

    for name, (x, y, z, roll, pitch, yaw) in directions:
        logger.info("Moving head %s...", name)
        pose = create_head_pose(x, y, z, roll, pitch, yaw, degrees=True)
        robot.goto_target(
            head=pose,
            antennas=[0.0, 0.0],
            duration=1.5,
            body_yaw=0.0,
        )
        time.sleep(2)

    logger.info("Head movement test complete")


def test_camera(robot):
    """Test camera capture."""
    logger.info("=" * 50)
    logger.info("Test 4: Camera")
    logger.info("=" * 50)

    try:
        logger.info("Starting camera...")
        robot.media.start_recording()
        time.sleep(2)

        frame = robot.media.get_frame()
        if frame is not None:
            logger.info("Frame captured: shape=%s, dtype=%s", frame.shape, frame.dtype)

            # Save frame
            import cv2
            output_path = Path("test_camera_frame.jpg")
            cv2.imwrite(str(output_path), frame)
            logger.info("Frame saved to: %s", output_path)
        else:
            logger.warning("No frame captured")

        robot.media.stop_recording()

    except Exception as e:
        logger.error("Camera test failed: %s", e)


def test_audio(robot):
    """Test audio playback through robot speaker."""
    logger.info("=" * 50)
    logger.info("Test 5: Audio Playback")
    logger.info("=" * 50)

    try:
        import numpy as np

        logger.info("Generating test tone...")
        sample_rate = robot.media.get_output_audio_samplerate()
        duration = 2.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        tone = np.sin(2 * np.pi * 440 * t).astype(np.float32) * 0.3

        logger.info("Playing test tone (440Hz, %.1fs)...", duration)
        robot.media.start_playing()
        robot.media.push_audio_sample(tone)
        time.sleep(duration + 0.5)
        robot.media.stop_playing()

        logger.info("Audio playback complete")

    except Exception as e:
        logger.error("Audio test failed: %s", e)


def test_antennas(robot):
    """Test antenna movements."""
    logger.info("=" * 50)
    logger.info("Test 6: Antennas")
    logger.info("=" * 50)

    from reachy_mini.utils import create_head_pose

    logger.info("Moving antennas...")
    neutral = create_head_pose(0, 0, 0, 0, 0, 0, degrees=True)

    # Wiggle antennas
    for i in range(3):
        robot.goto_target(
            head=neutral,
            antennas=[0.5, -0.5],
            duration=0.5,
            body_yaw=0.0,
        )
        time.sleep(0.7)
        robot.goto_target(
            head=neutral,
            antennas=[-0.5, 0.5],
            duration=0.5,
            body_yaw=0.0,
        )
        time.sleep(0.7)

    robot.goto_target(
        head=neutral,
        antennas=[0.0, 0.0],
        duration=1.0,
        body_yaw=0.0,
    )
    time.sleep(1.5)
    logger.info("Antenna test complete")


def main():
    """Run all robot connection tests."""
    logger.info("Starting Reachy Mini Robot Tests")
    logger.info("")

    robot = None
    try:
        # Test 1: Connection (use USB for Reachy Mini Lite)
        robot = test_connection(use_usb=True)

        # Test 2: Motors
        test_motors(robot)

        # Test 3: Head movements
        test_head_movement(robot)

        # Test 4: Camera
        test_camera(robot)

        # Test 5: Audio
        test_audio(robot)

        # Test 6: Antennas
        test_antennas(robot)

        logger.info("")
        logger.info("=" * 50)
        logger.info("All tests completed successfully!")
        logger.info("=" * 50)

    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error("Test failed: %s", e, exc_info=True)
    finally:
        if robot is not None:
            logger.info("Cleaning up...")
            try:
                robot.goto_target(
                    head=create_head_pose(0, 0, 0, 0, 0, 0, degrees=True),
                    antennas=[0.0, 0.0],
                    duration=2.0,
                    body_yaw=0.0,
                )
                time.sleep(2.5)
                robot.client.disconnect()
                logger.info("Robot disconnected")
            except Exception as e:
                logger.error("Cleanup error: %s", e)


if __name__ == "__main__":
    from reachy_mini.utils import create_head_pose
    main()
