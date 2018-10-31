import time
import asyncio
from smc import SMC
from queue import Queue
from threading import Lock
from atlasbuggy import Node


class MotorControllerBridge(Node):
    def __init__(self, enabled=True):
        self.set_logger(write=True)
        super(MotorControllerBridge, self).__init__(enabled)
        if enabled:
            self.mc = SMC('/dev/serial/by-id/usb-Pololu_Corporation_Pololu_Simple_High-Power_Motor_Controller_18v15_33FF-6806-4D4B-3731-5147-1543-if00', 115200)
        else:
            self.mc = None

        self.queue_active_event = asyncio.Event()
        self.queue_lock = Lock()
        self.command_queue = Queue()
        self.pause_timestamp = None

    async def setup(self):
        self.logger.debug("Initializing...")
        self.mc.init()
        self.mc.speed(0)
        self.logger.debug("done!")

    def set_speed(self, command):
        command = int(-command)
        self.logger.debug("command: %s" % command)
        self.mc.speed(command)

    def queue_speed(self, command):
        self.command_queue.put(int(command))

    def run_queue(self):
        self.queue_active_event.set()

    def write_pause(self, timestamp):
        self.command_queue.put(float(timestamp))

    def clear_write_queue(self):
        self.command_queue.put(None)

    async def loop(self):
        while True:
            await self.queue_active_event.wait()

            self.logger.info("Executing motor command queue backlog")
            with self.queue_lock:
                while not self.command_queue.empty():
                    if self.pause_timestamp is not None:
                        # if pause timer has expired, reset the timer and continue sending commands
                        if time.time() > self.pause_timestamp:
                            self.pause_timestamp = None
                        await asyncio.sleep(0.0)
                        continue

                    command = self.command_queue.get()
                    if type(command) == int:
                        self.set_speed(command)
                    elif type(command) == float:
                        self.pause_timestamp = command
                    else:
                        # for any other type, cancel the queue
                        while not self.command_queue.empty():
                            self.command_queue.get()
                        break
                    await asyncio.sleep(0.0)

            self.logger.info("Command queue backlog finished!")
            self.queue_active_event.clear()


    async def teardown(self):
        self.logger.debug("Tearing down")
        self.mc.speed(0)
        # self.mc.stop()
