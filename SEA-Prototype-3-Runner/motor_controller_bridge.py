import time
import asyncio
from smc import SMC
from atlasbuggy import Node


class MotorControllerBridge(Node):
    def __init__(self, enabled=True):
        super(MotorControllerBridge, self).__init__(enabled)
        if enabled:
            self.mc = SMC('/dev/serial/by-id/usb-Pololu_Corporation_Pololu_Simple_High-Power_Motor_Controller_18v15_33FF-6806-4D4B-3731-5147-1543-if00', 115200)
        else:
            self.mc = None

    async def setup(self):
        self.mc.init()
        self.mc.speed(0)

    def set_speed(self, command):
        self.mc.speed(int(command))

    async def teardown(self):
        self.mc.speed(0)
        # self.mc.stop()
