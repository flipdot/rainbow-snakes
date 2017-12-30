#!/usr/bin/env python3
# Sends rainbows via UDP to snake

import colorsys
import math
import socket
import time

from random import random

MAX_BRIGHTNESS = 250
FRAME_SLEEP = .01
TIMESTEP_INCREMENT = .01
LED_COUNT = 300
HOST = "esp-sofas.fd"
PORT = 7777
SERVER = (HOST, PORT)
USERS = [0, 48, 48]

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def col_rainbow(ts):
    colors = []
    for c in range(ts, LED_COUNT + ts + 1):
        c %= 360
        tmp = list(colorsys.hsv_to_rgb(c / 360, 1, .1))
        colors.extend([int(x * MAX_BRIGHTNESS) for x in tmp])
    return colors


def col_random():
    colors = []
    for c in range(LED_COUNT + 1):
        tmp = list(colorsys.hsv_to_rgb(random() * 360, 1, .1))
        colors.extend([int(x * MAX_BRIGHTNESS) for x in tmp])
    return colors


def col_pulse(ts):
    print(math.sin(ts))
    colors = [int((math.sin(ts) + 1) * 100), 0, 0] * LED_COUNT
    return colors


if __name__ == '__main__':
    ts = 0
    while True:
        colors = col_rainbow(ts)
        sock.sendto(bytes(colors), SERVER)

        time.sleep(FRAME_SLEEP)
        ts += 1
