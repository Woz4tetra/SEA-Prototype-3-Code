import time
import asyncio
from atlasbuggy import Node
from arduino_factory import Arduino


class BrakeControllerBridge(Node):
    def __init__(self, factory, enabled=True, enable_reporting=True):
        self.set_logger(write=True)
        super(BrakeControllerBridge, self).__init__(enabled)
        self.factory = factory
        self.brake_controller_bridge_arduino = Arduino("brake_controller", self.factory)

        self.prev_broadcast_time = 0.0
        self.prev_report_time = 0.0
        self.enable_reporting = enable_reporting

        self.kp = 0.0
        self.ki = 0.0
        self.kd = 0.0

    async def setup(self):
        start_packet = self.brake_controller_bridge_arduino.start()
        self.kp = start_packet.data[0]
        self.ki = start_packet.data[1]
        self.kd = start_packet.data[2]

        self.prev_broadcast_time = time.time()
        self.prev_report_time = time.time()

        self.logger.debug("start_packet: '%s'" % (str(start_packet)))

    async def loop(self):
        while self.factory.ok():
            packet = self.brake_controller_bridge_arduino.read()
            self.logger.debug("packet: '%s'" % (str(packet)))
            await asyncio.sleep(0.0)

            if packet.name is None:
                self.logger.warning("No packets found!")

            elif packet.name == "brake":
                # shunt_voltage = packet.data[0]
                # bus_voltage = packet.data[1]
                # current_mA = packet.data[2]
                # power_mW = packet.data[3]
                # load_voltage = packet.data[4]
                # current_pin_value = packet.data[5]
                # set_point = packet.data[6]
                self.log_to_buffer(packet.receive_time, packet)

                # if time.time() - self.prev_broadcast_time > 0.25:
                if self.enable_reporting and time.time() - self.prev_report_time > 1.0:
                    try:
                        print("shunt voltage (V): %0.2f\n"
                              "bus voltage (V): %0.2f\n"
                              "current (mA): %0.2f\n"
                              "power (mW): %0.2f\n"
                              "load voltage (V): %0.2f\n"
                              "pwm pin value: %s\n"
                              "set point (mA): %0.2f\n" % tuple(packet.data))
                    except TypeError as error:
                        print("The brake controller bridge encountered a formatting error while reporting values:")
                        print(error)
                    self.prev_report_time = time.time()
                self.prev_broadcast_time = time.time()

                await self.broadcast(packet)

    def command_brake(self, command):
        self.brake_controller_bridge_arduino.write("b" + str(float(command)))

    def set_kp(self, kp):
        self.kp = kp
        self.brake_controller_bridge_arduino.write("kp" + str(float(kp)))

    def set_ki(self, ki):
        self.ki = ki
        self.brake_controller_bridge_arduino.write("ki" + str(float(ki)))

    def set_kd(self, kd):
        self.kd = kd
        self.brake_controller_bridge_arduino.write("kd" + str(float(kd)))

    async def teardown(self):
        self.factory.stop_all()
