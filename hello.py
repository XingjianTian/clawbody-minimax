from reachy_mini import ReachyMini

# Use media_backend="no_media" to skip WebRTC initialization
# This avoids connection hangs when only controlling motors
with ReachyMini(media_backend="no_media") as mini:
    print("Connected to Reachy Mini! ")
    
    # Wiggle antennas
    print("Wiggling antennas...")
    mini.goto_target(antennas=[0.5, -0.5], duration=0.5)
    mini.goto_target(antennas=[-0.5, 0.5], duration=0.5)
    mini.goto_target(antennas=[0, 0], duration=0.5)

    print("Done!")
