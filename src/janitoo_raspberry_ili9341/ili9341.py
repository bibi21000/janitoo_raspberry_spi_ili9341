# -*- coding: utf-8 -*-
"""The Raspberry lcdchar thread

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
__copyright__ = "Copyright © 2013-2014-2015 Sébastien GALLET aka bibi21000"

import logging
logger = logging.getLogger(__name__)
import os, sys
import threading

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

COMMAND_MOTOR = 0x3100
COMMAND_SWITCH_MULTILEVEL = 0x0026
COMMAND_SWITCH_BINARY = 0x0025

assert(COMMAND_DESC[COMMAND_SWITCH_MULTILEVEL] == 'COMMAND_SWITCH_MULTILEVEL')
assert(COMMAND_DESC[COMMAND_SWITCH_BINARY] == 'COMMAND_SWITCH_BINARY')
assert(COMMAND_DESC[COMMAND_MOTOR] == 'COMMAND_MOTOR')
##############################################################

def make_screen(**kwargs):
    return ScreenComponent(**kwargs)

class ScreenComponent(JNTComponent):
    """ A Screen component for gpio """

    def __init__(self, bus=None, addr=None, **kwargs):
        """
        """
        oid = kwargs.pop('oid', 'rpiili9341.screen')
        name = kwargs.pop('name', "Screen")
        product_name = kwargs.pop('product_name', "Screen")
        product_type = kwargs.pop('product_type', "Screen")
        product_manufacturer = kwargs.pop('product_manufacturer', "Janitoo")
        JNTComponent.__init__(self, oid=oid, bus=bus, addr=addr, name=name,
                product_name=product_name, product_type=product_type, product_manufacturer=product_manufacturer, **kwargs)
        logger.debug("[%s] - __init__ node uuid:%s", self.__class__.__name__, self.uuid)
        uuid="message"
        self.values[uuid] = self.value_factory['action_string'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='A message to print on the screen',
            label='Msg',
            default='Janitoo started',
            set_data_cb=self.set_message,
            is_writeonly = True,
            cmd_class=COMMAND_MOTOR,
            genre=0x01,
        )
        poll_value = self.values[uuid].create_poll_value(default=300)
        self.values[poll_value.uuid] = poll_value
        self.pin_lcd_rs        = 27  # Note this might need to be changed to 21 for older revision Pi's.
        self.pin_lcd_en        = 22
        self.pin_lcd_d4        = 25
        self.pin_lcd_d5        = 24
        self.pin_lcd_d6        = 23
        self.pin_lcd_d7        = 18
        self.pin_lcd_backlight = 4
        self.lcd_columns = 20
        self.lcd_rows    = 4
        self.tft = None
        #~ self.lcd = Adafruit_CharLCD(self.pin_lcd_rs, self.pin_lcd_en, self.pin_lcd_d4, self.pin_lcd_d5, self.pin_lcd_d6, self.pin_lcd_d7,
                            #~ self.lcd_columns, self.lcd_rows, self.pin_lcd_backlight)

    def set_message(self, node_uuid, index, data):
        """Set the message on the screen
        """
        try:
            lcd.clear()
            lcd.message(data)
        except:
            logger.exception('Exception when displaying message')
