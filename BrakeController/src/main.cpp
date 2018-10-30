#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_INA219.h>
#include <ParticleBrake.h>
#include "ArduinoFactoryBridge.h"

#define CURRENT_CONTROL_PIN 6

Adafruit_INA219 ina219;
ParticleBrake brake(&ina219, CURRENT_CONTROL_PIN);

ArduinoFactoryBridge bridge("brake_controller");

uint32_t prev_time;
uint32_t current_time;

double setpoint;
double read_pid_constant;

void setup(void)
{
    bridge.begin();

    bridge.writeHello();
    pinMode(CURRENT_CONTROL_PIN, OUTPUT);
    analogWrite(CURRENT_CONTROL_PIN, 0);

    // Initialize the INA219.
    // By default the initialization will use the largest range (32V, 2A).  However
    // you can call a setCalibration function to change this range (see comments).
    ina219.begin();
    // To use a slightly lower 32V, 1A range (higher precision on amps):
    ina219.setCalibration_32V_1A();
    // Or to use a lower 16V, 400mA range (higher precision on volts and amps):
    // ina219.setCalibration_16V_400mA();

    brake.Kp = 30.0;
    brake.Ki = 0.0;
    brake.Kd = 0.0;

    prev_time = millis();

    bridge.setInitData("fff", brake.Kp, brake.Ki, brake.Kd);
    bridge.writeReady();
}

void loop(void)
{
    if (!bridge.isPaused()) {
        brake.update();
        current_time = millis();
        if ((current_time - prev_time) > 100) {
            prev_time = current_time;
            bridge.write("brake", "fffffdf",
                brake.getShuntVoltage(),
                brake.getBusVoltage(),
                brake.getCurrent_mA(),
                brake.getPower_mW(),
                brake.getLoadVoltage(),
                brake.getCurrentPinValue(),
                brake.getSetPoint()
            );
        }
    }

    if (bridge.available()) {
        int status = bridge.read();
        String command = bridge.getCommand();
        switch (status) {
            case 0:  // command
                switch (command.charAt(0)) {
                    case 'b':
                        setpoint = command.substring(1).toDouble();
                        brake.set(setpoint);
                        break;

                    case 'k':
                        read_pid_constant = command.substring(2).toDouble();
                        switch (command.charAt(1)) {
                            case 'p': brake.Kp = read_pid_constant; break;
                            case 'i': brake.Ki = read_pid_constant; break;
                            case 'd': brake.Kd = read_pid_constant; break;
                        }
                }
                break;
            case 1:  // start
                brake.reset();
                break;
            case 2:  // stop
                brake.reset();
                break;
        }
    }
}
