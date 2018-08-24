# Simple NeoPixel light painter for CPX.  Single image filename and speed are set
# in code, there's no interface for selecting items/speed/triggering etc.

import gc
import time
import board
import touchio
import digitalio
from neopixel_write import neopixel_write

# uncomment one line only here to select bitmap
FILENAME = "bats.bmp" # BMP file to load from flash filesystem
# FILENAME = "digikey.bmp"
# FILENAME = "burger.bmp"
# FILENAME = "afbanner.bmp"
# FILENAME = "blinka.bmp"
# FILENAME = "ghost04.bmp"
# FILENAME = "ghost07.bmp"
# FILENAME = "ghost02.bmp"
# FILENAME = "helix-32x30.bmp"
# FILENAME = "wales2-107x30.bmp"
# FILENAME = "pumpkin.bmp"
# FILENAME = "rainbow.bmp"
# FILENAME = "rainbowRoad.bmp"
# FILENAME = "rainbowZig.bmp"
# FILENAME = "skull.bmp"
# FILENAME = "adabot.bmp"
# FILENAME = "green_stripes.bmp"
# FILENAME = "red_blue.bmp"
# FILENAME = "minerva.bmp"

TOUCH = touchio.TouchIn(board.A5) # Rightmost capacitive touch pad
BRIGHTNESS = 1.0                  # NeoPixel brightness 0.0 (min) to 1.0 (max)
GAMMA = 2.7                       # Adjusts perceived brighthess linearity
NUM_PIXELS = 30                   # NeoPixel strip length (in pixels)
SPEED = 20000  # adjust this to change the playback speed e.g. 50000 is slow
LOOP = False  # set to True for looping
# Switch off onboard NeoPixel...
NEOPIXEL_PIN = digitalio.DigitalInOut(board.NEOPIXEL)
NEOPIXEL_PIN.direction = digitalio.Direction.OUTPUT
neopixel_write(NEOPIXEL_PIN, bytearray(3))
# ...then assign NEOPIXEL_PIN to the external NeoPixel connector:
NEOPIXEL_PIN = digitalio.DigitalInOut(board.A1)
NEOPIXEL_PIN.direction = digitalio.Direction.OUTPUT
neopixel_write(NEOPIXEL_PIN, bytearray(NUM_PIXELS * 3))

# Interpret multi-byte value from file as little-endian value
def read_le(value):
    result = 0
    shift = 0
    for byte in value:
        result += byte << shift
        shift += 8
    return result

class BMPError(Exception):
    pass

def load_bmp(filename):
    try:
        print("Loading", filename)
        with open("/" + filename, "rb") as f:
            print("File opened")
            if f.read(2) != b'BM':  # check signature
                raise BMPError("Not BitMap file")

            f.read(4)  # Read & ignore file size
            f.read(4)  # Read & ignore creator bytes

            bmpImageoffset = read_le(f.read(4))  # Start of image data
            f.read(4)  # Read & ignore header size
            bmpWidth = read_le(f.read(4))
            bmpHeight = read_le(f.read(4))
            # BMPs are traditionally stored bottom-to-top.
            # If bmpHeight is negative, image is in top-down order.
            # This is not BMP canon but has been observed in the wild!
            flip = True
            if bmpHeight < 0:
                bmpHeight = -bmpHeight
                flip = False

            print("WxH: (%d,%d)" % (bmpWidth, bmpHeight))

            if read_le(f.read(2)) != 1:
                raise BMPError("Not single-plane")
            bmpDepth = read_le(f.read(2))  # bits per pixel
            # print("Bit depth: %d" % (bmpDepth))
            if bmpDepth != 24:
                raise BMPError("Not 24-bit")
            if read_le(f.read(2)) != 0:
                raise BMPError("Compressed file")

            print("Image format OK, reading data...")

            rowSize = (bmpWidth * 3 + 3) & ~3  # 32-bit line boundary

            # Constrain rows loaded to pixel strip length
            clippedHeight = bmpHeight
            if clippedHeight > NUM_PIXELS:
                clippedHeight = NUM_PIXELS

            # Allocate per-column pixel buffers, sized for NeoPixel strip:
            columns = [bytearray(NUM_PIXELS * 3) for i in range(bmpWidth)]

            # Image is displayed at END (not start) of NeoPixel strip,
            # this index works incrementally backward in column buffers...
            idx = (NUM_PIXELS - 1) * 3
            for row in range(clippedHeight):  # For each scanline...
                if flip:  # Bitmap is stored bottom-to-top order (normal BMP)
                    pos = bmpImageoffset + (bmpHeight - 1 - row) * rowSize
                else:  # Bitmap is stored top-to-bottom
                    pos = bmpImageoffset + row * rowSize
                f.seek(pos)  # Start of scanline
                for c in columns:  # For each pixel of scanline...
                    # BMP files use BGR color order
                    # blue, green, red = bytearray(f.read(3))
                    blue, green, red = f.read(3)
                    # Rearrange into NeoPixel strip's color order,
                    # while handling brightness & gamma correction:
                    c[idx  ] = int(pow(green / 255, GAMMA) * BRIGHTNESS * 255 + 0.5)
                    c[idx+1] = int(pow(red   / 255, GAMMA) * BRIGHTNESS * 255 + 0.5)
                    c[idx+2] = int(pow(blue  / 255, GAMMA) * BRIGHTNESS * 255 + 0.5)
                idx -= 3  # Advance (back) one pixel

            # Add one more column with no color data loaded.  This is used
            # to turn the strip off at the end of the painting operation.
            if not LOOP:
                columns.append(bytearray(NUM_PIXELS * 3))

            print("Loaded OK!")
            gc.collect()  # Garbage-collect now so playback is smoother
            return columns

    except OSError as e:
        if e.args[0] == 28:
            raise OSError("OS Error 28 0.25")
        else:
            raise OSError("OS Error 0.5")
    except BMPError as e:
        print("Failed to parse BMP: " + e.args[0])


# Load BMP image, return 'columns' array:
columns = load_bmp(FILENAME)

print("Mem free:", gc.mem_free())
# Orig code: 10320 bytes free
# New code: 13216 bytes free

column_delay = SPEED / 65535.0 / 10.0  # 0.0 to 0.1 seconds
while LOOP:
    for c in columns:
        neopixel_write(NEOPIXEL_PIN, c)
        time.sleep(column_delay)  # Column-to-column delay

while True:
    # Wait for touch pad input:
    while not TOUCH.value:
        continue

    column_delay = SPEED / 65535.0 / 10.0  # 0.0 to 0.1 seconds
    # print(column_delay)

    # Play back color data loaded into each column:
    for c in columns:
        neopixel_write(NEOPIXEL_PIN, c)
        time.sleep(column_delay)  # Column-to-column delay
        # Last column is all 0's, no need to explicitly clear strip

    # Wait for touch pad release, just in case:
    while TOUCH.value:
        continue
