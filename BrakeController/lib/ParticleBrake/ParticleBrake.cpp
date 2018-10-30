#include <ParticleBrake.h>

ParticleBrake::ParticleBrake(Adafruit_INA219 *ina219, int current_control_pin)
{
    Kp = 1.0;
    Ki = 0.0;
    Kd = 0.0;

    response_unforced_msec = 25.0;
    response_forced_msec = 14.0;

    pidDelay = 500;

    PARTICLE_BRAKE_CURRENT_CONTROL_PIN = current_control_pin;
    this->ina219 = ina219;

    clearVariables();
}

void ParticleBrake::reset() {
    setCurrentPin(0);
    delay(response_unforced_msec);  // wait for brake to shutdown
    clearVariables();
}

void ParticleBrake::set(double current_mA) {
    pidEnabled = true;
    pidSetPoint = current_mA;
}

void ParticleBrake::update() {
    if (!pidEnabled) {
        return;
    }

    uint32_t current_time = micros();
    if (prevPidTimer > current_time) {  // if timer loops, reset timer
        prevPidTimer = current_time;
        return;
    }

    if ((current_time - prevPidTimer) < pidDelay) {
        return;
    }

    double dt = (double)(current_time - prevPidTimer) / 1E6;
    double error = pidSetPoint - getCurrent_mA();
    double d_error = (error - pidPrevError) / dt;
    double i_error = pidSumError * dt;

    int output = (int)(Kp * error + Ki * i_error + Kd * d_error);

    pidPrevError = error;
    pidSumError += error;
    prevPidTimer = micros();

    setCurrentPin(output);
}

void ParticleBrake::clearVariables() {
    shuntvoltage = 0.0;
    busvoltage = 0.0;
    current_mA = 0.0;
    loadvoltage = 0.0;
    power_mW = 0.0;

    current_pin_value = 0;

    pidEnabled = false;
    pidSetPoint = 0.0;
    pidPrevError = 0.0;
    pidSumError = 0.0;
    prevPidTimer = micros();
}

void ParticleBrake::setCurrentPin(int pwm_value)
{
    if (pwm_value > 255) {
        pwm_value = 255;
    }
    if (pwm_value < 0) {
        pwm_value = 0;
    }
    current_pin_value = pwm_value;
    analogWrite(PARTICLE_BRAKE_CURRENT_CONTROL_PIN, current_pin_value);
}


double ParticleBrake::getShuntVoltage() {
    shuntvoltage = ina219->getShuntVoltage_mV();
    return shuntvoltage;
}

double ParticleBrake::getBusVoltage() {
    busvoltage = ina219->getBusVoltage_V();
    return busvoltage;
}

double ParticleBrake::getCurrent_mA() {
    current_mA = ina219->getCurrent_mA();
    return current_mA;
}

double ParticleBrake::getPower_mW() {
    power_mW = ina219->getPower_mW();
    return power_mW;
}

double ParticleBrake::getLoadVoltage() {
    loadvoltage = busvoltage + (shuntvoltage / 1000);
    return loadvoltage;
}

int ParticleBrake::getCurrentPinValue() {
    return current_pin_value;
}

double ParticleBrake::getSetPoint() {
    return pidSetPoint;
}
