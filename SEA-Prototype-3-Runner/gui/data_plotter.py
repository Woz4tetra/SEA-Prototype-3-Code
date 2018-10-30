import asyncio
from threading import Event

from atlasbuggy import Node


class DataPlotter(Node):
    def __init__(self, enabled=True):
        super(DataPlotter, self).__init__(enabled)

        self.pause_time = 1 / 60
        self.exit_event = Event()
        self.plot_paused = False

        self.encoder_reader_bridge_tag = "encoder_reader_bridge"
        self.encoder_reader_bridge_sub = self.define_subscription(self.encoder_reader_bridge_tag, is_required=False, queue_size=5)
        self.encoder_reader_bridge_queue = None

        self.brake_controller_bridge_tag = "brake_controller_bridge"
        self.brake_controller_bridge_sub = self.define_subscription(self.brake_controller_bridge_tag, is_required=False, queue_size=5)
        self.brake_controller_bridge_queue = None

        self.diff_plot_time_window = 120.0
        self.enc_plot_time_window = 5.0
        self.brake_plot_time_window = 5.0

        self.encoder_diff_timestamps = []
        self.abs_encoder_diff_data = []
        self.rel_encoder_diff_data = []

        self.encoder_timestamps = []
        self.abs_encoder_data_1 = []
        self.abs_encoder_data_2 = []
        self.rel_encoder_data_1 = []
        self.rel_encoder_data_2 = []

        self.initial_val_enc_1 = None
        self.initial_val_enc_2 = None

        # self.gear_ratio = 48.0 / 32.0

        self.brake_timestamps = []
        self.brake_pin_value_data = []
        self.brake_current_mA_data = []
        self.brake_setpoint_data = []

        self.plt = None
        if self.enabled:
            self.enable_matplotlib()
            self.fig = self.plt.figure(1)
            self.fig.canvas.mpl_connect('key_press_event', self.press)
            self.fig.canvas.mpl_connect('close_event', lambda event: self.exit_event.set())

    def enable_matplotlib(self):
        from matplotlib import pyplot as plt
        self.plt = plt

    def take(self):
        if self.is_subscribed(self.encoder_reader_bridge_tag):
            self.encoder_reader_bridge_queue = self.encoder_reader_bridge_sub.get_queue()
        if self.is_subscribed(self.brake_controller_bridge_tag):
            self.brake_controller_bridge_queue = self.brake_controller_bridge_sub.get_queue()

    async def setup(self):
        # if self.is_subscribed(self.bno055_tag):
        #     self.bno_plot = self.fig.add_subplot(2, 1, 1)
        #     self.bno_data_line = self.bno_plot.plot([], [], '-', label="angle")[0]
        #
        #     self.speed_plot = self.fig.add_subplot(2, 1, 2)
        #
        #     self.bno_plot.legend(fontsize="x-small", shadow="True", loc=0)
        # else:
        self.diff_plot = self.fig.add_subplot(2, 2, 1)
        self.encoder_plot = self.fig.add_subplot(2, 2, 2)

        self.abs_diff_line = self.diff_plot.plot([], [], '-', label="abs diff")[0]
        self.rel_diff_line = self.diff_plot.plot([], [], '-', label="rel diff")[0]
        self.abs_encoder_line_1 = self.encoder_plot.plot([], [], '.-', label="abs enc1")[0]
        self.abs_encoder_line_2 = self.encoder_plot.plot([], [], '.-', label="abs enc2")[0]
        self.rel_encoder_line_1 = self.encoder_plot.plot([], [], '.-', label="rel enc1")[0]
        self.rel_encoder_line_2 = self.encoder_plot.plot([], [], '.-', label="rel enc2")[0]
        self.diff_plot.legend(fontsize="x-small", shadow="True", loc=0)
        self.encoder_plot.legend(fontsize="x-small", shadow="True", loc=0)

        self.brake_pin_value_plot = self.fig.add_subplot(2, 2, 3)
        self.brake_current_plot = self.fig.add_subplot(2, 2, 4)

        self.brake_pin_value_line = self.brake_pin_value_plot.plot([], [], '-', label="pin value")[0]
        self.brake_current_line = self.brake_current_plot.plot([], [], '.-', label="current (mA)")[0]
        self.brake_current_setpoint = self.brake_current_plot.plot([], [], '.-', label="setpoint")[0]
        self.brake_pin_value_plot.legend(fontsize="x-small", shadow="True", loc=0)
        self.brake_current_plot.legend(fontsize="x-small", shadow="True", loc=0)

        self.plt.ion()
        self.plt.show(block=False)

    async def loop(self):
        while True:
            if self.exit_event.is_set():
                return

            if self.plot_paused:
                await self.draw()
                continue

            self.get_encoder_data()
            self.get_brake_data()
            if self.is_subscribed(self.encoder_reader_bridge_tag):
                if len(self.encoder_diff_timestamps) == 0:
                    await self.draw()
                    continue

                while self.encoder_diff_timestamps[-1] - self.encoder_diff_timestamps[0] > self.diff_plot_time_window:
                    self.encoder_diff_timestamps.pop(0)
                    self.abs_encoder_diff_data.pop(0)
                    self.rel_encoder_diff_data.pop(0)

                while self.encoder_timestamps[-1] - self.encoder_timestamps[0] > self.enc_plot_time_window:
                    self.encoder_timestamps.pop(0)
                    self.abs_encoder_data_1.pop(0)
                    self.abs_encoder_data_2.pop(0)
                    self.rel_encoder_data_1.pop(0)
                    self.rel_encoder_data_2.pop(0)

            if self.is_subscribed(self.brake_controller_bridge_tag):
                if len(self.brake_timestamps) == 0:
                    await self.draw()
                    continue

                while self.brake_timestamps[-1] - self.brake_timestamps[0] > self.brake_plot_time_window:
                    self.brake_timestamps.pop(0)
                    self.brake_current_mA_data.pop(0)
                    self.brake_pin_value_data.pop(0)
                    self.brake_setpoint_data.pop(0)

            self.plot_data()
            await self.draw()

    def plot_data(self):
        if self.is_subscribed(self.encoder_reader_bridge_tag):
            self.abs_encoder_line_1.set_xdata(self.encoder_timestamps)
            self.abs_encoder_line_1.set_ydata(self.abs_encoder_data_1)

            self.abs_encoder_line_2.set_xdata(self.encoder_timestamps)
            self.abs_encoder_line_2.set_ydata(self.abs_encoder_data_2)

            self.rel_encoder_line_1.set_xdata(self.encoder_timestamps)
            self.rel_encoder_line_1.set_ydata(self.rel_encoder_data_1)

            self.rel_encoder_line_2.set_xdata(self.encoder_timestamps)
            self.rel_encoder_line_2.set_ydata(self.rel_encoder_data_2)

            self.abs_diff_line.set_xdata(self.encoder_diff_timestamps)
            self.abs_diff_line.set_ydata(self.abs_encoder_diff_data)

            self.rel_diff_line.set_xdata(self.encoder_diff_timestamps)
            self.rel_diff_line.set_ydata(self.rel_encoder_diff_data)

            self.encoder_plot.relim()
            self.encoder_plot.autoscale_view()

            self.diff_plot.relim()
            self.diff_plot.autoscale_view()

        if self.is_subscribed(self.brake_controller_bridge_tag):
            self.brake_pin_value_line.set_xdata(self.brake_timestamps)
            self.brake_pin_value_line.set_ydata(self.brake_pin_value_data)

            self.brake_current_line.set_xdata(self.brake_timestamps)
            self.brake_current_line.set_ydata(self.brake_current_mA_data)

            self.brake_current_setpoint.set_xdata(self.brake_timestamps)
            self.brake_current_setpoint.set_ydata(self.brake_setpoint_data)

            self.brake_pin_value_plot.relim()
            self.brake_pin_value_plot.autoscale_view()

            self.brake_current_plot.relim()
            self.brake_current_plot.autoscale_view()

    def get_encoder_data(self):
        if self.is_subscribed(self.encoder_reader_bridge_tag):
            while not self.encoder_reader_bridge_queue.empty():
                # message = await asyncio.wait_for(self.brake_controller_bridge_queue.get(), timeout=1)
                message = self.encoder_reader_bridge_queue.get_nowait()

                abs_encoder_1 = message.data[0]
                abs_encoder_2 = message.data[1]
                rel_encoder_1 = message.data[4]
                rel_encoder_2 = message.data[5]

                if self.initial_val_enc_1 is None:
                    self.initial_val_enc_1 = abs_encoder_1

                if self.initial_val_enc_2 is None:
                    self.initial_val_enc_2 = abs_encoder_2

                abs_enc1_angle = (abs_encoder_1 - self.initial_val_enc_1)
                abs_enc2_angle = (abs_encoder_2 - self.initial_val_enc_2)

                # enc1_angle = message.data[0] * self.gear_ratio
                # enc2_angle = message.data[1] * self.gear_ratio

                self.encoder_timestamps.append(message.timestamp)
                self.encoder_diff_timestamps.append(message.timestamp)
                self.abs_encoder_diff_data.append(abs_enc1_angle - abs_enc2_angle)
                self.rel_encoder_diff_data.append(rel_encoder_1 - rel_encoder_2)
                self.abs_encoder_data_1.append(abs_enc1_angle)
                self.abs_encoder_data_2.append(abs_enc2_angle)
                self.rel_encoder_data_1.append(rel_encoder_1)
                self.rel_encoder_data_2.append(rel_encoder_2)

    def get_brake_data(self):
        if self.is_subscribed(self.brake_controller_bridge_tag):
            while not self.brake_controller_bridge_queue.empty():
                message = self.brake_controller_bridge_queue.get_nowait()
                current_mA = message.data[2]
                pin_value = message.data[5]
                set_point = message.data[6]

                self.brake_timestamps.append(message.timestamp)
                self.brake_current_mA_data.append(current_mA)
                self.brake_pin_value_data.append(pin_value)
                self.brake_setpoint_data.append(set_point)

    def press(self, event):
        """matplotlib key press event. Close all figures when q is pressed"""
        if event.key == "q":
            self.exit_event.set()
        if event.key == " ":
            self.plot_paused = not self.plot_paused
            print("Plot is paused:", self.plot_paused)

    async def draw(self):
        self.fig.canvas.draw()
        self.plt.pause(self.pause_time)
        await asyncio.sleep(self.pause_time)

    async def teardown(self):
        self.plt.close("all")
