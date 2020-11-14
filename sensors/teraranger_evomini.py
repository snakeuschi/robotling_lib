# ----------------------------------------------------------------------------
# teraranger_evomini.py
# Class for TeraRanger Evo Mini 4-pixel distance sensor
#
# The MIT License (MIT)
# Copyright (c) 2020 Thomas Euler
# 2020-08-08, v1
#
# ----------------------------------------------------------------------------
import array
from micropython import const
import robotling_lib.misc.ansi_color as ansi
from robotling_lib.misc.helpers import timed_function

try:
  import struct
except ImportError:
  import ustruct as struct

from robotling_lib.platform.platform import platform
if platform.languageID == platform.LNG_MICROPYTHON:
  from robotling_lib.platform.esp32.busio import UART
  from time import sleep_ms
  import select
elif platform.languageID == platform.LNG_CIRCUITPYTHON:
  from robotling_lib.platform.circuitpython.busio import UART
  from robotling_lib.platform.circuitpython.time import sleep_ms
else:
  print("ERROR: No matching hardware libraries in `platform`.")

__version__ = "0.1.0.0"
CHIP_NAME   = "tera_evomini"
CHAN_COUNT  = const(4)

# pylint: disable=bad-whitespace
# User facing constants/module globals.
TERA_DIST_NEG_INF   = const(0x0000)
TERA_DIST_POS_INF   = const(0xFFFF)
TERA_DIST_INVALID   = const(0x0001)
TERA_POLL_WAIT_MS   = const(10)

# Internal constants and register values:
_TERA_BAUD          = 115200
_TERA_CMD_WAIT_MS   = const(10)
_TERA_START_CHR     = const(0x54)
_TERA_OUT_MODE_TEXT = bytearray([0x00, 0x11, 0x01, 0x45])
_TERA_OUT_MODE_BIN  = bytearray([0x00, 0x11, 0x02, 0x4C])
_TERA_PIX_MODE_1    = bytearray([0x00, 0x21, 0x01, 0xBC])
_TERA_PIX_MODE_2    = bytearray([0x00, 0x21, 0x03, 0xB2])
_TERA_PIX_MODE_4    = bytearray([0x00, 0x21, 0x02, 0xB5])
_TERA_RANGE_SHORT   = bytearray([0x00, 0x61, 0x01, 0xE7])
_TERA_RANGE_LONG    = bytearray([0x00, 0x61, 0x03, 0xE9])
# pylint: enable=bad-whitespace

# ----------------------------------------------------------------------------
class TeraRangerEvoMini:
  """Driver for the TeraRanger Evo Mini 4-pixel distance sensor."""

  def __init__(self, id, tx, rx, nPix=4, short=True):
    """ Requires pins and channel for unused UART
    """
    self._uart = UART(id, baudrate=_TERA_BAUD, tx=tx, rx=rx)
    self._nPix = nPix
    self._short = short

    # Set pixel mode and prepare buffer
    if self._nPix == 4:
      self._uart.write(_TERA_PIX_MODE_4)
    elif self._nPix == 2:
      self._uart.write(_TERA_PIX_MODE_2)
    else:
      self._nPix = 1
      self._uart.write(_TERA_PIX_MODE_1)
    sleep_ms(_TERA_CMD_WAIT_MS)
    self._nBufExp = self._nPix*2 +2
    self._dist = array.array("i", [0]*self._nPix)
    self._inval = array.array("i", [0]*self._nPix)

    # Set binary mode for results
    self._uart.write(_TERA_OUT_MODE_BIN)
    sleep_ms(_TERA_CMD_WAIT_MS)

    # Set distance mode
    if self._short:
      self._uart.write(_TERA_RANGE_SHORT)
    else:
      self._uart.write(_TERA_RANGE_LONG)
    sleep_ms(_TERA_CMD_WAIT_MS)

    # Prepare polling construct, if available
    self._poll = None
    if platform.ID == platform.ENV_ESP32_UPY:
      self._poll = select.poll()
      self._poll.register(self._uart, select.POLLIN)

    self._isReady = True
    c = ansi.GREEN if self._isReady else ansi.RED
    print(c +"[{0:>12}] {1:35} ({2}): {3}"
          .format(CHIP_NAME, "TeraRanger Evo Mini", __version__,
                  "ok" if self._isReady else "NOT FOUND") +ansi.BLACK)

  def __deinit__(self):
    if self._uart is not None:
      self._uart.deinit()
      self._isReady == False

  # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
  def update(self, raw=True):
    """ Update distance reading(s)
    """
    if self._uart is not None:
      # UART seems to be ready ...
      np = self._nPix
      if self._poll is not None:
        if len(self._poll.poll(TERA_POLL_WAIT_MS)) == 0:
          return
      elif self._uart.any() < self._nBufExp:
        return
      buf = self._uart.readline()
      if buf and len(buf) == self._nBufExp and buf[0] == _TERA_START_CHR:
        # Is valid buffer
        if np == 4:
          d = struct.unpack_from('>HHHH', buf[1:9])
        elif np == 2:
          d = struct.unpack_from('>HH', buf[1:5])
        else:
          d = struct.unpack_from('>H', buf[1:3])
        if raw:
          # Just copy new values to `dist`
          self._dist = d
        else:
          # Check if values are valid and keep track of last valid reading
          for iv,v in enumerate(d):
            if v == TERA_DIST_INVALID:
              self._inval[iv] += 1
            else:
              self._dist[iv] = v
              self._inval[iv] = 0

  @property
  def distance(self):
    return self._dist

  @property
  def invalids(self):
    return self._inval

# ----------------------------------------------------------------------------
