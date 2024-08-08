#!/usr/bin/env python3

import os
from time import sleep, time, strftime, localtime
import readchar
from os import geteuid, getlogin, path, environ
from google_speech import Speech

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

def smooth_turn(direction, angle_step=5, max_angle=30, delay=0.05):
    current_angle = px.get_dir_servo_angle()
    if direction == "left":
        target_angle = -max_angle
    elif direction == "right":
        target_angle = max_angle
    else:
        return  # No valid direction provided

    while current_angle != target_angle:
        if direction == "left":
            current_angle = max(current_angle - angle_step, target_angle)
        else:
            current_angle = min(current_angle + angle_step, target_angle)
        px.set_dir_servo_angle(current_angle)
        sleep(delay)

def move_forward_backward(operation, speed):
    if operation == "stop":
        px.stop()
    elif operation == "forward":
        px.forward(speed)
    elif operation == "backward":
        px.backward(speed)

def handle_steering(key):
    if key == "a":
        smooth_turn("left")
    elif key == "d":
        smooth_turn("right")
    else:
        px.set_dir_servo_angle(0)  # Center the steering

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
    status = "stop"
    flag_bgm = False
    cam_tilt_angle = 0  # Initialize the camera tilt angle
    cam_pan_angle = 0  # Initialize the camera pan angle
    music.music_set_volume(100)

    Vilib.camera_start(vflip=False, hflip=False)
    Vilib.display(local=True, web=True)
    sleep(2)  # wait for startup
    print(manual)

    # Get paths from environment variables
    music_path = environ.get('MUSIC_PATH', "../musics/robomusic.mp3")
    sound_path = environ.get('SOUND_PATH', "../sounds/directives.wav")
    while True:
        print("\rstatus: %s , speed: %s    " % (status, speed), end="", flush=True)
        # readkey
        key = readchar.readkey()

        if key in (
            "w",
            "a",
            "s",
            "d",
            "-",
            "=",
            " ",
            readchar.key.UP,
            readchar.key.DOWN,
            readchar.key.LEFT,
            readchar.key.RIGHT,
        ):
            # throttle
            if key == "=":  # speed up
                if speed <= 90:
                    speed += 10
            elif key == "-":  # speed down
                if speed >= 10:
                    speed -= 10
                if speed == 0:
                    status = "stop"
            # direction
            elif key in ("w", "s"):
                if speed == 0:
                    speed = 10
                if key == "w":
                    if status != "forward" and speed > 60:
                        speed = 60
                    status = "forward"
                elif key == "s":
                    if (
                        status != "backward" and speed > 60
                    ):  # Speed limit when reversing
                        speed = 60
                    status = "backward"
            elif key in ("a", "d"):
                handle_steering(key)
            # stop
            elif key == " ":
                status = "stop"
            # camera control
            elif key == readchar.key.UP:
                cam_tilt_angle += 5
                if cam_tilt_angle > 35:
                    cam_tilt_angle = 35
                px.set_cam_tilt_angle(cam_tilt_angle)
            elif key == readchar.key.DOWN:
                cam_tilt_angle -= 5
                if cam_tilt_angle < -35:
                    cam_tilt_angle = -35
                px.set_cam_tilt_angle(cam_tilt_angle)
            elif key == readchar.key.LEFT:
                cam_pan_angle -= 5
                if cam_pan_angle < -35:
                    cam_pan_angle = -35
                px.set_cam_pan_angle(cam_pan_angle)
            elif key == readchar.key.RIGHT:
                cam_pan_angle += 5
                if cam_pan_angle > 35:
                    cam_pan_angle = 35
                px.set_cam_pan_angle(cam_pan_angle)
            # move forward/backward
            move_forward_backward(status, speed)
        # take photo
        elif key == "t":
            take_photo()
        # play music
        elif key == "m":
            flag_bgm = not flag_bgm
            if flag_bgm:
                print("Play Music")
                print(f"Playing music: {music_path}")
                play_music(music_path)
            else:
                print("Stop Music")
                music.music_stop()
        # play sound effect
        elif key == "r":
            print(f"Playing sound: {sound_path}")
            play_sound(sound_path)
            sleep(0.05)
            print("4: Classified")
        # text to speech
        elif key == "k":
            words = "Target identified."
            text_to_speech(f"{words}")
        # quit
        elif key == readchar.key.CTRL_C:
            print("\nquit ...")
            px.stop()
            Vilib.camera_close()
            break

        sleep(0.05)  # Reduced sleep time for better responsiveness

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"error:{e}")
    finally:
        px.stop()
        Vilib.camera_close()