#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_INA219.h>

class ParticleBrake
{
    public:
        ParticleBrake(Adafruit_INA219 *ina219, int current_control_pin);

        void reset();

        void set(double current_mA);
        double getShuntVoltage();
        double getBusVoltage();
        double getCurrent_mA();
        double getPower_mW();
        double getLoadVoltage();
        int getCurrentPinValue();
        double getSetPoint();

        void update();

        double Kp, Ki, Kd;
        bool pidEnabled;
        double response_unforced_msec, response_forced_msec;

    private:
        void setCurrentPin(int pwm_value);
        void clearVariables();

        int PARTICLE_BRAKE_CURRENT_CONTROL_PIN;

        int current_pin_value;
        double shuntvoltage, busvoltage, current_mA, power_mW, loadvoltage;

        Adafruit_INA219 *ina219;

        double pidSetPoint;
        double pidPrevError;
        double pidSumError;
        uint32_t prevPidTimer = 0;
        uint32_t pidDelay;  // microseconds
};
