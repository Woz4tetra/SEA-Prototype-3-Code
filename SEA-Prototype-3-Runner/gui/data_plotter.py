import asyncio
from threading import Event
from atlasbuggy import Node

from data_processing.experiment_helpers import *


class LineArgsContainer:
    def __init__(self, name, *plot_args, enabled=True, **plot_kwargs):
        self.name = name
        self.enabled = enabled
        self.args = plot_args
        self.kwargs = plot_kwargs


class PlotContainer:
    def __init__(self, name, plot, *line_arg_containers, x_data_window=0.0, enabled=True):
        self.name = name
        self.enabled = enabled
        self.x_data = []
        self.y_data = {}
        self.plot = plot
        self.lines = {}
        self.x_data_window = x_data_window
        self.disabled_lines = set()

        for line_args_container in line_arg_containers:
            name = line_args_container.name
            if line_args_container.enabled:
                args = line_args_container.args
                kwargs = line_args_container.kwargs

                self.y_data[name] = []
                self.lines[name] = self.plot.plot([], [], *args, **kwargs)[0]
            else:
                self.disabled_lines.add(name)

        if len(self.y_data) == 0:
            self.enabled = False

    def append_x(self, datum):
        if self.enabled:
            self.x_data.append(datum)

    def append_y(self, line_name, datum):
        if line_name in self.disabled_lines:
            return

        if self.enabled:
            self.y_data[line_name].append(datum)

    def update_lines(self):
        if not self.enabled:
            return

        if self.x_data_window > 0.0:
            while self.x_data[-1] - self.x_data[0] > self.x_data_window:
                self.x_data.pop(0)
                for y_data_line in self.y_data.values():
                    y_data_line.pop(0)

        for line_name, line_plot in self.lines.items():
            line_plot.set_xdata(self.x_data)
            line_plot.set_ydata(self.y_data[line_name])


