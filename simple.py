from smc import SMC
import time

mc = SMC('/dev/serial/by-id/usb-Pololu_Corporation_Pololu_Simple_High-Power_Motor_Controller_18v15_33FF-6806-4D4B-3731-5147-1543-if00', 115200)
# open serial port and exit safe mode
mc.init()

# drive using 12b mode
mc.speed(1000)
time.sleep(3)
mc.speed(-1000)
time.sleep(3)

# drive using 7b mode
mc.speed7b(100)
time.sleep(3)
mc.speed7b(-100)
time.sleep(3)

# and stop motor
mc.stop()
