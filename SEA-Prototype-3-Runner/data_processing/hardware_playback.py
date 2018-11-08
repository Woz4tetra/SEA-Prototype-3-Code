import asyncio
from arduino_factory import packet
from atlasbuggy.log.playback import PlaybackNode


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

