#!/usr/bin/env python3
# Sends rainbows via UDP to snake

import colorsys
import math
import random
import socket
import time
import yaml

import paho.mqtt.client as mqtt

MAX_BRIGHTNESS = 250
FRAME_SLEEP = .01
FLICKER_SPEED = .18
LED_COUNT = 300
LED_HOST = "esp-sofas.fd"
LED_PORT = 7777
LED_SERVER = (LED_HOST, LED_PORT)
COLOR_CHANNELS = 3

DEBUG = False

MQTT_HOST = "mqtt.fd"
MQTT_TOPIC = "sensors/all/users"

PIXEL_MASS = 1
FORCE_FACTOR = 0.05
TIMESTEP_LEN = 0.001
ENERGY_PER_PARTICLE = 1.0
POT_ENERGY_FACTOR = 0.01# lower for more than 20 particles

ANIMATIONS = []
FOO = 0
for i in range(FOO):
    anim = {}
    anim['p'] = 1.0*i/FOO
    anim['i'] = i
    def test_anim(colors,t,params):
        colors[int((t*3+anim['i'] + 3*LED_COUNT*params['p']) % (3*LED_COUNT))] = 127
    anim['f'] = test_anim
    ANIMATIONS.append(anim)

USERS = []
for i in range(5):
    USERS.append(int(random.random() * 360))

kinetic_pixels = []


def sign(x):
    return (1, -1)[x < 0]


def on_connect(client, userdata, flags, result):
    client.subscribe(MQTT_TOPIC)


def on_message(client, userdata, message):
    # Compare list of hues with list of 'kinetic pixels'
    # which is actually a list of dicts
    global kinetic_pixels

    msg_content = yaml.load(message.payload)
    msg_hues = msg_content['known']['hues']
    msg_colors = [h_to_rgb(h) for h in msg_hues]

    # Count colors in mqtt message
    msg_hue_counts = {}
    for c in msg_colors:
        h = rgb_to_h(c)
        if h in msg_hue_counts:
            msg_hue_counts[h] += 1
        else:
            msg_hue_counts[h] = 1

    dict_hue_counts = {}
    for pixel in kinetic_pixels:
        h = rgb_to_h(pixel['c'])
        if h in dict_hue_counts:
            dict_hue_counts[h] += 1
        else:
            dict_hue_counts[h] = 1

    diff_hues = {}
    for k, v2 in msg_hue_counts.items():
        try:
            v1 = dict_hue_counts[k]
        except:
            v1 = 0
        diff_hues[k] = v2

    for k, v in dict_hue_counts.items():
        if not k in diff_hues:
            diff_hues[k] = 0

    # Use counted hues to take over already present pixels
    new_pixels = []
    for pixel in kinetic_pixels:
        h = rgb_to_h(pixel['c'])
        d = diff_hues[h]
        if d <= 0:
            continue
        # Disable sine flicker, because pixel is old
        pixel['s'] = False
        new_pixels.append(pixel)
        diff_hues[h] -= 1

    # Create new pixels for colors not yet found
    for k, v in diff_hues.items():
        if v <= 0:
            continue
        for i in range(v):
            pixel = {}
            # Color
            pixel['c'] = h_to_rgb(k)
            # Position
            pixel['p'] = random.random()
            # Initial Velocity
            pixel['v'] = (random.random() - .5) * 2
            # Enable sine flicker, because pixel is new
            pixel['s'] = True
            new_pixels.append(pixel)

    kinetic_pixels = new_pixels
    if (DEBUG):
        print()
        for pixel in kinetic_pixels:
            print("{:3} {}".format(
                rgb_to_h(pixel['c']),
                "NEW" if pixel['s'] else ""))


def rgb_to_h(rgb):
    # TODO Fix rounding errors
    return math.ceil(colorsys.rgb_to_hsv(rgb[0], rgb[1], rgb[2])[0] * 360)


def h_to_rgb(h):
    # TODO Fix rounding errors
    return colorsys.hsv_to_rgb(int(h) / 360, 1, 1)


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
        pixel['c'] = h_to_rgb(h)
        # Position
        pixel['p'] = random.random()
        # Initial Velocity
        pixel['v'] = (random.random() - .5) * 2
        # Sine flicker
        pixel['s'] = False
        kinetic_pixels.append(pixel)
    return kinetic_pixels


def kinetic_step(kinetic_pixels):
    if len(kinetic_pixels) == 0:
        return kinetic_pixels

    for pixel in kinetic_pixels:
        # Electrostatic pushes / Forces between pixels
        # Calculate new velocities
        rs = [pixel['p'] - p['p'] for p in kinetic_pixels]
        force = 0.0
        for r in rs:
            if abs(r) > 0.001:
                # Electrostatic force: f(r)~1/r^2
                # Could be replaced by any other force law
                force += FORCE_FACTOR / (r*r) * sign(r)
        acc = force / PIXEL_MASS
        pixel['v'] = pixel['v'] + acc * TIMESTEP_LEN

    for pixel in kinetic_pixels:
        # Movement of pixels
        pixel['p'] = pixel['p'] + pixel['v'] * TIMESTEP_LEN

    energy = 0.0
    for pixel in kinetic_pixels:
        # Kinetic energy
        energy += pixel['v'] * pixel['v'] * PIXEL_MASS
        # Potential energy
        for p2 in kinetic_pixels:
            r_ij = float(pixel['p'] - p2['p'])
            # print("r_ij=", r_ij)
            if abs(r_ij) > 0.001:
                energy += abs(POT_ENERGY_FACTOR / r_ij)
    # print("energy: ", energy)
    normalization = 0.8*(ENERGY_PER_PARTICLE * len(kinetic_pixels)) / energy + 0.2

    for pixel in kinetic_pixels:
        pixel['v'] = pixel['v'] * normalization

    for pixel in kinetic_pixels:
        # Bound checks
        if pixel['p'] < 0:
            pixel['p'] = pixel['p'] * -1
            pixel['v'] = pixel['v'] * -1
        if pixel['p'] > 1:
            pixel['p'] = 2 - pixel['p']
            pixel['v'] = pixel['v'] * -1
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
    current_colors = [0, 0, 0] + [0] * LED_COUNT * COLOR_CHANNELS

    # Initialize MQTT client
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.loop_start()

    client.connect(MQTT_HOST)

    while True:
        kinetic_pixels = kinetic_step(kinetic_pixels)
        new_colors = kinetic_colors(kinetic_pixels, ts)
        for anim in ANIMATIONS:
            anim['f'](new_colors, ts - anim.get('starttime', 0), anim)
        ANIMATIONS = list(filter(lambda a: not a.get('finished', False), ANIMATIONS))
        for idx, color in enumerate(new_colors):
            current_colors[idx] = int(0.9 * float(current_colors[idx]) + 0.1 * float(color))
        try:
            sock.sendto(bytes(current_colors), LED_SERVER)
        except socket.gaierror:
            pass
        client.user_data_set({})

        time.sleep(FRAME_SLEEP)
        ts += 1
