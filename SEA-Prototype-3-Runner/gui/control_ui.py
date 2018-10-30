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

        self.motor_speed_slider = Scale(self.root, label="Motor speed", from_=-255, to=255, resolution=1, orient=HORIZONTAL, length=self.width)
        self.brake_power_slider = Scale(self.root, label="Brake power", from_=0.0, to=400.0, resolution=1.0, orient=HORIZONTAL, length=self.width)

        self.set_motor_button = Button(self.root, text="Set motor", command=self.set_motor)
        self.stop_motor_button = Button(self.root, text="Stop motor", command=self.stop_motor)
        self.set_brake_button = Button(self.root, text="Set brake", command=self.set_brake)
        self.stop_brake_button = Button(self.root, text="Stop brake", command=self.stop_brake)

        self.motor_speed_slider.pack()
        self.set_motor_button.pack()
        self.stop_motor_button.pack()

        self.brake_power_slider.pack()
        self.set_brake_button.pack()
        self.stop_brake_button.pack()

        self.brake_controller_bridge_tag = "brake_controller_bridge"
        self.brake_controller_bridge_sub = self.define_subscription(
            self.brake_controller_bridge_tag,
            queue_size=None,
            required_attributes=("command_brake", "set_kp", "set_ki", "set_kd")
        )
        self.brake_controller_bridge = None

        self.pickle_file_path = pickle_file_path

        self.kp = 30.0
        self.ki = 30.0
        self.kd = 30.0

    def take(self):
        self.brake_controller_bridge = self.brake_controller_bridge_sub.get_producer()

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
        pass

    def set_brake(self):
        self.brake_controller_bridge.command_brake(self.brake_power_slider.get())

    def stop_motor(self):
        pass

    def stop_brake(self):
        self.brake_controller_bridge.command_brake(0)

    def shutdown_tk(self):
        self.is_running = False