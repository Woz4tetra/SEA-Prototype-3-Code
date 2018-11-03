import csv
import math
import peakutils
import numpy as np

ozin_to_nm = 0.0070615518333333
lbin_to_nm = 0.11298482933333
default_rel_enc_ticks_to_rad = 2 * math.pi / 2000
default_motor_enc_ticks_to_rad = 2 * math.pi / (131.25 * 64)
default_abs_gear_ratio = 48.0/32.0


class TorqueTable:
    def __init__(self, torque_table_path, voltage_variant=12):
        with open(torque_table_path) as csv_file:
            reader = csv.reader(csv_file)

            header = next(reader)

            self.conversion = self.select_units(header)
            self.voltage_variant = voltage_variant
            self.selected_current_column = self.select_voltage_variant(header, voltage_variant)

            self.forcing_torque = []
            self.unforcing_torque = []
            self.forcing_current = []
            self.unforcing_current = []

            self.max_torque = 0.0

            apply_to_forcing = False
            for row in reader:
                forcing_direction = row[0]
                if forcing_direction == "Forcing":
                    apply_to_forcing = True
                elif forcing_direction == "Unforcing":
                    apply_to_forcing = False

                torque_nm = float(row[1]) * self.conversion
                current_mA = float(row[self.selected_current_column])

                if apply_to_forcing:
                    self.forcing_torque.append(torque_nm)
                    self.forcing_current.append(current_mA)
                else:
                    self.unforcing_torque.append(torque_nm)
                    self.unforcing_current.append(current_mA)

                if torque_nm > self.max_torque:
                    self.max_torque = torque_nm

            # flip direction to make np.interp work
            self.unforcing_torque = self.unforcing_torque[::-1]
            self.unforcing_current = self.unforcing_current[::-1]


    def to_current_mA(self, is_forcing, torque):
        if is_forcing:
            return np.interp(torque, self.forcing_torque, self.forcing_current)
        else:
            return np.interp(torque, self.unforcing_torque, self.unforcing_current)

    def to_torque(self, is_forcing, current_mA):
        if is_forcing:
            return np.interp(current_mA, self.forcing_current, self.forcing_torque)
        else:
            return np.interp(current_mA, self.unforcing_current, self.unforcing_torque)

    def select_units(self, header):
        if header[1].find("oz-in") > -1:
            conversion = ozin_to_nm
        elif header[1].find("lb-in") > -1:
            conversion = lbin_to_nm
        else:
            raise ValueError("Unknown units encountered in csv table: '%s'. Not 'oz-in' or 'lb-in'" % header[1])

        return conversion

    def select_voltage_variant(self, header, voltage_variant):
        for index, cell in enumerate(header):
            if cell.find(str(voltage_variant)) > -1:
                return index
        raise ValueError("Couldn't find requested voltage variant in the torque table:\n\t'%s'" % header)


def get_key_transistions(brake_timestamps, brake_current, motor_direction_switch_time):
    brake_ramp_transitions = peakutils.indexes(brake_current, thres=0.9, min_dist=500)
    motor_direction_switch_brake_index = (np.abs(brake_timestamps - motor_direction_switch_time)).argmin()
    assert len(brake_ramp_transitions) == 2, len(brake_ramp_transitions)
    assert motor_direction_switch_brake_index > brake_ramp_transitions[0], motor_direction_switch_brake_index

    return brake_ramp_transitions, motor_direction_switch_brake_index


def interpolate_encoder_values(encoder_timestamps, encoder_1_ticks, encoder_2_ticks, rel_enc_ticks_to_rad, brake_timestamps):
    encoder_delta = (encoder_1_ticks - encoder_2_ticks) * rel_enc_ticks_to_rad
    encoder_interp_delta = []

    interp_enc_index = 0
    for brake_t in brake_timestamps:
        # Encoder samples ~5 times faster than the brake's current feedback. Interpolate encoder values to brake timestamps
        while encoder_timestamps[interp_enc_index] < brake_t:
            interp_enc_index += 1
            if interp_enc_index >= len(encoder_timestamps):
                interp_enc_index -= 1
                break
        enc_index = interp_enc_index

        encoder_interp_delta.append(encoder_delta[enc_index])

    return encoder_interp_delta


def compute_linear_regression(encoder_interp_delta, brake_torque_nm):
    polynomial = np.polyfit(encoder_interp_delta, brake_torque_nm, 1)
    linear_regression_fn = np.poly1d(polynomial)
    encoder_lin_reg = linear_regression_fn(encoder_interp_delta)
    return encoder_lin_reg, polynomial


