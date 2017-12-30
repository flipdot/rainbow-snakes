#!/usr/bin/env python3
# Sends rainbows via UDP to snake

import colorsys
import math
import random
import socket
import time

MAX_BRIGHTNESS = 250
MIN_FORCE = .001
MAX_FORCE = .003
MAX_PUSH = .000001
FRAME_SLEEP = .01
FLICKER_SPEED = .18
LED_COUNT = 300
LED_HOST = "esp-sofas.fd"
LED_PORT = 7777
LED_SERVER = (LED_HOST, LED_PORT)
COLOR_CHANNELS = 3

USERS = []
for i in range(5):
    USERS.append(int(random.random() * 360))


def sign(x):
    return (1, -1)[x < 0]


def kinetic_init(hues=USERS, positions=[], forces=[]):
    if len(positions) == 0:
        positions = [random.random() for p in hues]
    if len(forces) == 0:
        forces = [random.random() for f in hues]
    if len(hues) != len(positions) or len(hues) != len(forces):
        raise Exception(
            'Length mismatch of hues ({}), positions ({}) or forces ({}).'
            .format(len(hues), len(positions), len(forces))
        )
    kinetic_pixels = []
    for h, p, f in zip(hues, positions, forces):
        pixel = {}
        # Color
        pixel['c'] = colorsys.hsv_to_rgb(h / 360, 1, 1)
        # Position
        pixel['p'] = random.random()
        # Force
        pixel['f'] = (random.random() - .5) * 2
        # Sine flicker
        pixel['s'] = False
        kinetic_pixels.append(pixel)
    return kinetic_pixels


def kinetic_step(kinetic_pixels):
    for pixel in kinetic_pixels:

        # Regular movement of pixel's individual force
        f = sign(pixel['f']) *\
            (abs(pixel['f']) * (MAX_FORCE - MIN_FORCE) + MIN_FORCE)
        pixel['p'] = pixel['p'] + f

        # Gravitational pushes / Forces between pixels
        # M = [pixel['p'] - p['p'] for p in kinetic_pixels]
        # for m in M:
        #     t = 1 - (m ** MAX_PUSH)
        #     pixel['p'] = pixel['p'] + t.real + t.imag
        #     print(m, pixel['p'])
        # print()
        # print(M, (M ** MAX_PUSH).real)

        # Bound checks
        if pixel['p'] < 0:
            pixel['p'] = pixel['p'] * -1
            pixel['f'] = pixel['f'] * -1
        if pixel['p'] > 1:
            pixel['p'] = 2 - pixel['p']
            pixel['f'] = pixel['f'] * -1
    return kinetic_pixels


def kinetic_colors(kinetic_pixels, ts):
    # Initialize black rgb stripe with empty leading pixel
    # as defined by the protocol: https://github.com/cnlohr/esp8266ws2812i2s
    colors = [0, 0, 0] + [0] * LED_COUNT * COLOR_CHANNELS

    for pixel in kinetic_pixels:
        c = pixel['c']
        p = pixel['p'] * LED_COUNT

        r = c[0] * MAX_BRIGHTNESS
        g = c[1] * MAX_BRIGHTNESS
        b = c[2] * MAX_BRIGHTNESS

        # Position in array
        x1 = int(p) * COLOR_CHANNELS
        x2 = x1 + COLOR_CHANNELS

        # Brightness
        y1 = 1 - (p % 1)
        y2 = p % 1

        if pixel['s']:
            s = (math.sin(ts * FLICKER_SPEED) + 1) / 2
            r *= s
            g *= s
            b *= s

        # Set color channels
        colors[x1 + 0] = int(r * y1)
        colors[x1 + 1] = int(g * y1)
        colors[x1 + 2] = int(b * y1)

        if x2 >= len(colors):
            continue

        colors[x2 + 0] = int(r * y2)
        colors[x2 + 1] = int(g * y2)
        colors[x2 + 2] = int(b * y2)
    return colors


if __name__ == '__main__':
    ts = 0
    kinetic_pixels = kinetic_init()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    while True:
        kinetic_pixels = kinetic_step(kinetic_pixels)
        colors = kinetic_colors(kinetic_pixels, ts)
        sock.sendto(bytes(colors), LED_SERVER)

        time.sleep(FRAME_SLEEP)
        ts += 1
