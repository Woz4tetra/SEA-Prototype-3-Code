import time
from atlasbuggy import Orchestrator, Node, run

from data_processing.experiment_helpers.plot_helpers import *
from data_processing.experiment_helpers.k_calculator_helpers import compute_k
from data_processing.hardware_playback import *
from data_processing.torque_table import TorqueTable


class DataAggregator(Node):
    def __init__(self, torque_table_path, filename, directory, conical_annulus_size, save_figures=True, enabled=True,
                 enable_smoothing=False):
        super(DataAggregator, self).__init__(enabled)

        self.torque_table = TorqueTable(torque_table_path)
        self.log_filename = os.path.splitext(filename)[0]
        self.log_directory = directory
        self.conical_annulus_size = conical_annulus_size
        self.save_figures = save_figures
        self.enable_smoothing = enable_smoothing

        self.brake_tag = "brake"
        self.brake_sub = self.define_subscription(self.brake_tag, message_type=packet.Packet,
                                                  callback=self.brake_callback)
        self.brake = None

        self.encoders_tag = "encoders"
        self.encoders_sub = self.define_subscription(self.encoders_tag, message_type=packet.Packet,
                                                     callback=self.encoders_callback)
        self.encoder = None

        self.motor_tag = "motor"
        self.motor_sub = self.define_subscription(self.motor_tag, message_type=tuple, callback=self.motor_callback)
        self.motor = None

        self.experiment_start_time = 0.0
        self.experiment_stop_time = 0.0
        self.motor_direction_switch_time = 0.0

        self.experiment_tag = "experiment"
        self.experiment_sub = self.define_subscription(self.experiment_tag, message_type=tuple,
                                                       callback=self.experiment_callback)
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
        encoder_timestamps, encoder_delta, encoder_interp_delta, encoder_lin_reg, \
        brake_timestamps, brake_current, brake_ramp_transitions, brake_torque_nm, polynomial = \
            compute_k(
                self.torque_table,
                self.encoder_timestamps, self.encoder_1_ticks, self.encoder_2_ticks,
                self.brake_timestamps, self.brake_current,
                self.motor_direction_switch_time, self.enable_smoothing
            )

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
            save_fig("%s/%s-%s/raw_encoder_data" % (self.conical_annulus_size, self.log_directory, self.log_filename))

        new_fig()
        plt.title("Raw Brake Data")
        plt.xlabel("Time (s)")
        plt.ylabel("Current sensed (mA)")
        plt.plot(brake_timestamps, brake_current)
        if brake_ramp_transitions is not None:
            plt.plot(brake_timestamps[brake_ramp_transitions], brake_current[brake_ramp_transitions], 'x')
        plt.axvline(self.experiment_start_time, color="black")
        plt.axvline(self.experiment_stop_time, color="black")
        if self.save_figures:
            save_fig("%s/%s-%s/raw_brake_data" % (self.conical_annulus_size, self.log_directory, self.log_filename))

        if brake_torque_nm is not None:
            new_fig()
            plt.title("Brake torque vs. delta angle")
            plt.xlabel("Delta angle (rad)")
            plt.ylabel("Brake torque (Nm)")
            plt.plot(encoder_interp_delta, brake_torque_nm, '.', markersize=0.5)
            plt.plot(encoder_interp_delta, encoder_lin_reg,
                     label='m=%0.4fNm/rad, b=%0.4fNm' % (polynomial[0], polynomial[1]))
            plt.plot(0, 0, '+', markersize=15)
            plt.legend()
            if self.save_figures:
                save_fig(
                    "%s/%s-%s/torque_vs_angle" % (self.conical_annulus_size, self.log_directory, self.log_filename))

        plt.show()


class PlaybackOrchestrator(Orchestrator):
    def __init__(self, event_loop):
        self.set_default(write=False)

        super(PlaybackOrchestrator, self).__init__(event_loop, return_when=asyncio.ALL_COMPLETED)

        # filename = "20_56_08.log"
        # filename = "22_35_04.log"
        # directory = "2018_Oct_30"
        # conical_annulus_size = "0.25x1.25x0.49"
        # torque_table_path = "brake_torque_data/B15 Torque Table.csv"
        # enable_smoothing = False

        filename = "23_45_11.log"
        directory = "2018_Nov_06"
        conical_annulus_size = "0.25x1.25x0.49"
        torque_table_path = "brake_torque_data/B5Z Torque Table.csv"
        enable_smoothing = True

        self.brake = BrakePlayback(filename, directory)
        self.motor = MotorPlayback(filename, directory)
        self.encoders = EncoderPlayback(filename, directory)
        self.experiment = ExperimentPlayback(filename, directory)
        self.aggregator = DataAggregator(
            torque_table_path, filename, directory, conical_annulus_size,
            save_figures=True, enabled=True, enable_smoothing=enable_smoothing
        )

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