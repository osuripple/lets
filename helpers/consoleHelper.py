"""Some console related functions"""
import logging

from common.constants import bcolors
from objects import glob


ASCII = """ (                 (     
 )\\ )        *   ) )\\ )  
(()/(  (   ` )  /((()/(  
 /(_)) )\\   ( )(_))/(_)) 
(_))  ((_) (_(_())(_))   
| |   | __||_   _|/ __|  
| |__ | _|   | |  \\__ \\  
|____||___|  |_|  |___/  \n"""


def printServerStartHeader(asciiArt):
	"""
	Print server start header with optional ascii art

	asciiArt -- if True, will print ascii art too
	"""

	if asciiArt:
		ascii_list = ASCII.split("\n")
		for i, x in enumerate(ascii_list):
			logging.info(x)

	logging.info("Welcome to the Latest Essential Tatoe Server v{}".format(glob.VERSION))
	logging.info("Made by the Ripple team")
	logging.info("https://zxq.co/ripple/lets")
