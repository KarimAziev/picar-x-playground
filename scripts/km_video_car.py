#!/usr/bin/env python3

import os
from time import sleep, strftime, localtime, time as t
import readchar
from os import geteuid, getlogin, path, environ
from google_speech import Speech
import threading

# Check if the OS is Raspberry Pi by checking nodename
is_os_raspbery = os.uname().nodename == "raspberrypi"

if is_os_raspbery:
    print("OS is raspberrypi")
    from picarx import Picarx
    from vilib import Vilib
    from robot_hat.utils import reset_mcu
    from robot_hat import Music
else:
    from stubs import FakePicarx as Picarx
    from stubs import FakeVilib as Vilib
    from stubs import fake_reset_mcu as reset_mcu
    from stubs import FakeMusic as Music

user = getlogin()
user_home = path.expanduser(f"~{user}")

reset_mcu()
sleep(0.2)  # Allow the MCU to reset

manual = """
╔══════════════════════════════════════════════════════════════════╗
║                       CONTROLS MANUAL                            ║
╠══════════════════════════════════════════════════════════════════╣
║ Press key to call the function (non-case sensitive):             ║
║                                                                  ║
║       ┌──────── MOVE ─────────────────── SPEED ──────────┐       ║
║       │                                                  │       ║
║       │                                                  │       ║
║       │          w                                       │       ║
║       │          |                  =  Speed Up          │       ║
║       │    a  <     >  d            -  Speed Down        │       ║
║       │          |                                       │       ║
║       │          s                                       │       ║
║       │                                                  │       ║
║       │                                                  │       ║
║       │    [Space]  Stop                                 │       ║
║       └──────────────────────────────────────────────────┘       ║
║       ┌────────────────── CAMERA ────────────────────────┐       ║
║       │                                                  │       ║
║       │                  arrow                           │       ║
║       │                    up                            │       ║
║       │           arrow    |     arrow                   │       ║
║       │           left  <     >  right                   │       ║
║       │                    |                             │       ║
║       │                  arrow                           │       ║
║       │                   down                           │       ║
║       │                                                  │       ║
║       └──────────────────────────────────────────────────┘       ║
║                                                                  ║
║        t : Take Photo                                            ║
║                                                                  ║
║       ┌───────────────── Sound Controls ─────────────────┐       ║
║       │    r : Tell directives                           │       ║
║       │    m : Play/Stop Music                           │       ║
║       │    k : Speech                                    │       ║
║       └──────────────────────────────────────────────────┘       ║
║                                                                  ║
║     Ctrl+C : Quit                                                ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
"""

print(manual)

px = Picarx()
music = Music()

def text_to_speech(words):
    try:
        print(f"Playing text-to-speech for: {words}")
        speech = Speech(words, "en")
        speech.play()
    except Exception as e:
        print(f"Error playing text-to-speech audio: {e}")

if geteuid() != 0 and is_os_raspbery:
    print(
        f"\033[0;33m{'The program needs to be run using sudo, otherwise there may be no sound.'}\033[0m"
    )

def take_photo():
    _time = strftime("%Y-%m-%d-%H-%M-%S", localtime(t()))
    name = "photo_%s" % _time
    photo_path = f"{user_home}/Pictures/picar-x/"
    Vilib.take_photo(name, photo_path)
    print("\nphoto save as %s%s.jpg" % (photo_path, name))

def smooth_acceleration(current_speed, target_speed, step=5):
    if current_speed < target_speed:
        return min(current_speed + step, target_speed)
    elif current_speed > target_speed:
        return max(current_speed - step, target_speed)
    return current_speed

def handle_deceleration(current_speed, step=5):
    print(f"handle_deceleration {current_speed}")
    if current_speed > 0:
        return max(0, current_speed - step)
    elif current_speed < 0:
        return min(0, current_speed + step)
    return current_speed

def handle_steering(current_angle, target_angle, step=5):
    if current_angle < target_angle:
        return min(current_angle + step, target_angle)
    elif current_angle > target_angle:
        return max(current_angle - step, target_angle)
    return current_angle

def play_music(track_path: str):
    if not path.exists(track_path):
        text = f'The music file {track_path} is missing.'
        speech = Speech(text, "en")
        speech.play()
    else:
        music.music_play(track_path)

def play_sound(sound_path: str):
    if not path.exists(sound_path):
        text = f'The sound file {sound_path} is missing.'
        speech = Speech(text, "en")
        speech.play()
    else:
        music.sound_play(sound_path)

