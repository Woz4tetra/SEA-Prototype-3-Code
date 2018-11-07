from arduino_factory import DeviceFactory
from atlasbuggy import Orchestrator, run

from gui.data_plotter import DataPlotter
from gui.control_ui import TkinterGUI
from brake_controller_bridge import BrakeControllerBridge
from motor_controller_bridge import MotorControllerBridge
from encoder_reader_bridge import EncoderReaderBridge
from experiment_node import ExperimentNode


class ExperimentOrchestrator(Orchestrator):
    def __init__(self, event_loop):
        self.set_default(write=False)
        super(ExperimentOrchestrator, self).__init__(event_loop)

        # self.experiment = ExperimentNode(2.0, 50, 15.0, "brake_torque_data/B15 Torque Table.csv", enabled=True)
        self.experiment = ExperimentNode(2.0, 50, 15.0, "brake_torque_data/B5Z Torque Table.csv", enabled=True)
        self.plot = DataPlotter(enabled=True)
        self.ui = TkinterGUI("pickled/pid_constants.pkl")

        factory = DeviceFactory()
        self.motor = MotorControllerBridge(enabled=True)
        self.brake = BrakeControllerBridge(factory, enable_reporting=True)
        self.encoders = EncoderReaderBridge(factory, enable_reporting=True)

        # self.add_nodes()
        self.subscribe(self.brake, self.plot, self.plot.brake_controller_bridge_tag)
        self.subscribe(self.encoders, self.plot, self.plot.encoder_reader_bridge_tag)
        self.subscribe(self.brake, self.ui, self.ui.brake_controller_bridge_tag)
        self.subscribe(self.motor, self.ui, self.ui.motor_controller_bridge_tag)
        self.subscribe(self.experiment, self.ui, self.ui.experiment_tag)
        self.subscribe(self.brake, self.experiment, self.experiment.brake_controller_bridge_tag)
        self.subscribe(self.motor, self.experiment, self.experiment.motor_controller_bridge_tag)
        self.subscribe(self.encoders, self.experiment, self.experiment.encoder_reader_bridge_tag)

        factory.init()


def main():
    run(ExperimentOrchestrator)


main()
