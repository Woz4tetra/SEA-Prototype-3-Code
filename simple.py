# from smc import SMC
# import time
#
# mc = SMC('/dev/cu.usbmodem142401', 115200)
# # open serial port and exit safe mode
# mc.init()
#
# # drive using 12b mode
# mc.speed(1000)
# time.sleep(3)
# mc.speed(-1000)
# time.sleep(3)
#
# # drive using 7b mode
# mc.speed7b(100)
# time.sleep(3)
# mc.speed7b(-100)
# time.sleep(3)
#
# # and stop motor
# mc.stop()

# import serial
# import time
import os

dev_folder = os.listdir("/dev")
for entry in dev_folder:
    if entry.find("usb") > -1:
        print(entry)
# 
# s = serial.Serial("/dev/tty.usbmodem142401", 115200, timeout=1.0)
# time.sleep(1.0)
#
# s.write((0x83,))
# time.sleep(0.1)
# s.write((0xe0,))
# s.close()
