from arduino_factory import DeviceFactory
from atlasbuggy import Orchestrator, run

from gui.data_plotter import DataPlotter
from gui.control_ui import TkinterGUI
from brake_controller_bridge import BrakeControllerBridge
from motor_controller_bridge import MotorControllerBridge
from encoder_reader_bridge import EncoderReaderBridge


class ExperimentOrchestrator(Orchestrator):
    def __init__(self, event_loop):
        super(ExperimentOrchestrator, self).__init__(event_loop)

        factory = DeviceFactory()
        self.plot = DataPlotter(enabled=True)
        self.ui = TkinterGUI("pickled/pid_constants.pkl")
        self.brake = BrakeControllerBridge(factory)
        self.motor = MotorControllerBridge(enabled=False)
        self.encoders = EncoderReaderBridge(factory)

        # self.add_nodes(self.bridge)
        self.subscribe(self.brake, self.plot, self.plot.brake_controller_bridge_tag)
        self.subscribe(self.encoders, self.plot, self.plot.encoder_reader_bridge_tag)
        self.subscribe(self.brake, self.ui, self.ui.brake_controller_bridge_tag)
        self.subscribe(self.motor, self.ui, self.ui.motor_controller_bridge_tag)


def main():
    run(ExperimentOrchestrator)


main()
