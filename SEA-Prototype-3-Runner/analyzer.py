import os
import time
import math
import asyncio
import peakutils
import numpy as np
import matplotlib.pyplot as plt

from arduino_factory import packet
from atlasbuggy.log.playback import PlaybackNode
from atlasbuggy import Orchestrator, Node, run

from experiment_helpers import *

class BrakePlayback(PlaybackNode):
    def __init__(self, filename, directory, enabled=True):
        super(BrakePlayback, self).__init__(
            "logs/%s/BrakeControllerBridge/%s" % (directory, filename),
            enabled=enabled, update_rate=0.0)
        self.done = False

    async def parse(self, line):
        message = packet.parse(line.message)
        # print(message is not None, line.message)
        if message is not None:
            await self.broadcast(message)

    async def completed(self):
        self.done = True

class EncoderPlayback(PlaybackNode):
    def __init__(self, filename, directory, enabled=True):
        super(EncoderPlayback, self).__init__(
            "logs/%s/EncoderReaderBridge/%s" % (directory, filename),
            enabled=enabled, update_rate=0.0)
        self.done = False

    async def parse(self, line):
        message = packet.parse(line.message)
        if message is not None:
            # self.logger.info("recovered: %s" % message)
            await self.broadcast(message)

    async def completed(self):
        self.done = True

class MotorPlayback(PlaybackNode):
    def __init__(self, filename, directory, enabled=True):
        super(MotorPlayback, self).__init__(
            "logs/%s/MotorControllerBridge/%s" % (directory, filename),
            enabled=enabled, update_rate=0.0)
        self.done = False
        self.command_flag = "command: "

    async def parse(self, line):
        if line.message == "Executing motor command queue backlog":
            await self.broadcast(("start", line.timestamp))
        elif line.message.startswith(self.command_flag):
            command = int(line.message[len(self.command_flag):])
            self.logger.info("recovered motor command: %s, %s" % (command, line.timestamp))
            await self.broadcast(("command", command, line.timestamp))
        elif line.message == "Command queue backlog finished!":
            await self.broadcast(("stop", line.timestamp))
        else:
            await asyncio.sleep(0.0)

    async def completed(self):
        self.done = True

class ExperimentPlayback(PlaybackNode):
    def __init__(self, filename, directory, enabled=True):
        super(ExperimentPlayback, self).__init__(
            "logs/%s/ExperimentNode/%s" % (directory, filename),
            enabled=enabled, update_rate=0.0)
        self.done = False

    async def parse(self, line):
        self.logger.info("recovered: %s" % line.message)
        await asyncio.sleep(0.0)

    async def completed(self):
        self.done = True

current_fig_num = 0

def new_fig(fig_num=None):
    """Create a new figure"""

    global current_fig_num, current_fig
    if fig_num is None:
        current_fig_num += 1
    else:
        current_fig_num = fig_num
    fig = plt.figure(current_fig_num)
    fig.canvas.mpl_connect('key_press_event', press)
    current_fig = fig

    return fig

def press(event):
    """matplotlib key press event. Close all figures when q is pressed"""
    if event.key == "q":
        plt.close("all")

def mkdir(path, is_file=True):
    if is_file:
        path = os.path.split(path)[0]  # remove the file part of the path

    if not os.path.isdir(path):
        os.makedirs(path)

def save_fig(path):
    path = "figures/%s.png" % path
    mkdir(path)
    print("saving to '%s'" % path)
    plt.savefig(path, dpi=200)

