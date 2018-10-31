import csv
import numpy as np

ozin_to_nm = 0.0070615518333333
lbin_to_nm = 0.11298482933333

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

if __name__ == '__main__':
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

    test()