def compute_k(torque_table,
        encoder_timestamps, encoder_1_ticks, encoder_2_ticks,
        brake_timestamps, brake_current,
        motor_direction_switch_time):
    rel_enc_ticks_to_rad = default_rel_enc_ticks_to_rad

    encoder_timestamps = np.array(encoder_timestamps)
    encoder_1_ticks = np.array(encoder_1_ticks)
    encoder_2_ticks = np.array(encoder_2_ticks)
    brake_timestamps = np.array(brake_timestamps)
    brake_current = np.array(brake_current)

    brake_ramp_transitions, motor_direction_switch_brake_index = get_key_transistions(brake_timestamps, brake_current, motor_direction_switch_time)
    encoder_interp_delta = interpolate_encoder_values(encoder_timestamps, encoder_1_ticks, encoder_2_ticks, rel_enc_ticks_to_rad, brake_timestamps)

    # convert sensed current to torque (Nm)
    brake_current_forcing_forward = brake_current[0:brake_ramp_transitions[0]]
    brake_current_unforcing_forward = brake_current[brake_ramp_transitions[0]:motor_direction_switch_brake_index]
    brake_current_forcing_backward = brake_current[motor_direction_switch_brake_index:brake_ramp_transitions[1]]
    brake_current_unforcing_backward = brake_current[brake_ramp_transitions[1]:]

    btff = torque_table.to_torque(True, brake_current_forcing_forward)
    btuf = torque_table.to_torque(False, brake_current_unforcing_forward)
    btfb = -torque_table.to_torque(True, brake_current_forcing_backward)
    btub = -torque_table.to_torque(False, brake_current_unforcing_backward)
    brake_torque_nm = np.concatenate((btff, btuf, btfb, btub))

    encoder_lin_reg, polynomial = compute_linear_regression(encoder_interp_delta, brake_torque_nm)

    return (encoder_timestamps, encoder_delta, encoder_interp_delta, encoder_lin_reg,
        brake_timestamps, brake_current, brake_ramp_transitions, brake_torque_nm, polynomial)


def single_weight_test(measurement_on_ruler_cm, actual_displacement, weight_used=True):
    m_ruler_mount_kg = 0.066
    m_ruler_kg = 0.06
    m_weight_kg = 1.0
    m_weight_mount_kg = 0.114

    ruler_mount_center_of_mass_m = 0.015
    ruler_length_cm = 30.0
    offset_from_axle_cm = 2.028
    ruler_center_of_mass_m = (offset_from_axle_cm + ruler_length_cm / 2) / 100
    lever_arm_m = (ruler_length_cm + offset_from_axle_cm - measurement_on_ruler_cm) / 100.0

    g = 9.81
    K = 2.9887

    net_moment = g * (
        m_ruler_mount_kg * ruler_mount_center_of_mass_m +
        m_ruler_kg * ruler_center_of_mass_m
    )
    if weight_used:
        net_moment += (m_weight_mount_kg + m_weight_kg) * lever_arm_m * g

    predicted_displacement = net_moment / K
    error = actual_displacement - predicted_displacement
    print("Results:")
    print("\tnet moment: %sNm" % net_moment)
    print("\tpredicted displacement: %srad" % predicted_displacement)
    print("\tactual displacement: %srad" % actual_displacement)
    print("\tdisplacement error: %srad" % error)
    if weight_used:
        print("\tlever arm: %sm\n" % lever_arm_m)
    else:
        print()

    return net_moment, actual_displacement, error

if __name__ == '__main__':
    def run_single_weight_tests():
        import matplotlib.pyplot as plt
        moments = []
        errors = []
        actual_displacements = []
        for net_moment, actual_displacement, error in [
                single_weight_test(18.0, 0.41783182292744253),
                single_weight_test(19.0, 0.38515925933010864),
                single_weight_test(22.0, 0.2984513020910304),
                single_weight_test(0.0, 0.025132741228718346, False)
                ]:
            moments.append(net_moment)
            actual_displacements.append(actual_displacement)
            errors.append(error)

        displacement_lin_reg, polynomial = compute_linear_regression(actual_displacements, moments)

        # plt.figure(1)
        # plt.plot(errors, moments, 'x')
        # plt.figure(2)
        plt.plot(actual_displacements, moments, 'x')
        plt.plot(actual_displacements, displacement_lin_reg, label='m=%0.4fNm/rad, b=%0.4fNm' % (polynomial[0], polynomial[1]))

        plt.legend()
        plt.show()

    run_single_weight_tests()

    def test():
        table = TorqueTable("brake_torque_data/B15 Torque Table.csv")
        result1 = table.to_current_mA(True, 0.1125 * lbin_to_nm)
        assert abs(result1 - 30.75) < 0.00001, result1
        print(result1)

        result2 = table.to_current_mA(True, 0.05 * lbin_to_nm)
        assert abs(result2 - 20.5) < 0.00001, result2
        print(result2)

        result3 = table.to_torque(True, result1)
        assert abs(result3 - 0.1125 * lbin_to_nm) < 0.00001, result3 / lbin_to_nm
        print(result3 / lbin_to_nm)

        result4 = table.to_torque(True, result2)
        assert abs(result4 - 0.05 * lbin_to_nm) < 0.00001, result4 / lbin_to_nm
        print(result4 / lbin_to_nm)

        result5 = table.to_current_mA(False, 3.1 * lbin_to_nm)
        assert abs(result5 - 123) < 0.00001, result5
        print(result5)

        result6 = table.to_current_mA(False, 2.73 * lbin_to_nm)
        assert abs(result6 - 112.75) < 0.00001, result6
        print(result6)

        result7 = table.to_torque(False, result5)
        assert abs(result7 - 3.1 * lbin_to_nm) < 0.00001, result7 / lbin_to_nm
        print(result7 / lbin_to_nm)

        result8 = table.to_torque(False, result6)
        assert abs(result8 - 2.73 * lbin_to_nm) < 0.00001, result8 / lbin_to_nm
        print(result8 / lbin_to_nm)

    # test()
