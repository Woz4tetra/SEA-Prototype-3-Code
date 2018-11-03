import time
import asyncio
import numpy as np
from atlasbuggy import Node

from experiment_helpers import *

class ExperimentNode(Node):
    def __init__(self, step_duration, num_steps, min_current_mA, torque_table_path, enabled=True):
        self.set_logger(write=True)
        super(ExperimentNode, self).__init__(enabled)
        self.brake_controller_bridge_tag = "brake_controller_bridge"
        self.brake_controller_bridge_sub = self.define_subscription(
            self.brake_controller_bridge_tag,
            queue_size=None,
            required_methods=("command_brake",)
        )
        self.brake_controller_bridge = None
        # self.brake_controller_bridge_queue = None

        self.motor_controller_bridge_tag = "motor_controller_bridge"
        self.motor_controller_bridge_sub = self.define_subscription(
            self.motor_controller_bridge_tag,
            queue_size=None,
            required_methods=("queue_speed", "write_pause", "run_queue", "clear_write_queue"),
        )
        self.motor_controller_bridge = None

        self.encoder_reader_bridge_tag = "encoder_reader_bridge"
        self.encoder_reader_bridge_sub = self.define_subscription(self.encoder_reader_bridge_tag, queue_size=5)
        self.encoder_reader_bridge_queue = None

        self.torque_table = TorqueTable(torque_table_path)
        self.min_torque_forcing = self.torque_table.to_torque(True, min_current_mA)
        self.min_torque_unforcing = self.torque_table.to_torque(False, min_current_mA)

        self.experiment_step_duration = step_duration
        self.experiment_num_steps = num_steps

        self.experiment_time = time.time()

        self.taking_sample_lock = asyncio.Event()
        self.sample_duration = 0.0

        self.logger.info(
            "Experiment:\n"
            "\tStep duration: %f\n"
            "\tNumber of steps: %d\n"
            "\tApprox. experiment duration: %f\n"
            "\tTorque step resolution: %f\n"
            "\tTorque range: %f..%f (forcing), %f..%f (unforcing)\n"
            "\tTorque table path: %s" % (
                self.experiment_step_duration,
                self.experiment_num_steps,
                # experiments consist of a ramp up, ramp down, motor direction change and repeat
                self.experiment_step_duration * self.experiment_num_steps * 4,
                self.torque_table.max_torque / self.experiment_num_steps,
                self.min_torque_forcing, self.torque_table.max_torque,
                self.min_torque_unforcing, self.torque_table.max_torque,
                torque_table_path
            )
        )

    def take(self):
        self.brake_controller_bridge = self.brake_controller_bridge_sub.get_producer()
        # self.brake_controller_bridge_queue = self.brake_controller_bridge_sub.get_queue()
        self.motor_controller_bridge = self.motor_controller_bridge_sub.get_producer()
        self.encoder_reader_bridge_queue = self.encoder_reader_bridge_sub.get_queue()
        # self.brake_controller_bridge_sub.enabled = False
        self.encoder_reader_bridge_sub.enabled = False

    def run_experiment(self):
        self.experiment_time = time.time()
        self.motor_controller_bridge.queue_speed(3200)
        self.write_pause(self.experiment_step_duration + 2.0)

        self.ramp_up_brake()
        self.ramp_down_brake()
        self.write_pause(self.experiment_step_duration + 2.0)

        self.motor_controller_bridge.queue_speed(-3200)
        self.write_pause(self.experiment_step_duration + 2.0)

        self.ramp_up_brake()
        self.ramp_down_brake()
        self.write_pause(self.experiment_step_duration + 2.0)

        self.motor_controller_bridge.queue_speed(0)
        self.brake_controller_bridge.command_brake(0)

        self.motor_controller_bridge.run_queue()

    def cancel_experiment(self):
        self.motor_controller_bridge.clear_write_queue()
        self.brake_controller_bridge.brake_controller_bridge_arduino.clear_write_queue()

        self.motor_controller_bridge.set_speed(0)
        self.brake_controller_bridge.command_brake(0)

    def take_sample(self, length_sec):
        self.taking_sample_lock.set()
        self.encoder_reader_bridge_sub.enabled = True
        # self.brake_controller_bridge_sub.enabled = True
        self.sample_duration = length_sec

    async def loop(self):
        while True:
            await self.taking_sample_lock.wait()

            # encoder_timestamps = []
            encoder_1_ticks = []
            encoder_2_ticks = []
            # brake_timestamps = []
            # brake_current = []

            sample_start_time = time.time()
            while time.time() - sample_start_time < self.sample_duration:
                while not self.encoder_reader_bridge_queue.empty():
                    message = await self.encoder_reader_bridge_queue.get()

                    # encoder_timestamps.append(message.timestamp)
                    encoder_1_ticks.append(message.data[4])
                    encoder_2_ticks.append(message.data[5])
                await asyncio.sleep(0.0)

                # while not self.brake_controller_bridge_queue.empty():
                #     message = await self.brake_controller_bridge_queue.get()
                #     brake_timestamps.append(message.timestamp)
                #     brake_current.append(message.data[2])

            # encoder_timestamps = np.array(encoder_timestamps)
            encoder_1_ticks = np.array(encoder_1_ticks)
            encoder_2_ticks = np.array(encoder_2_ticks)
            encoder_delta = encoder_1_ticks - encoder_2_ticks
            # brake_timestamps = np.array(brake_timestamps)
            # brake_current = np.array(brake_current)
            #
            # encoder_interp_delta = interpolate_encoder_values(
            #     encoder_timestamps, encoder_1_ticks, encoder_2_ticks,
            #     default_rel_enc_ticks_to_rad, brake_timestamps
            # )
            # brake_torque_forcing_nm = self.torque_table.to_torque(True, brake_current)
            # brake_torque_unforcing_nm = self.torque_table.to_torque(False, brake_current)
            #
            encoder_delta_rad_avg = np.mean(encoder_delta) * default_rel_enc_ticks_to_rad
            # brake_torque_forcing_nm_avg = np.mean(brake_torque_forcing_nm)
            # brake_torque_unforcing_nm_avg = np.mean(brake_torque_unforcing_nm)
            #
            # k_forced = brake_torque_forcing_nm_avg / encoder_delta_rad_avg
            # k_unforced = brake_torque_unforcing_nm_avg / encoder_delta_rad_avg
            #
            # print(
            #     "Sample results:\n"
            #     "\tDisplacement (rad): %s\n"
            #     "\tTorque, forced (N): %s\n"
            #     "\tTorque, unforced (N): %s\n"
            #     "\tK, forced (Nm): %s\n"
            #     "\tK, unforced (Nm): %s" % (encoder_delta_rad_avg,
            #         brake_torque_forcing_nm_avg, brake_torque_unforcing_nm_avg,
            #         k_forced, k_unforced
            #     )
            # )
            print(
                "Sample results:\n"
                "\tDisplacement (rad): %s\n" % str(encoder_delta_rad_avg)
            )

            self.encoder_reader_bridge_sub.enabled = False
            # self.brake_controller_bridge_sub.enabled = False
            self.taking_sample_lock.clear()

    def ramp_up_brake(self):
        for step_num in range(self.experiment_num_steps):
            current_mA = self.get_forcing_current_mA(step_num)
            self.brake_controller_bridge.command_brake(current_mA)
            self.write_pause(self.experiment_step_duration)

    def ramp_down_brake(self):
        for step_num in range(self.experiment_num_steps - 1, -1, -1):
            current_mA = self.get_unforcing_current_mA(step_num)
            self.brake_controller_bridge.command_brake(current_mA)
            self.write_pause(self.experiment_step_duration)

    def get_forcing_current_mA(self, step_num):
        percent_torque = (step_num + 1) / self.experiment_num_steps
        torque = percent_torque * (self.torque_table.max_torque - self.min_torque_forcing) + self.min_torque_forcing
        current_mA = self.torque_table.to_current_mA(True, torque)
        return current_mA

    def get_unforcing_current_mA(self, step_num):
        percent_torque = (step_num + 1) / self.experiment_num_steps
        torque = percent_torque * (self.torque_table.max_torque - self.min_torque_unforcing) + self.min_torque_unforcing
        current_mA = self.torque_table.to_current_mA(False, torque)
        return current_mA

    def write_pause(self, time_interval):
        self.experiment_time += time_interval
        self.motor_controller_bridge.write_pause(self.experiment_time)
        self.brake_controller_bridge.brake_controller_bridge_arduino.write_pause(self.experiment_time, relative_time=False)