def main():
    speed = 0
    target_speed = 0
    status = "stop"
    flag_bgm = False
    cam_tilt_angle = 0
    cam_pan_angle = 0
    steering_angle = 0
    target_steering_angle = 0
    moving = False
    music.music_set_volume(100)

    Vilib.camera_start(vflip=False, hflip=False)
    Vilib.display(local=True, web=True)
    sleep(2)  # wait for startup
    print(manual)

    # Get paths from environment variables
    music_path = environ.get('MUSIC_PATH', "../musics/robomusic.mp3")
    sound_path = environ.get('SOUND_PATH', "../sounds/directives.wav")

    deceleration_timer = None

    def start_deceleration_timer():
        nonlocal deceleration_timer

        # Function to initiate deceleration
        def decelerate():
            nonlocal target_speed, moving
            target_speed = 0
            moving = False
            print("[TIMER] Timer expired, starting deceleration.")

        # Cancel any existing timer
        if deceleration_timer:
            deceleration_timer.cancel()

        # Start a new timer
        deceleration_timer = threading.Timer(0.5, decelerate)  # 0.5 seconds
        deceleration_timer.start()
        print("[TIMER] Timer started/reset")

    def control_loop():
        prev_speed = -1
        prev_steering_angle = -1
        nonlocal speed, target_speed, steering_angle, target_steering_angle, status, moving
        while True:
            print(f"[CONTROL_LOOP] moving: {moving} target_speed: {target_speed}, current_speed: {speed}, status: {status}")
            if moving:
                speed = smooth_acceleration(speed, target_speed)
            else:
                speed = handle_deceleration(speed)

            steering_angle = handle_steering(steering_angle, target_steering_angle)

            if speed != prev_speed or steering_angle != prev_steering_angle:
                if status == "forward":
                    px.forward(speed)
                elif status == "backward":
                    px.backward(speed)
                elif status == "stop":
                    px.stop()

                px.set_dir_servo_angle(steering_angle)

                prev_speed = speed
                prev_steering_angle = steering_angle

            if speed == 0 and not moving:
                status = "stop"

            sleep(0.05)

    control_thread = threading.Thread(target=control_loop)
    control_thread.daemon = True  # Ensures the thread exits with the main program
    control_thread.start()

    while True:
        key = readchar.readkey()
        print(f"[KEY_PRESS] Key: {key}")
        print(f"\rstatus: {status} , speed: {speed}    ", end="", flush=True)

        if key == readchar.key.CTRL_C:
            print("\nquit ...")
            px.stop()
            Vilib.camera_close()
            break

        # Speed adjustments
        elif key == "=":
            if target_speed <= 90:
                target_speed += 10
        elif key == "-":
            if target_speed >= 10:
                target_speed -= 10
            if target_speed == 0:
                status = "stop"

        # Movement and direction
        elif key == "w":
            status = "forward"
            target_speed = 60
            moving = True
            start_deceleration_timer()  # Reset timer on key press
        elif key == "s":
            status = "backward"
            target_speed = 60
            moving = True
            start_deceleration_timer()  # Reset timer on key press
        elif key == "a":
            target_steering_angle = -30
        elif key == "d":
            target_steering_angle = 30
        elif key == " ":
            status = "stop"
            target_speed = 0
        elif key == readchar.key.UP:
            cam_tilt_angle = min(35, cam_tilt_angle + 5)
            px.set_cam_tilt_angle(cam_tilt_angle)
        elif key == readchar.key.DOWN:
            cam_tilt_angle = max(-35, cam_tilt_angle - 5)
            px.set_cam_tilt_angle(cam_tilt_angle)
        elif key == readchar.key.LEFT:
            cam_pan_angle = max(-35, cam_pan_angle - 5)
            px.set_cam_pan_angle(cam_pan_angle)
        elif key == readchar.key.RIGHT:
            cam_pan_angle = min(35, cam_pan_angle + 5)
            px.set_cam_pan_angle(cam_pan_angle)
        elif key == "t":
            take_photo()
        elif key == "m":
            flag_bgm = not flag_bgm
            if flag_bgm:
                print("Play Music")
                play_music(music_path)
            else:
                print("Stop Music")
                music.music_stop()
        elif key == "r":
            print(f"Playing sound: {sound_path}")
            play_sound(sound_path)
            sleep(0.05)
            text_to_speech("Classified")
        elif key == "k":
            text_to_speech("Target identified.")

        # Center the steering if no key is pressed
        if key not in ("a", "d"):
            target_steering_angle = 0

        # Start deceleration timer if no movement key is pressed
        if key not in ("w", "s"):
            start_deceleration_timer()

        print(f"[POST_KEY] target_speed: {target_speed}, status: {status}")

        sleep(0.05)  # Reduced sleep time for better responsiveness

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"error: {e}")
    finally:
        px.stop()
        Vilib.camera_close()