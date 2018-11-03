import time
import math
import asyncio
from atlasbuggy import Node
from arduino_factory import Arduino


class EncoderReaderBridge(Node):
    def __init__(self, factory, enabled=True, enable_reporting=True):
        self.set_logger(write=True)
        super(EncoderReaderBridge, self).__init__(enabled)
        self.factory = factory
        self.encoder_reader_bridge_arduino = Arduino("encoder_reader", self.factory)

        self.prev_broadcast_time = 0.0
        self.prev_report_time = 0.0
        self.enable_reporting = enable_reporting

        self.num_packets_received = 0

    async def setup(self):
        start_packet = self.encoder_reader_bridge_arduino.start()
        # self.initial_abs_enc1 = -start_packet.data[0]
        # self.initial_abs_enc2 = -start_packet.data[1]

        self.prev_broadcast_time = time.time()
        self.prev_report_time = time.time()

    async def loop(self):

        while self.factory.ok():
            time_diff = 0.0
            packet = None
            while time_diff == 0.0 or time_diff > 0.1: # don't let the packets get behind
                packet = self.encoder_reader_bridge_arduino.read()
                self.log_to_buffer(packet.receive_time, packet)
                self.num_packets_received += 1
                time_diff = time.time() - packet.receive_time

            await asyncio.sleep(0.0)

            if packet.name is None:
                self.logger.warning("No packets found!")

            elif packet.name == "enc":
                # abs_enc1_angle = packet.data[0]
                # abs_enc2_angle = packet.data[1]
                # abs_enc1_analog = packet.data[2]
                # abs_enc2_analog = packet.data[3]
                # enc1_pos = packet.data[4]
                # enc2_pos = packet.data[5]
                # motor_pos = packet.data[6]

                # if time.time() - self.prev_broadcast_time > 0.25:
                if self.enable_reporting and time.time() - self.prev_report_time > 1.0:
                    try:
                        print("abs_enc1_angle: %0.6f\n"
                              "abs_enc2_angle: %0.6f\n"
                              "abs_enc1_analog: %d\n"
                              "abs_enc2_analog: %d\n"
                              "enc1_pos: %0.6f\n"
                              "enc2_pos: %0.6f\n"
                              "motor_pos: %0.6f" % tuple(packet.data))
                        print()
                    except TypeError as error:
                        print("The encoder reader bridge encountered a formatting error while reporting values:")
                        print(error)
                    self.prev_report_time = time.time()
                self.prev_broadcast_time = time.time()

                await self.broadcast(packet)

    async def teardown(self):
        self.factory.stop_all()
        self.logger.info("packets per sec: %s" % (self.num_packets_received / (time.time() - self.start_time)))
