#include <Encoder.h>
#include <ArduinoFactoryBridge.h>

#include "AbsoluteEncoder.h"

#define ENCODER_1_PIN_A 2
#define ENCODER_1_PIN_B 3
#define ENCODER_2_PIN_A 4
#define ENCODER_2_PIN_B 5

#define MOTOR_ENCODER_PIN_A 6
#define MOTOR_ENCODER_PIN_B 7

#define ABS_ENCODER_1_PIN A13
#define ABS_ENCODER_3_PIN A12

Encoder enc1(ENCODER_1_PIN_A, ENCODER_1_PIN_B);
Encoder enc2(ENCODER_2_PIN_A, ENCODER_2_PIN_B);
Encoder motor_enc(MOTOR_ENCODER_PIN_A, MOTOR_ENCODER_PIN_B);

ArduinoFactoryBridge bridge("encoder_reader");

AbsoluteEncoder abs_enc1(ABS_ENCODER_1_PIN);
AbsoluteEncoder abs_enc2(ABS_ENCODER_3_PIN);

uint32_t prev_time;
uint32_t current_time;

void setup()
{
    bridge.begin();
    bridge.writeHello();

    abs_enc1.begin();
    abs_enc2.begin();

    enc1.read();
    enc2.read();
    motor_enc.read();
    bridge.setInitData("ff", abs_enc1.getAngle(), abs_enc2.getAngle());

    bridge.writeReady();
}

void loop()
{
    if (!bridge.isPaused()) {
        abs_enc1.read();
        abs_enc2.read();

        long enc1_pos = enc1.read();
        long enc2_pos = enc2.read();
        long motor_enc_pos = motor_enc.read();

        current_time = millis();
        if ((current_time - prev_time) > 10) {
            prev_time = current_time;
            bridge.write("enc", "ffddddd",
                abs_enc1.getFullAngle(), abs_enc2.getFullAngle(), abs_enc1.getAnalogValue(), abs_enc2.getAnalogValue(),
                enc1_pos, enc2_pos, motor_enc_pos
            );
        }
    }

    if (bridge.available()) {
        int status = bridge.read();
        String command = bridge.getCommand();
        switch (status) {
            // case 0:  // command
            case 1:  // start
                enc1.write(0);
                enc2.write(0);
                motor_enc.write(0);
                abs_enc1.reset();
                abs_enc2.reset();
            case 2:  // stop
                break;
        }

    }
}
