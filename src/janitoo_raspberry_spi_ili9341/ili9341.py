# -*- coding: utf-8 -*-
"""The Raspberry ili9341 thread

See https://github.com/adafruit/Adafruit_Python_CharLCD/blob/master/examples/char_lcd.py

"""

__license__ = """
    This file is part of Janitoo.

    Janitoo is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Janitoo is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with Janitoo. If not, see <http://www.gnu.org/licenses/>.

"""
__author__ = 'Sébastien GALLET aka bibi21000'
__email__ = 'bibi21000@gmail.com'
__copyright__ = "Copyright © 2013-2014-2015-2016 Sébastien GALLET aka bibi21000"

import logging
logger = logging.getLogger(__name__)
import os, sys
import threading
import datetime

import cStringIO
import PIL.Image as Image
import base64

from janitoo.thread import JNTBusThread, BaseThread
from janitoo.options import get_option_autostart
from janitoo.utils import HADD
from janitoo.node import JNTNode
from janitoo.value import JNTValue
from janitoo.component import JNTComponent

try:
    import Adafruit_ILI9341 as TFT
    import Adafruit_GPIO as GPIO
    import Adafruit_GPIO.SPI as SPI
except:
    logger.exception("Can't import Adafruit_ILI9341")

##############################################################
#Check that we are in sync with the official command classes
#Must be implemented for non-regression
from janitoo.classes import COMMAND_DESC

COMMAND_SCREEN_DRAW = 0x3200
COMMAND_SCREEN_MESSAGE = 0x3201
COMMAND_SCREEN_CLEAR = 0x3202
COMMAND_BLINK = 0x3203

assert(COMMAND_DESC[COMMAND_SCREEN_DRAW] == 'COMMAND_SCREEN_DRAW')
assert(COMMAND_DESC[COMMAND_SCREEN_MESSAGE] == 'COMMAND_SCREEN_MESSAGE')
assert(COMMAND_DESC[COMMAND_SCREEN_CLEAR] == 'COMMAND_SCREEN_CLEAR')
assert(COMMAND_DESC[COMMAND_BLINK] == 'COMMAND_BLINK')
##############################################################

def make_screen(**kwargs):
    return ScreenComponent(**kwargs)

