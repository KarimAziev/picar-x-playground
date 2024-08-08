#!/usr/bin/env python3

import os
from time import sleep, time, strftime, localtime
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
    _time = strftime("%Y-%m-%d-%H-%M-%S", localtime(time()))
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
    cam_tilt_angle = 0  # Initialize the camera tilt angle
    cam_pan_angle = 0  # Initialize the camera pan angle
    steering_angle = 0   # Initialize the steering angle
    target_steering_angle = 0
    music.music_set_volume(100)

    Vilib.camera_start(vflip=False, hflip=False)
    Vilib.display(local=True, web=True)
    sleep(2)  # wait for startup
    print(manual)

    # Get paths from environment variables
    music_path = environ.get('MUSIC_PATH', "../musics/robomusic.mp3")
    sound_path = environ.get('SOUND_PATH', "../sounds/directives.wav")

    def control_loop():
        prev_speed = -1
        prev_steering_angle = -1
        nonlocal speed, target_speed, steering_angle, target_steering_angle
        while True:
            speed = smooth_acceleration(speed, target_speed)
            steering_angle = handle_steering(steering_angle, target_steering_angle)

            # Update only if there's a change
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

            sleep(0.05)

    control_thread = threading.Thread(target=control_loop)
    control_thread.daemon = True  # This makes sure the thread exits when the main program does
    control_thread.start()

    while True:
        key = readchar.readkey()
        print("\rstatus: %s , speed: %s    " % (status, speed), end="", flush=True)

        # Throttle and speed adjustments
        if key == "=":  # speed up
            if target_speed <= 90:
                target_speed += 10
        elif key == "-":  # speed down
            if target_speed >= 10:
                target_speed -= 10
            if target_speed == 0:
                status = "stop"

        # Movement and direction
        elif key in ("w", "s"):
            if target_speed == 0:
                target_speed = 10
            if key == "w":
                if status != "forward" and target_speed > 60:
                    target_speed = 60
                status = "forward"
            elif key == "s":
                if status != "backward" and target_speed > 60:  # Speed limit when reversing
                    target_speed = 60
                status = "backward"
        elif key == "a":
            target_steering_angle = -30  # Update steering target
        elif key == "d":
            target_steering_angle = 30  # Update steering target
        elif key == " ":
            status = "stop"
            target_speed = 0  # Decelerate to stop
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
        elif key == readchar.key.CTRL_C:
            print("\nquit ...")
            px.stop()
            Vilib.camera_close()
            break

        # Ensuring it updates state efficiently
        if status == "forward":
            px.forward(target_speed)
        elif status == "backward":
            px.backward(target_speed)
        elif status == "stop":
            px.stop()

        # Center the steering if no key is pressed
        if key not in ("a", "d"):
            target_steering_angle = 0

        sleep(0.05)  # Reduced sleep time for better responsiveness

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"error: {e}")
    finally:
        px.stop()
        Vilib.camera_close()