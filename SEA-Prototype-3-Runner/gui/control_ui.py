import os
import pickle
import asyncio
from tkinter import *
from atlasbuggy import Node

import matplotlib
matplotlib.use("TkAgg")  # keeps tkinter happy


class TkinterGUI(Node):
    def __init__(self, pickle_file_path):
        super(TkinterGUI, self).__init__()
        self.interval = 1 / 30

        self.root = Tk()
        self.width = 440
        self.height = 800
        self.root.geometry('%sx%s' % (self.width, self.height))
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown_tk)

        self.is_running = True

        self.motor_speed_slider = Scale(self.root, label="Motor speed", from_=-3200, to=3200, resolution=1, orient=HORIZONTAL, length=self.width)
        self.brake_power_slider = Scale(self.root, label="Brake power", from_=0.0, to=400.0, resolution=1.0, orient=HORIZONTAL, length=self.width)

        self.set_motor_button = Button(self.root, text="Set motor", command=self.set_motor)
        self.stop_motor_button = Button(self.root, text="Stop motor", command=self.stop_motor)
        self.set_brake_button = Button(self.root, text="Set brake", command=self.set_brake)
        self.stop_brake_button = Button(self.root, text="Stop brake", command=self.stop_brake)

        self.experiment_toggle_button_states = ["Start experiment", "Stop experiment"]
        self.is_experiment_started = False
        self.experiment_toggle_button = Button(
            self.root, text=self.experiment_toggle_button_states[0],
            command=self.toggle_experiment
        )
        self.take_sample_slider = Scale(self.root, label="Sample length (s)", from_=0.0, to=30.0, resolution=1.0, orient=HORIZONTAL, length=self.width)
        self.take_sample_button = Button(self.root, text="take sample", command=self.take_sample)

        self.motor_speed_slider.pack()
        self.set_motor_button.pack()
        self.stop_motor_button.pack()

        self.brake_power_slider.pack()
        self.set_brake_button.pack()
        self.stop_brake_button.pack()

        self.experiment_toggle_button.pack()

        self.take_sample_slider.pack()
        self.take_sample_button.pack()

        self.brake_controller_bridge_tag = "brake_controller_bridge"
        self.brake_controller_bridge_sub = self.define_subscription(
            self.brake_controller_bridge_tag,
            queue_size=None,
            required_methods=("command_brake", "set_kp", "set_ki", "set_kd")
        )
        self.brake_controller_bridge = None

        self.motor_controller_bridge_tag = "motor_controller_bridge"
        self.motor_controller_bridge_sub = self.define_subscription(
            self.motor_controller_bridge_tag,
            queue_size=None,
            required_methods=("set_speed",)
        )
        self.motor_controller_bridge = None

        self.experiment_tag = "experiment"
        self.experiment_sub = self.define_subscription(
            self.experiment_tag,
            queue_size=None,
            required_methods=("run_experiment", "cancel_experiment", "take_sample")
        )
        self.experiment = None

        self.pickle_file_path = pickle_file_path

        self.kp = 30.0
        self.ki = 0.0
        self.kd = 0.0

    def take(self):
        self.brake_controller_bridge = self.brake_controller_bridge_sub.get_producer()
        self.motor_controller_bridge = self.motor_controller_bridge_sub.get_producer()
        self.experiment = self.experiment_sub.get_producer()

    def load_constants(self):
        if os.path.isfile(self.pickle_file_path):
            self.kp, self.ki, self.kd = pickle.load(open(self.pickle_file_path, "rb"))

            # self.kd_slider.set(self.kd)

            print("loaded constants:", self.kp, self.ki, self.kd)

    def save_constants(self):
        pickle.dump((self.kp, self.ki, self.kd), open(self.pickle_file_path, "wb"))

        print("saving constants:", self.kp, self.ki, self.kd)

    async def loop(self):
        try:
            while self.is_running:
                self.root.update()

                await asyncio.sleep(self.interval)
        except TclError as e:
            if "application has been destroyed" not in e.args[0]:
                raise

    async def teardown(self):
        self.save_constants()

    def set_motor(self):
        if self.is_subscribed(self.motor_controller_bridge_tag):
            self.motor_controller_bridge.set_speed(self.motor_speed_slider.get())

    def set_brake(self):
        self.brake_controller_bridge.command_brake(self.brake_power_slider.get())

    def stop_motor(self):
        if self.is_subscribed(self.motor_controller_bridge_tag):
            self.motor_controller_bridge.set_speed(0)

    def stop_brake(self):
        self.brake_controller_bridge.command_brake(0)

    def toggle_experiment(self):
        if self.is_experiment_started:
            new_button_text = self.experiment_toggle_button_states[0]
            self.experiment.cancel_experiment()
        else:
            new_button_text = self.experiment_toggle_button_states[1]
            self.experiment.run_experiment()

        self.is_experiment_started = not self.is_experiment_started

        self.experiment_toggle_button["text"] = new_button_text

    def take_sample(self):
        self.experiment.take_sample(self.take_sample_slider.get())

    def shutdown_tk(self):
        self.is_running = False