class DataAggregator(Node):
    def __init__(self, torque_table_path, filename, directory, save_figures=True, enabled=True):
        super(DataAggregator, self).__init__(enabled)

        self.torque_table = TorqueTable(torque_table_path)
        self.log_filename = os.path.splitext(filename)[0]
        self.log_directory = directory
        self.save_figures = save_figures

        self.brake_tag = "brake"
        self.brake_sub = self.define_subscription(self.brake_tag, message_type=packet.Packet, callback=self.brake_callback)
        self.brake = None

        self.encoders_tag = "encoders"
        self.encoders_sub = self.define_subscription(self.encoders_tag, message_type=packet.Packet, callback=self.encoders_callback)
        self.encoder = None

        self.motor_tag = "motor"
        self.motor_sub = self.define_subscription(self.motor_tag, message_type=tuple, callback=self.motor_callback)
        self.motor = None

        self.experiment_start_time = 0.0
        self.experiment_stop_time = 0.0
        self.motor_direction_switch_time = 0.0

        self.experiment_tag = "experiment"
        self.experiment_sub = self.define_subscription(self.experiment_tag, message_type=tuple, callback=self.experiment_callback)
        self.experiment = None

        self.brake_start_time = 0.0
        self.brake_timestamps = []
        self.brake_current = []

        self.exit_event = asyncio.Event()

        self.encoder_start_time = 0.0
        self.encoder_timestamps = []
        self.encoder_1_ticks = []
        self.encoder_2_ticks = []

    def take(self):
        self.brake = self.brake_sub.get_producer()
        self.encoders = self.encoders_sub.get_producer()
        self.motor = self.motor_sub.get_producer()
        self.experiment = self.experiment_sub.get_producer()

    async def loop(self):
        self.logger.info("waiting for data...")
        while not self.check_status():
            await asyncio.sleep(0.25)
        self.logger.info("done!")

    def brake_callback(self, message):
        if self.brake_start_time == 0.0:
            self.brake_start_time = message.receive_time
            print("brake start time: %s" % self.brake_start_time)
        self.brake_timestamps.append(message.timestamp + self.brake_start_time)
        self.brake_current.append(message.data[2])

    def encoders_callback(self, message):
        if self.encoder_start_time == 0.0:
            # teensy clock does not reset when a new USB connection is made
            self.encoder_start_time = message.receive_time - message.timestamp
            print("encoder start time: %s" % self.encoder_start_time)
        self.encoder_timestamps.append(message.timestamp + self.encoder_start_time)
        self.encoder_1_ticks.append(message.data[4])
        self.encoder_2_ticks.append(message.data[5])

    def motor_callback(self, message):
        if message[0] == "start":
            self.experiment_start_time = message[1]
        elif message[0] == "stop":
            self.experiment_stop_time = message[1]
        elif message[0] == "command":
            if message[1] > 0 and self.motor_direction_switch_time == 0.0:
                self.motor_direction_switch_time = message[2]

    def experiment_callback(self, message):
        pass

    def check_status(self):
        if self.brake.done and self.encoders.done and self.motor.done and self.experiment.done:
            self.logger.info("All done flags are True")
            return True
        else:
            return False


    async def teardown(self):
        rel_enc_ticks_to_rad = 2 * math.pi / 2000

        encoder_timestamps = np.array(self.encoder_timestamps)
        encoder_1_ticks = np.array(self.encoder_1_ticks)
        encoder_2_ticks = np.array(self.encoder_2_ticks)
        brake_timestamps = np.array(self.brake_timestamps)
        brake_current = np.array(self.brake_current)

        brake_ramp_transitions = peakutils.indexes(brake_current, thres=0.9, min_dist=500)
        motor_direction_switch_brake_index = (np.abs(brake_timestamps - self.motor_direction_switch_time)).argmin()
        assert len(brake_ramp_transitions) == 2, len(brake_ramp_transitions)
        assert motor_direction_switch_brake_index > brake_ramp_transitions[0], motor_direction_switch_brake_index

        encoder_delta = (encoder_1_ticks - encoder_2_ticks) * rel_enc_ticks_to_rad
        encoder_interp_delta = []

        interp_enc_index = 0
        for brake_t in brake_timestamps:
            # Encoder samples ~5 times faster than the brake's current feedback. Interpolate encoder values to brake timestamps
            while encoder_timestamps[interp_enc_index] < brake_t:
                interp_enc_index += 1
                if interp_enc_index >= len(encoder_timestamps):
                    interp_enc_index -= 1
                    break
            enc_index = interp_enc_index

            encoder_interp_delta.append(encoder_delta[enc_index])


        # convert sensed current to torque (Nm)
        brake_current_forcing_forward = brake_current[0:brake_ramp_transitions[0]]
        brake_current_unforcing_forward = brake_current[brake_ramp_transitions[0]:motor_direction_switch_brake_index]
        brake_current_forcing_backward = brake_current[motor_direction_switch_brake_index:brake_ramp_transitions[1]]
        brake_current_unforcing_backward = brake_current[brake_ramp_transitions[1]:]

        btff = self.torque_table.to_torque(True, brake_current_forcing_forward)
        btuf = self.torque_table.to_torque(False, brake_current_unforcing_forward)
        btfb = -self.torque_table.to_torque(True, brake_current_forcing_backward)
        btub = -self.torque_table.to_torque(False, brake_current_unforcing_backward)
        brake_torque_nm = np.concatenate((btff, btuf, btfb, btub))

        polynomial = np.polyfit(encoder_interp_delta, brake_torque_nm, 1)
        linear_regression_fn = np.poly1d(polynomial)
        encoder_lin_reg = linear_regression_fn(encoder_interp_delta)

        new_fig()
        plt.title("Raw Encoder Data")
        plt.xlabel("Time (s)")
        plt.ylabel("Delta angle (rad)")
        plt.plot(encoder_timestamps, encoder_delta, label="all values")
        plt.plot(brake_timestamps, encoder_interp_delta, 'x', markersize=0.1, label="used points")
        plt.axvline(self.experiment_start_time, color="black")
        plt.axvline(self.experiment_stop_time, color="black")
        plt.legend()
        if self.save_figures:
            save_fig("%s-%s/raw_encoder_data" % (self.log_directory, self.log_filename))

        new_fig()
        plt.title("Raw Brake Data")
        plt.xlabel("Time (s)")
        plt.ylabel("Current sensed (mA)")
        plt.plot(brake_timestamps, brake_current)
        plt.plot(brake_timestamps[brake_ramp_transitions], brake_current[brake_ramp_transitions], 'x')
        plt.axvline(self.experiment_start_time, color="black")
        plt.axvline(self.experiment_stop_time, color="black")
        if self.save_figures:
            save_fig("%s-%s/raw_brake_data" % (self.log_directory, self.log_filename))

        new_fig()
        plt.title("Brake torque vs. delta angle")
        plt.xlabel("Delta angle (rad)")
        plt.ylabel("Brake torque (Nm)")
        plt.plot(encoder_interp_delta, brake_torque_nm, '.', markersize=0.5)
        plt.plot(encoder_interp_delta, encoder_lin_reg, label='m=%0.4fNm/rad, b=%0.4fNm' % (polynomial[0], polynomial[1]))
        plt.plot(0, 0, '+', markersize=15)
        plt.legend()
        if self.save_figures:
            save_fig("%s-%s/torque_vs_angle" % (self.log_directory, self.log_filename))

        plt.show()