class ScreenComponent(JNTComponent):
    """ A Screen component for spi """

    def __init__(self, bus=None, addr=None, **kwargs):
        """
        """
        oid = kwargs.pop('oid', 'rpispi.ili9341')
        name = kwargs.pop('name', "Screen")
        product_name = kwargs.pop('product_name', "Screen")
        product_type = kwargs.pop('product_type', "Screen")
        product_manufacturer = kwargs.pop('product_manufacturer', "Janitoo")
        JNTComponent.__init__(self, oid=oid, bus=bus, addr=addr, name=name,
                product_name=product_name, product_type=product_type, product_manufacturer=product_manufacturer, **kwargs)
        logger.debug("[%s] - __init__ node uuid:%s", self.__class__.__name__, self.uuid)
        uuid="device"
        self.values[uuid] = self.value_factory['config_byte'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='Either the device number on the hardware bus or the SPI CS pin of the software one',
            label='device',
            default=0,
        )
        uuid="reset_pin"
        self.values[uuid] = self.value_factory['config_byte'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The reset pin',
            label='reset',
            default=None,
        )
        uuid="message"
        self.values[uuid] = self.value_factory['action_string'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='A message to print on the screen',
            label='Msg',
            default='Janitoo started',
            set_data_cb=self.set_message,
            is_writeonly = True,
            cmd_class=COMMAND_SCREEN_MESSAGE,
            genre=0x01,
        )
        uuid="draw"
        self.values[uuid] = self.value_factory['action_string'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='Draw an image on the screen. The image must be base64 encoded.',
            label='Draw',
            default=None,
            set_data_cb=self.set_draw,
            is_writeonly = True,
            cmd_class=COMMAND_SCREEN_DRAW,
            genre=0x01,
        )
        uuid="clear"
        self.values[uuid] = self.value_factory['action_string'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='Clear the screen with the color give parameter',
            label='Clear',
            default='0,0,0',
            set_data_cb=self.set_clear,
            is_writeonly = True,
            cmd_class=COMMAND_SCREEN_CLEAR,
            genre=0x01,
        )
        uuid="reset"
        self.values[uuid] = self.value_factory['action_string'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='Reset the screen',
            label='Reset',
            default=None,
            set_data_cb=self.set_reset,
            is_writeonly = True,
            cmd_class=COMMAND_SCREEN_CLEAR,
            genre=0x01,
        )
        poll_value = self.values[uuid].create_poll_value(default=300)
        self.tft = None
        self.tft_lock = threading.Lock()
        self.tft_lock_last = None
        self.tft_timer = None

    def tft_acquire(self, blocking=True):
        """Get a lock on the bus"""
        if self.tft_lock.acquire(blocking):
            self.tft_lock_last = None
            return True
        return False

    def tfr_release(self):
        """Release a lock on the bus"""
        self.tft_lock.release()


    def start(self, mqttc):
        """Start the bus
        """
        res = JNTComponent.start(self, mqttc)
        self._bus.spi_acquire()
        try:

            device = self.values["device"].data
            reset = self.values["reset_pin"].data
            dc_pin = self._bus.get_spi_device_pin(device)
            spi = self._bus.get_spi_device(device, max_speed_hz=64000000)
            self.setup_ili9341(dc_pin, rst, spi, self._ada_gpio)
        except:
            res = False
            logger.exception("[%s] - Can't start component", self.__class__.__name__)
        finally:
            self._bus.spi_release()
        return res

    def setup_ili9341(self, dc_pin, rst, spi, gpio):
        """
        """
        logger.debug("[%s] - Init the TFT", self.__class__.__name__)
        self.tft = TFT.ILI9341(dc_pin, rst, spi, gpio)
        logger.debug("[%s] - Begin the TFT", self.__class__.__name__)
        self.tft.begin()
        logger.debug("[%s] - Clear the TFT", self.__class__.__name__)
        self.tft.clear()

    def stop(self):
        """
        """
        res = JNTComponent.stop(self)
        if self._bus.spi_locked():
            logger.warning('[%s] - Bus is locked. Close device anyway.', self.__class__.__name__)
            if self.tft is not None:
                self.tft.close()
        self._bus.spi_acquire()
        try:
            self.tft.close()
        except:
            logger.exception('[%s] - Exception when clearing', self.__class__.__name__)
        try:
            self.tft = None
        except:
            logger.exception('[%s] - Exception when stopping', self.__class__.__name__)
        finally:
            self._bus.spi_release()
        return res

    def set_message(self, node_uuid, index, data):
        """Display a message on the screen
        """
        if self._bus.spi_acquire( blocking = False ) == True:
            try:
                self.tft.clear()
                self.values['message'].data = data
            except:
                logger.exception('[%s] - Exception when displaying message', self.__class__.__name__)
            finally:
                self._bus.spi_release()
        else:
            logger.warning("[%s] - Can't get lock when displaying message", self.__class__.__name__)

    def set_draw(self, node_uuid, index, data):
        """Draw the image on the screen
        """
        img = None
        try:
            imgsio = cStringIO.StringIO(base64.base64_decode(data))
            img = PIL.Image.open(imgsio)
        except:
            logger.exception('[%s] - Exception when reading image', self.__class__.__name__)
        if img is not None:
            if self._bus.spi_acquire( blocking = False ) == True:
                try:
                    imgsio = cStringIO.StringIO(base64.base64_decode(data))
                    img = PIL.Image.open(imgsio)
                    self.tft.display(img)
                    self.values['draw'].data = data
                except:
                    logger.exception('[%s] - Exception when drawing image', self.__class__.__name__)
                finally:
                    self._bus.spi_release()
            else:
                logger.warning("[%s] - Can't get lock when drawing image", self.__class__.__name__)

    def set_reset(self, node_uuid, index, data):
        """Reset the screen
        """
        if self._bus.spi_acquire( blocking = False ) == True:
            try:
                self.tft.reset()
            except:
                logger.exception('[%s] - Exception when resetting screen', self.__class__.__name__)
            finally:
                self._bus.spi_release()
        else:
            logger.warning("[%s] - Can't get lock when resetting screen", self.__class__.__name__)

    def set_clear(self, node_uuid, index, data):
        """Clear the screen with the color given in data
        """
        c1 = c2 = c3 = 0
        try:
            c1,c2,c3 = data.split(',')
            self.values['clear'].data = data
        except:
            logger.exception('[%s] - Exception when converting color : %s', self.__class__.__name__, data)
            try:
                c1,c2,c3 = self.values['clear'].default.split(',')
            except:
                logger.exception('[%s] - Exception when converting default color %s', self.__class__.__name__, self.values['clear'].default)
        if self._bus.spi_acquire( blocking = False ) == True:
            try:
                self.tft.clear(color=(c1,c2,c3))
            except:
                logger.exception('[%s] - Exception when resetting image', self.__class__.__name__)
            finally:
                self._bus.spi_release()
        else:
            logger.warning("[%s] - Can't get lock when resetting screen", self.__class__.__name__)

    def check_heartbeat(self):
        """Check that the component is 'available'

        """
        return self.tft is not None