class DataPlotter(Node):
    def __init__(self, enabled=True):
        super(DataPlotter, self).__init__(enabled)

        self.pause_time = 1 / 60
        self.exit_event = Event()
        self.plot_paused = False

        self.encoder_reader_bridge_tag = "encoder_reader_bridge"
        self.encoder_reader_bridge_sub = self.define_subscription(self.encoder_reader_bridge_tag, queue_size=5)
        self.encoder_reader_bridge_queue = None

        self.brake_controller_bridge_tag = "brake_controller_bridge"
        self.brake_controller_bridge_sub = self.define_subscription(self.brake_controller_bridge_tag, queue_size=5)
        self.brake_controller_bridge_queue = None

        self.diff_plot_container = None
        self.encoder_plot_container = None
        self.brake_pin_plot_container = None
        self.brake_current_plot_container = None

        self.initial_val_enc_1 = None
        self.initial_val_enc_2 = None

        self.rel_enc_ticks_to_rad = default_rel_enc_ticks_to_rad
        self.motor_enc_ticks_to_rad = default_motor_enc_ticks_to_rad
        self.abs_gear_ratio = default_abs_gear_ratio

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
        self.encoder_reader_bridge_queue = self.encoder_reader_bridge_sub.get_queue()
        self.brake_controller_bridge_queue = self.brake_controller_bridge_sub.get_queue()

    async def setup(self):
        self.diff_plot = self.fig.add_subplot(2, 2, 1)
        self.encoder_plot = self.fig.add_subplot(2, 2, 2)
        self.brake_pin_value_plot = self.fig.add_subplot(2, 2, 3)
        self.brake_current_plot = self.fig.add_subplot(2, 2, 4)

        self.diff_plot_container = PlotContainer(
            "diff", self.diff_plot,
            LineArgsContainer("abs", '-', enabled=False, label="abs diff"),
            LineArgsContainer("rel", '-', enabled=True, label="rel diff"),
            LineArgsContainer("motor", '-', enabled=False, label="motor diff"),
            x_data_window = 120.0
        )
        self.encoder_plot_container = PlotContainer(
            "encoder", self.encoder_plot,
            LineArgsContainer("abs enc 1", '.-', enabled=False, label="abs enc1"),
            LineArgsContainer("abs enc 2", '.-', enabled=False, label="abs enc2"),
            LineArgsContainer("rel enc 1", '.-', enabled=True, label="rel enc1"),
            LineArgsContainer("rel enc 2", '.-', enabled=True, label="rel enc2"),
            LineArgsContainer("motor", '.-', enabled=True, label="motor"),
            x_data_window = 10.0
        )

        self.brake_pin_plot_container = PlotContainer(
            "brake pin", self.brake_pin_value_plot,
            LineArgsContainer("pin", '-', enabled=True, label="pin value"),

        )
        self.brake_current_plot_container = PlotContainer(
            "brake current", self.brake_current_plot,
            LineArgsContainer("current", '.-', enabled=True, label="current (mA)"),
            LineArgsContainer("setpoint", '.-', enabled=True, label="setpoint"),
        )

        self.diff_plot.legend(fontsize="x-small", shadow="True", loc=0)
        self.encoder_plot.legend(fontsize="x-small", shadow="True", loc=0)
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

            await self.get_encoder_data()
            await self.get_brake_data()

            if len(self.diff_plot_container.x_data) == 0 and len(self.brake_current_plot_container.x_data) == 0:
                await self.draw()
                continue

            self.diff_plot_container.update_lines()
            self.encoder_plot_container.update_lines()
            self.brake_pin_plot_container.update_lines()
            self.brake_current_plot_container.update_lines()

            self.encoder_plot.relim()
            self.encoder_plot.autoscale_view()

            self.diff_plot.relim()
            self.diff_plot.autoscale_view()

            self.brake_pin_value_plot.relim()
            self.brake_pin_value_plot.autoscale_view()

            self.brake_current_plot.relim()
            self.brake_current_plot.autoscale_view()

            await self.draw()

    async def get_encoder_data(self):
        message = None
        if not self.encoder_reader_bridge_queue.empty():
            while not self.encoder_reader_bridge_queue.empty():
                # message = await asyncio.wait_for(self.brake_controller_bridge_queue.get(), timeout=1)
                message = await self.encoder_reader_bridge_queue.get()
        else:
            return

        abs_encoder_1 = message.data[0] * math.pi / 180 * self.abs_gear_ratio
        abs_encoder_2 = message.data[1] * math.pi / 180 * self.abs_gear_ratio
        rel_encoder_1 = message.data[4] * self.rel_enc_ticks_to_rad
        rel_encoder_2 = message.data[5] * self.rel_enc_ticks_to_rad
        motor_encoder = message.data[6] * self.motor_enc_ticks_to_rad

        if self.initial_val_enc_1 is None:
            self.initial_val_enc_1 = abs_encoder_1

        if self.initial_val_enc_2 is None:
            self.initial_val_enc_2 = abs_encoder_2

        abs_enc1_angle = (abs_encoder_1 - self.initial_val_enc_1)
        abs_enc2_angle = (abs_encoder_2 - self.initial_val_enc_2)

        # enc1_angle = message.data[0] * self.gear_ratio
        # enc2_angle = message.data[1] * self.gear_ratio

        self.encoder_plot_container.append_x(message.timestamp)
        self.encoder_plot_container.append_y("abs enc 1", abs_enc1_angle)
        self.encoder_plot_container.append_y("abs enc 2", abs_enc2_angle)
        self.encoder_plot_container.append_y("rel enc 1", rel_encoder_1)
        self.encoder_plot_container.append_y("rel enc 2", rel_encoder_2)
        self.encoder_plot_container.append_y("motor", motor_encoder)

        self.diff_plot_container.append_x(message.timestamp)
        self.diff_plot_container.append_y("abs", abs_enc1_angle - abs_enc2_angle)
        self.diff_plot_container.append_y("rel", rel_encoder_1 - rel_encoder_2)
        self.diff_plot_container.append_y("motor", rel_encoder_2 - motor_encoder)

    async def get_brake_data(self):
        message = None
        if not self.brake_controller_bridge_queue.empty():
            while not self.brake_controller_bridge_queue.empty():
                message = await self.brake_controller_bridge_queue.get()
        else:
            return

        current_mA = message.data[2]
        pin_value = message.data[5]
        setpoint = message.data[6]

        self.brake_pin_plot_container.append_x(message.timestamp)
        self.brake_pin_plot_container.append_y("pin", pin_value)

        self.brake_current_plot_container.append_x(message.timestamp)
        self.brake_current_plot_container.append_y("current", current_mA)
        self.brake_current_plot_container.append_y("setpoint", setpoint)

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