class PlaybackOrchestrator(Orchestrator):
    def __init__(self, event_loop):
        self.set_default(write=False)

        super(PlaybackOrchestrator, self).__init__(event_loop, return_when=asyncio.ALL_COMPLETED)

        # filename = "20_56_08.log"
        filename = "22_35_04.log"
        directory = "2018_Oct_30"
        torque_table_path = "brake_torque_data/B15 Torque Table.csv"

        self.brake = BrakePlayback(filename, directory)
        self.motor = MotorPlayback(filename, directory)
        self.encoders = EncoderPlayback(filename, directory)
        self.experiment = ExperimentPlayback(filename, directory)
        self.aggregator = DataAggregator(torque_table_path, filename, directory, save_figures=True, enabled=True)

        # self.add_nodes(self.brake, self.motor, self.encoders, self.experiment)
        self.subscribe(self.brake, self.aggregator, self.aggregator.brake_tag)
        self.subscribe(self.motor, self.aggregator, self.aggregator.motor_tag)
        self.subscribe(self.encoders, self.aggregator, self.aggregator.encoders_tag)
        self.subscribe(self.experiment, self.aggregator, self.aggregator.experiment_tag)

        self.t0 = 0
        self.t1 = 0

    async def setup(self):
        self.t0 = time.time()

    async def loop(self):
        pass

    async def teardown(self):
        self.t1 = time.time()

        print("took: %ss" % (self.t1 - self.t0))

run(PlaybackOrchestrator)
