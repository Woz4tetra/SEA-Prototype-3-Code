import numpy as np
from .k_calculator_helpers import default_rel_enc_ticks_to_rad


def single_weight_test(measurement_on_ruler_cm, actual_displacement, predicted_K, weight_used=True):
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

    net_moment = g * (
            m_ruler_mount_kg * ruler_mount_center_of_mass_m +
            m_ruler_kg * ruler_center_of_mass_m
    )
    if weight_used:
        net_moment += (m_weight_mount_kg + m_weight_kg) * lever_arm_m * g

    predicted_displacement = net_moment / predicted_K
    error = actual_displacement - predicted_displacement

    print("Results:")
    print("\tnet moment: %sNm" % net_moment)
    print("\tpredicted displacement: %srad" % predicted_displacement)
    print("\tactual displacement: %srad" % actual_displacement)
    print("\tdisplacement error: %srad" % error)
    print("\tmoment error: %srad" % error)
    if weight_used:
        print("\tlever arm: %sm\n" % lever_arm_m)
    else:
        print()

    return net_moment, actual_displacement, error


def average_sample(encoder_1_ticks, encoder_2_ticks):
    encoder_1_ticks = np.array(encoder_1_ticks)
    encoder_2_ticks = np.array(encoder_2_ticks)
    encoder_delta = encoder_1_ticks - encoder_2_ticks
    encoder_delta_rad_avg = np.mean(encoder_delta) * default_rel_enc_ticks_to_rad

    return encoder_delta_rad_avg
