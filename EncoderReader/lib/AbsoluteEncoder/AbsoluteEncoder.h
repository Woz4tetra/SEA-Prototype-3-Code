#include <Arduino.h>

class AbsoluteEncoder
{
#define ENCODER_MIN_VAL 3  // min voltage: 0.015 / 5.0 * 1024 = 3
#define ENCODER_MAX_VAL 1021  // max voltage: 4.987 / 5.0 * 1024 = 1021
#define ENCODER_CROSSOVER_THRESHOLD 500
private:
    int analog_pin;
    int prev_enc_val;
    int curr_enc_val;
    double encoder_angle;
    int32_t rotations;
    bool is_reversed;
    int encoder_min_val, encoder_max_val;

    void read_into_curr_val()
    {
        // TODO: find out why analogRead glitches and gives a random value sometimes (noise on the voltage bus?)
        if (is_reversed) {
            curr_enc_val = 1024 - analogRead(analog_pin);
        }
        else {
            curr_enc_val = analogRead(analog_pin);
        }

        if (curr_enc_val > encoder_max_val) {
            curr_enc_val = encoder_max_val;
        }
        if (curr_enc_val < encoder_min_val) {
            curr_enc_val = encoder_min_val;
        }
    }
public:
    AbsoluteEncoder(int analog_pin, bool is_reversed = false, int encoder_min_val = ENCODER_MIN_VAL, int encoder_max_val = ENCODER_MAX_VAL) {
        this->analog_pin = analog_pin;
        this->is_reversed = is_reversed;
        this->encoder_min_val = encoder_min_val;
        this->encoder_max_val = encoder_max_val;

        reset();
    };

    void reset() {
        encoder_angle = 0.0;
        prev_enc_val = -1;
        curr_enc_val = -1;
        rotations = 0;
    }

    void begin() {
        pinMode(analog_pin, INPUT);
        read_into_curr_val();
        prev_enc_val = curr_enc_val;
    }

    void read()
    {
        prev_enc_val = curr_enc_val;
        read_into_curr_val();

        encoder_angle = 360.0 * (curr_enc_val - encoder_min_val) / (encoder_max_val - encoder_min_val);
        if (curr_enc_val - prev_enc_val > ENCODER_CROSSOVER_THRESHOLD) {
            rotations--;
        }
        if (prev_enc_val - curr_enc_val > ENCODER_CROSSOVER_THRESHOLD) {
            rotations++;
        }
        // encoder_angle = fmod(encoder_angle, 360.0);
    };

    double getAngle() {
        return encoder_angle;
    };

    double getFullAngle() {
        return rotations * 360.0 + encoder_angle;
    };

    int32_t getRotations() {
        return rotations;
    };

    int getAnalogValue() {
        return curr_enc_val;
    }
};
