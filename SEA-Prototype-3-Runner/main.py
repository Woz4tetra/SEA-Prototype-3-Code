from atlasbuggy import Orchestrator, run

from gui.data_plotter import DataPlotter
from gui.control_ui import TkinterGUI
from brake_controller_bridge import BrakeControllerBridge
from motor_controller_bridge import MotorControllerBridge


class ExperimentOrchestrator(Orchestrator):
    def __init__(self, event_loop):
        super(ExperimentOrchestrator, self).__init__(event_loop)

        self.bridge = BrakeControllerBridge()
        self.plot = DataPlotter(enabled=True)
        self.ui = TkinterGUI("pickled/pid_constants.pkl")
        self.motor = MotorControllerBridge()

        # self.add_nodes(self.bridge)
        self.subscribe(self.bridge, self.plot, self.plot.brake_controller_bridge_tag)
        self.subscribe(self.bridge, self.ui, self.ui.brake_controller_bridge_tag)
        self.subscribe(self.motor, self.ui, self.ui.motor_controller_bridge_tag)


def main():
    run(ExperimentOrchestrator)


main()
