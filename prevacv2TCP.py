import socket
import struct
import os
import platform
import subprocess
import uuid

# Wrapper class for interacting with the device using the Prevac protocol
class prevacV2TCP:
    def __init__(self, ip_address: str, port: int = 502, device_address: int = 0xC8):
        self.ip_address = ip_address
        self.port = port
        self.sock = None
        self.device_address = device_address
        self.host_address = 0x01  # Default host address, this will be updated after registration

    def connect(self):
        """
        Create and open a TCP socket connection to the Modbus server.
        """
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(2.0)
            self.sock.connect((self.ip_address, self.port))
            print(f"Connected to {self.ip_address}:{self.port}")
            return True
        except socket.timeout:
            raise TimeoutError(f"Connection to {self.ip_address}:{self.port} timed out")
            self.sock = None
            return False
        except socket.error as e:
            raise ConnectionError(f"Failed to connect to {self.ip_address}:{self.port}: {e}")
            self.sock = None
            return False

    def close(self):
        """Close the TCP connection."""
        if self.sock:
            self.sock.close()
            self.sock = None
            print(f"Disconnected from {self.ip_address}:{self.port}")

    def get_mac_address(self):
        # Get the MAC address using uuid library
        mac_addr = hex(uuid.getnode())[2:].upper()
        mac_addr = ':'.join(mac_addr[i:i+2] for i in range(0, 12, 2))
        return mac_addr

    def get_uuid(self):
        os_type = platform.system()

        if os_type == "Windows":
            # On Windows, get the BIOS serial number using WMIC
            try:
                output = subprocess.check_output("wmic bios get serialnumber", shell=True)
                uuid_str = output.decode().split("\n")[1].strip()
                if uuid_str and uuid_str != "To be filled by O.E.M.":
                    return uuid_str
            except Exception as e:
                print(f"Error retrieving UUID on Windows: {e}")
        
        elif os_type == "Linux":
            # On Linux, read the product_uuid file
            try:
                with open("/sys/class/dmi/id/product_uuid", "r") as file:
                    uuid_str = file.read().strip()
                    if uuid_str:
                        return uuid_str
            except FileNotFoundError:
                print("Error: /sys/class/dmi/id/product_uuid not found. Run as root?")
            except Exception as e:
                print(f"Error retrieving UUID on Linux: {e}")
        
        elif os_type == "Darwin":  # macOS
            # On macOS, get the hardware UUID using system_profiler
            try:
                output = subprocess.check_output(["system_profiler", "SPHardwareDataType"])
                for line in output.decode().split("\n"):
                    if "Hardware UUID" in line:
                        uuid_str = line.split(":")[1].strip()
                        if uuid_str:
                            return uuid_str
            except Exception as e:
                print(f"Error retrieving UUID on macOS: {e}")
        
        # If UUID can't be retrieved, fallback to the MAC address
        mac_addr = get_mac_address()
        if mac_addr:
            return mac_addr

        # If both UUID and MAC address are unavailable, fallback to a Python-generated UUID
        return str(uuid.uuid1())

	# Function to build the data frame
    def build_data_frame(self, function_code: int, data: bytes) -> bytes:
        header = 0xBB
        data_length = len(data)

        # Build frame without CRC
        frame = bytearray([header, data_length, self.device_address, self.host_address])
        frame.extend(function_code.to_bytes(2, 'big'))  # MSB and LSB of function code
        frame.extend(data)

        # Calculate and append CRC
        crc = self.calculate_crc(frame[1:])  # CRC without header byte
        frame.append(crc)

        return bytes(frame)

    def calculate_crc(self, data: bytes) -> int:
        crc = 0
        for byte in data:
            crc = (crc + byte) % 256
        return crc

	# TCP communication function
    def tcp_send_command(self, function_code: int, data: bytes = b''):
        """
        Send the request to the Modbus server and receive the response.
        """
        if self.sock is None:
            raise ConnectionError("Socket is not connected. Call connect() first.")

        try:
            request = self.build_data_frame(function_code, data)
            #print(f"Send: {request.hex()}")
            self.sock.sendall(request)
            response = self.sock.recv(1024)  # Buffer size is 1024 bytes
            #print(f"Received response: {response.hex()}")
            return self.extract_data_from_response(response)
        except socket.timeout:
            raise TimeoutError("Receiving data timed out")
            return None
        except socket.error as e:
            raise ConnectionError(f"Error receiving data: {e}")
            return None

    # Function to extract data from the response
    def extract_data_from_response(self, response: bytes):
        #if len(response) < 6:
        #    print("Invalid response: too short.")
        #    return None
        #print(f"Full response in hex: {response.hex()}")  # Print the full response in hexadecimal

        # Extract fields from the response
        header = response[0]
        data_length = response[1]
        device_address = response[2]
        host_address = response[3]
        function_code = int.from_bytes(response[4:6], 'big')
        data = response[6:-1]  # All data excluding CRC
        crc_received = response[-1]
        #print(f"Data: {data.hex()}")  # Print the full response in hexadecimal

        # Validate CRC (ignoring header byte)
        #calculated_crc = calculate_crc(response[1:-1])
        #if crc_received != calculated_crc:
        #    print(f"CRC error: expected {calculated_crc}, received {crc_received}")
        #    return None

        # Check for errors (last byte is 0x00 for success, other values indicate errors)
        #if response[-1] != 0x00:
        #    error_code = response[-1]
        #    print(f"Error code received: {hex(error_code)}")
        #    print(f"Full response in hex: {response.hex()}")  # Print the full response in hexadecimal
        #    return None

        # Handle successful response and extract meaningful data (based on the function code)
        return data

    # Convert ASCII to bytes
    def ascii_to_bytes(self, value: str) -> bytes:
        return value.encode('ascii')

    # Convert bytes to ASCII
    def bytes_to_ascii(self, data: bytes) -> str:
        return data.decode('ascii')

    # Convert int (1-byte integer) to byte (big-endian)
    def int_to_byte(self, value: int) -> bytes:
        return value.to_bytes(1, 'big')  # 1 byte, big-endian
        
    # Convert bytes  to a 1-byte integer (big-endian)
    def byte_to_int(self, data: bytes) -> int:
        return int.from_bytes(data, 'big')

    # Convert long (4-byte integer) to bytes (big-endian)
    def long_to_bytes(self, value: int) -> bytes:
        return value.to_bytes(4, 'big')

    # Convert bytes to long (4-byte integer) (big-endian)
    def bytes_to_long(self, data: bytes) -> int:
        return int.from_bytes(data, 'big')

    # Convert double (8 bytes) to bytes (big-endian)
    def double_to_bytes(self, value: float) -> bytes:
        return struct.pack('>d', value)

    # Convert bytes to double (8 bytes, big-endian)
    def bytes_to_double(self, data: bytes) -> float:
        return struct.unpack('>d', data)[0]

    ### Host registration ###

    # 0x7FF0: Host number assign
    def register_new_host(self):
        function_code = 0x7FF0
        uuid_str = self.get_uuid()  # Get the UUID of the client system
        data = uuid_str.encode('ascii')  # Convert UUID to bytes
        message = self.tcp_send_command(function_code, data)
        self.host_address = self.byte_to_int(message)
        return self.host_address

    # 0x7FF1: Master mode
    def master_mode(self, remote: bool, rw : int = 1):
        function_code = 0x7FF1
        if rw == 1:
            function_code = function_code| 0x8000
            data = bytes([1 if remote else 0])
            return self.tcp_send_command(function_code,data)
        else:
            return self.tcp_send_command(function_code)

    ### Global Orders ###

    # 0x7F01: Read product number
    def r_product_number(self):
        function_code = 0x7F01
        message = self.tcp_send_command(function_code)
        return self.bytes_to_ascii(message)

    # 0x7F02: Read serial number
    def r_serial_number(self):
        function_code = 0x7F02
        message = self.tcp_send_command(function_code)
        return self.bytes_to_ascii(message)

    # 0x7F03: Read device version
    def r_device_version(self):
        function_code = 0x7F03
        message = self.tcp_send_command(function_code)
        return self.bytes_to_ascii(message)

    # 0x7F04: Read hash code version
    def r_hash_code_version(self):
        function_code = 0x7F04
        message = self.tcp_send_command(function_code)
        return self.bytes_to_ascii(message)

    # 0x7F05: Read device name
    def r_device_name(self):
        function_code = 0x7F05
        message = self.tcp_send_command(function_code)
        return self.bytes_to_ascii(message)

    # 0x7F06: Read/write customer name (R/W)
    def rw_customer_name(self, rw : int = 1, name: str = None):
        function_code = 0x7F06
        if rw == 1:
            function_code = function_code| 0x8000

        if name is None:
            # Read operation
            return self.tcp_send_command(function_code)
        else:
            # Write operation (max 17 characters)
            data = name.encode('ascii')
            if len(data) > 17:
                raise ValueError("Customer name exceeds the 17 character limit")
            return self.tcp_send_command(function_code, data)

    # 0x7F50: Read device status
    def r_device_status(self):
        function_code = 0x7F50
        return self.tcp_send_command(function_code)

    # 0x7F51: Read error codes
    def r_error_codes(self):
        function_code = 0x7F51
        return self.tcp_send_command(function_code)

    # 0x7F52: Read warning codes
    def r_warning_codes(self):
        function_code = 0x7F52
        return self.tcp_send_command(function_code)

    # 0x7F60: Read/write voltage value (R/W)
    def rw_voltage(self, index: int, value: float = None):
        function_code = 0x7F60
        if value is None:
            # Read operation
            data = bytes([index])
        else:
            # Write operation (sending voltage as double in Big Endian format)
            data = bytes([index]) + value.to_bytes(8, 'big', signed=False)
        return self.tcp_send_command(function_code, data)

    # 0x7F61: Read actual voltage value
    def r_actual_voltage(self, index: int):
        function_code = 0x7F61
        data = bytes([index])
        return self.tcp_send_command(function_code, data)

    # 0x7F62: Read/write current value (R/W)
    def rw_current(self, index: int, value: float = None):
        function_code = 0x7F62
        if value is None:
            # Read operation
            data = bytes([index])
        else:
            # Write operation
            data = bytes([index]) + value.to_bytes(8, 'big', signed=False)
        return self.tcp_send_command(function_code, data)

    # 0x7F63: Read actual current value
    def r_actual_current_value(self, channel: int):
        mode_mapping = {
            'Ic': 1,
            'Ie': 2,
            'Iflux': 3,
            'Ifil1': 4,
            'Ifil2': 5,
            'Ifil3': 6,
            'Ifil4': 7
        }

        # Check if the unit is valid, otherwise raise an error
        if channel not in mode_mapping:
            raise ValueError(f"Invalid unit '{channel}'. Must be one of 'Ic', 'Ie', 'Iflux', 'Ifil1', 'Ifil2', 'Ifil3', 'Ifil4'.")
        mode = mode_mapping[channel]
        function_code = 0x7F63
        data = bytes([mode])
        message = self.tcp_send_command(function_code, data)        
        if len(message) <= 1:
            return 0
        else:
            return self.bytes_to_double(message[1:])

    ### HEAT3 Orders ###

    # 0x4101: Operate control (R/W)
    def operate_control(self, channel: int, operate_on: bool, rw: int = 1):
        function_code = 0x4101
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel, 1 if operate_on else 0])
        message = self.tcp_send_command(function_code, data)
        return message[1:]

    # 0x4102: Run/Hold control (R/W)
    def run_hold_control(self, channel: int, run: bool, rw: int = 1):
        function_code = 0x4102
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel, 1 if run else 0])
        message = self.tcp_send_command(function_code, data)
        return message[1:]

    # 0x4103: Process value unit (R/W)
    def set_process_value_unit(self, channel: int, unit: str, rw: int = 1):
        unit_mapping = {
            'K': 0,  # Kelvin
            'C': 1,  # Celsius
            'F': 2,  # Fahrenheit
            'V': 3   # Voltage
        }

        # Check if the unit is valid, otherwise raise an error
        if unit not in unit_mapping:
            raise ValueError(f"Invalid unit '{unit}'. Must be one of 'K', 'C', 'F', or 'V'.")
        unit_int = unit_mapping[unit]
        function_code = 0x4103
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel, unit_int])
        message = self.tcp_send_command(function_code, data)
        return message[1:]

    # 0x4104: Read temperature from thermocouple channel (R)
    def r_temperature_from_thermocouple(self, channel: str):
        channel_mapping = {
            'Tc1': 1,
            'Tc2': 2
        }
        channel_int = channel_mapping[channel]
        function_code = 0x4104
        data = bytes([channel_int])
        message = self.tcp_send_command(function_code, data)
        return self.bytes_to_double(message[1:])

    # 0x4105: Read temperature from diode channel (R)
    def r_temperature_from_diode(self, channel: int):
        channel_mapping = {
            'D1': 1,
            'D2': 2
        }
        channel_int = channel_mapping[channel]
        function_code = 0x4105
        data = bytes([channel_int])
        message = self.tcp_send_command(function_code, data)
        return self.bytes_to_double(message[1:])

    # 0x4106: Read temperature from resistance channel (R)
    def r_temperature_from_resistance(self):
        function_code = 0x4106
        return self.tcp_send_command(function_code)
        
    # 0x4107: Thermocouple type (R/W)
    def set_thermocouple_type(self, channel: int, thermocouple_type: int, rw: int = 1):
        function_code = 0x4107
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel, thermocouple_type])
        return self.tcp_send_command(function_code, data)

    # 0x4108: Diode type (R/W)
    def set_diode_type(self, channel: int, diode_type: int, rw: int = 1):
        function_code = 0x4108
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel, diode_type])
        return self.tcp_send_command(function_code, data)

    # 0x4109: Resistance sensor type (R/W)
    def set_resistance_sensor_type(self, channel: int, sensor_type: int, rw: int = 1):
        function_code = 0x4109
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel, sensor_type])
        return self.tcp_send_command(function_code, data)

    # 0x410A: Regulation type (T/dT) (R/W)
    def set_regulation_type(self, channel: int, regulation_type: str, rw: int = 1):
        mode_mapping = {
            'T': 0,  # T mode
            'dT': 1  # dT mode   
        }

        # Check if the unit is valid, otherwise raise an error
        if regulation_type not in mode_mapping:
            raise ValueError(f"Invalid unit '{regulation_type}'. Must be one of 'T', 'Tc'.")
        mode = mode_mapping[regulation_type]
        function_code = 0x410A
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel, mode])
        message = self.tcp_send_command(function_code, data)
        return message[1:]

    # 0x410B: Heating mode EB/RES (R/W)
    def set_heating_mode(self, heating_mode: str, rw: int = 1):
        mode_mapping = {
            'RES': 0,  # resistive mode
            'EB': 1    # electron bombarded mode   
        }

        # Check if the unit is valid, otherwise raise an error
        if heating_mode not in mode_mapping:
            raise ValueError(f"Invalid unit '{heating_mode}'. Must be one of 'RES', 'EB'.")
        mode = mode_mapping[heating_mode]
        function_code = 0x410B
        channel = 1
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel, mode])
        message = self.tcp_send_command(function_code, data)
        return message

    # 0x410C: Work mode AUTO/MANUAL (R/W)
    def set_work_mode(self, channel: int, work_mode: str, rw: int = 1):
        mode_mapping = {
            'Manual': 0,   # Manual
            'PID': 1,      # PID Auto   
            'External': 2, # External Controll (read only)
            'Out': 3       # PID Out (read only)
        }

        # Check if the unit is valid, otherwise raise an error
        if work_mode not in mode_mapping:
            raise ValueError(f"Invalid unit '{work_mode}'. Must be one of 'Manual', 'PID', 'External', 'Out'.")
        mode = mode_mapping[work_mode]
        function_code = 0x410C
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel, mode])
        message = self.tcp_send_command(function_code, data)
        return message[1:]

    # 0x410D: Autotune ON/OFF (R/W)
    def set_autotune(self, channel: int, autotune_on: bool, rw: int = 1):
        function_code = 0x410D
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel, 1 if autotune_on else 0])
        message = self.tcp_send_command(function_code, data)
        return message[1:]

    # 0x410E: Input selection for Process Value (R/W)
    def set_input_selection_for_process_value(self, channel: int, input_selection: str, rw: int = 1):
        mode_mapping = {
            'Tc1': 0,   # Thermocoulpe Channel 1
            'Tc2': 1,   # Thermocoulpe Channel 2
            'D1': 2,    # Diode Channel 1
            'D2': 3,    # Diode Channel 2
            'RTD': 4,   # Resistance Channel
            'Ain1': 5,  # Analog Input Channel 1
            'Ain2': 6   # Analog Input Channel 2
        }

        # Check if the unit is valid, otherwise raise an error
        if input_selection not in mode_mapping:
            raise ValueError(f"Invalid unit '{input_selection}'. Must be one of 'Tc1', 'Tc2', 'D1', 'D2', 'RTD', 'Ain1', 'Ain2'.")
        mode = mode_mapping[input_selection]
        function_code = 0x410E
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel, mode])
        message = self.tcp_send_command(function_code, data)
        return message[1:]

    # 0x410F: Cathode ramp at RES mode at OPERATE mode (R/W) 
    def set_cathode_ramp_res_mode(self, channel: int, ramp_value: float, rw: int = 1):
        function_code = 0x410F
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel]) + self.double_to_bytes(ramp_value)
        message = self.tcp_send_command(function_code, data)
        return message[1:]

    # 0x4110: Cathode ramp unit at RES mode at OPERATE mode (R/W)
    def set_cathode_ramp_unit_res_mode(self, channel: int, ramp_unit: int, rw: int = 1):
        function_code = 0x4110
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel, ramp_unit])
        message = self.tcp_send_command(function_code, data)
        return message[1:]

    # 0x4111: Cathode ramp at RES mode during transition (R/W)
    def set_cathode_ramp_during_transition(self, channel: int, ramp_value: float, rw: int = 1):
        function_code = 0x4111
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel]) + self.double_to_bytes(ramp_value)
        message = self.tcp_send_command(function_code, data)
        return message[1:]

    # 0x4112: Cathode ramp unit during transition (R/W)
    def set_cathode_ramp_unit_during_transition(self, channel: int, ramp_unit: int, rw: int = 1):
        function_code = 0x4112
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel, ramp_unit])
        message = self.tcp_send_command(function_code, data)
        return message[1:]

    # 0x4113: Cathode ramp at EB mode at OPERATE mode (R/W)
    def set_cathode_ramp_eb_mode(self, ramp_value: float, rw: int = 1):
        function_code = 0x4113
        channel = 1
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel]) + self.double_to_bytes(ramp_value)
        message = self.tcp_send_command(function_code, data)
        return message

    # 0x4114: Cathode ramp unit at EB mode at OPERATE mode (R/W)
    def set_cathode_ramp_unit_eb_mode(self, ramp_unit: int, rw: int = 1):
        function_code = 0x4114
        channel = 1
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel, ramp_unit])
        message = self.tcp_send_command(function_code, data)
        return message

    # 0x4115: Cathode ramp at EB mode during transition (R/W)
    def set_cathode_ramp_transition_eb_mode(self, ramp_value: float, rw: int = 1):
        function_code = 0x4115
        channel = 1
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel]) + self.double_to_bytes(ramp_value)
        message = self.tcp_send_command(function_code, data)
        return message

    # 0x4116: Cathode ramp unit at EB mode during transition (R/W)
    def set_cathode_ramp_unit_transition_eb_mode(self, ramp_unit: int, rw: int = 1):
        function_code = 0x4116
        channel = 1
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel, ramp_unit])
        message = self.tcp_send_command(function_code, data)
        return message

    # 0x4117: Emission voltage ramp at OPERATE mode (R/W)
    def set_emission_voltage_ramp_operate(self, ramp_value: float, rw: int = 1):
        function_code = 0x4117
        channel = 1
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel]) + self.double_to_bytes(ramp_value)
        message = self.tcp_send_command(function_code, data)
        return message

    # 0x4118: Unit of emission voltage ramp at OPERATE mode (R/W)
    def set_unit_emission_voltage_ramp(self, ramp_unit: int, rw: int = 1):
        function_code = 0x4118
        channel = 1
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel, ramp_unit])
        message = self.tcp_send_command(function_code, data)
        return message

    # 0x4119: Emission voltage ramp during transition (R/W)
    def set_emission_voltage_ramp_transition(self, ramp_value: float, rw: int = 1):
        function_code = 0x4119
        channel = 1
        if rw == 1:
            function_code = function_code | 0x8000
        data =  bytes([channel]) + self.double_to_bytes(ramp_value)
        message = self.tcp_send_command(function_code, data)
        return message

    # 0x411A: Unit of emission voltage ramp during transition (R/W)
    def set_unit_emission_voltage_ramp_transition(self, ramp_unit: int, rw: int = 1):
        function_code = 0x411A
        channel = 1
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel, ramp_unit])
        message = self.tcp_send_command(function_code, data)
        return message

    # 0x411B: Setpoint for T-mode (R/W)
    def set_setpoint_t_mode(self, channel: int, setpoint: float, rw: int = 1):
        function_code = 0x411B
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel]) + self.double_to_bytes(setpoint)
        message = self.tcp_send_command(function_code, data)
        return message[1:]

    # 0x411C: Ramp rate for T-mode (R/W)
    def set_ramp_rate_t_mode(self, channel: int, ramp_rate: float, rw: int = 1):
        function_code = 0x411C
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel]) + self.double_to_bytes(ramp_rate)
        message = self.tcp_send_command(function_code, data)
        return message[1:]

    # 0x411D: Ramp rate unit for T-mode (R/W)
    def set_ramp_rate_unit_t_mode(self, channel: int, ramp_rate_unit: int, rw: int = 1):
        function_code = 0x411D
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel, ramp_rate_unit])
        message = self.tcp_send_command(function_code, data)
        return message[1:]

    # 0x411E: Setpoint for dT-mode (R/W)
    def set_setpoint_dt_mode(self, channel: int, setpoint: float, rw: int = 1):
        function_code = 0x411E
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel]) + self.double_to_bytes(setpoint)
        message = self.tcp_send_command(function_code, data)
        return message[1:]

    # 0x411F: Trigger temperature for dT-mode (R/W)
    def set_trigger_temperature_dt_mode(self, channel: int, trigger_temp: float, rw: int = 1):
        function_code = 0x411F
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel]) + self.double_to_bytes(trigger_temp)
        message = self.tcp_send_command(function_code, data)
        return message[1:]

    # 0x4120: End temperature for T-mode (R/W)
    def set_end_temperature_t_mode(self, channel: int, end_temp: float, rw: int = 1):
        function_code = 0x4120
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel]) + self.double_to_bytes(end_temp)
        message = self.tcp_send_command(function_code, data)
        return message[1:]

    # 0x4121: The P parameter of pid regulator at T-mode  (R/W)
    def set_p_parameter_t_mode(self, channel: int, p: float, rw: int = 1):
        function_code = 0x4121
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel]) + self.double_to_bytes(p)
        message = self.tcp_send_command(function_code, data)
        return message[1:]

    # 0x4122: The I parameter of pid regulator at T-mode  (R/W)
    def set_i_parameter_t_mode(self, channel: int, i: float, rw: int = 1):
        function_code = 0x4122
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel]) + self.double_to_bytes(i)
        message = self.tcp_send_command(function_code, data)
        return message[1:]

    # 0x4123: The D parameter of pid regulator at T-mode  (R/W)
    def set_d_parameter_t_mode(self, channel: int, d: float, rw: int = 1):
        function_code = 0x4123
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel]) + self.double_to_bytes(d)
        message = self.tcp_send_command(function_code, data)
        return message[1:]

    # 0x4127: Ic limit for res mode   (R/W)
    def set_Ic_limit_res_mode(self, channel: int, value: float, rw: int = 1):       
        function_code = 0x4127
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel]) + self.double_to_bytes(value)
        message = self.tcp_send_command(function_code, data)
        return message[1:]

    # 0x4128: Uc limit for res mode   (R/W)
    def set_Uc_limit_res_mode(self, channel: int, value: float, rw: int = 1):       
        function_code = 0x4128
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel]) + self.double_to_bytes(value)
        message = self.tcp_send_command(function_code, data)
        return message[1:]

    # 0x4129: Ic limit for eb mode (* only with HV module)   (R/W)
    def set_Ic_limit_eb_mode(self, value: float, rw: int = 1):       
        function_code = 0x4129
        channel = 1
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel]) + self.double_to_bytes(value)
        message = self.tcp_send_command(function_code, data)
        return message[1:]

    # 0x412A: Uc limit for eb mode (* only with HV module)   (R/W)
    def set_Uc_limit_eb_mode(self, value: float, rw: int = 1):       
        function_code = 0x412A
        channel = 1
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel]) + self.double_to_bytes(value)
        message = self.tcp_send_command(function_code, data)
        return message[1:]

    # 0x4129: Ie limit for eb mode (* only with HV module)   (R/W)
    def set_Ie_limit_eb_mode(self, value: float, rw: int = 1):       
        function_code = 0x412B
        channel = 1
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel]) + self.double_to_bytes(value)
        message = self.tcp_send_command(function_code, data)
        return message[1:]

    # 0x412A: Ue limit for eb mode (* only with HV module)   (R/W)
    def set_Ue_limit_eb_mode(self, value: float, rw: int = 1):       
        function_code = 0x412C
        channel = 1
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel]) + self.double_to_bytes(value)
        message = self.tcp_send_command(function_code, data)
        return message[1:]

    # 0x412D: Output signal Ue/Uc(Ic) (* only with HV module)  (R/W)
    def set_output_signal_Ue_UcIc(self, output: str, rw: int = 1):       
        output_mapping = {
            'Ue': 0,   # output Ue
            'Ic': 1  # output Uc/Ic (module dependent)
        }

        # Check if the unit is valid, otherwise raise an error
        if output not in output_mapping:
            raise ValueError(f"Invalid unit '{output}'. Must be one of 'Ue', 'Ic', 'UcIc'.")
        mode = output_mapping[output]
        function_code = 0x412D
        channel = 1
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel, mode])
        message = self.tcp_send_command(function_code, data)
        return message

    # 0x412E: Read/write of Uc target value   (R/W)
    def set_Uc_target_value(self, channel: int, value: float, rw: int = 1):
        function_code = 0x412E
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel]) + self.double_to_bytes(value)
        message = self.tcp_send_command(function_code, data)
        return message[1:]        

    # 0x412F: Read of actual value of Uc
    def r_actual_value_Uc(self, channel: int):
        function_code = 0x412F
        data = bytes([channel])
        message = self.tcp_send_command(function_code, data)
        return self.bytes_to_double(message[1:])     

    # 0x4130: Read/write of Ue target value (* only with HV module)   (R/W)
    def set_Ue_target_value(self, value: float, rw: int = 1):
        function_code = 0x4130
        channel = 1
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel]) + self.double_to_bytes(value)
        message = self.tcp_send_command(function_code, data)
        return message[1:]

    # 0x4131: Read of actual value of Ue
    def r_actual_value_Ue(self):
        function_code = 0x4131
        channel = 1
        data = bytes([channel])
        message = self.tcp_send_command(function_code, data)
        if len(message) == 1:
            return 0
        else:
            return self.bytes_to_double(message[1:])
        #return self.bytes_to_double(message[1:])

    # 0x4132: Read/write of Ic target value (* only with HV module)   (R/W)
    def set_Ic_target_value(self, channel: int, value: float, rw: int = 1):
        function_code = 0x4132
        if rw == 1:
            function_code = function_code | 0x8000
        data = bytes([channel]) + self.double_to_bytes(value)
        message = self.tcp_send_command(function_code, data)
        return message[1:]        

    # 0x4133: Read of actual value of Ic
    def r_actual_value_Ic(self, channel: int):
        function_code = 0x4133
        data = bytes([channel])
        message = self.tcp_send_command(function_code, data)
        return self.bytes_to_double(message[1:])

    # 0x4134: Read of actual value of Ie
    def r_actual_value_Ie(self):
        function_code = 0x4134
        channel = 1
        data = bytes([channel])
        message = self.tcp_send_command(function_code, data)
        if len(message) == 1:
            return 0
        else:
            return self.bytes_to_double(message[1:])
        #return self.bytes_to_double(message[1:])

    # 0x413A: Actual process value (R)
    def r_actual_process_value(self, channel: int):
        function_code = 0x413A
        data = bytes([channel])
        message = self.tcp_send_command(function_code, data)
        return self.bytes_to_double(message[1:])

    # 0x413B: Actual PID output value (R)
    def r_actual_pid_output_value(self, channel: int):
        function_code = 0x413B
        data = bytes([channel])
        message = self.tcp_send_command(function_code, data)
        return self.bytes_to_double(message[1:])

    # 0x4139: Vacuum interlock ON/OFF (R/W)
    def set_vacuum_interlock(self, channel: int, interlock_on: bool):
        function_code = 0x4139
        data = bytes([channel, 1 if interlock_on else 0])
        return self.tcp_send_command(function_code, data)

    ### Vacuum Gauge Orders ###

    # 0x0101: Read actual vacuum gauge value (R)
    def r_vacuum_gauge_value(self, channel: int):
        function_code = 0x0101
        data = bytes([channel])
        return self.tcp_send_command(function_code, data)

    # 0x0103: Vacuum gauge unit (R/W)
    def set_vacuum_gauge_unit(self, channel: int, unit: int):
        function_code = 0x0103
        data = bytes([channel, unit])
        return self.tcp_send_command(function_code, data)

    ### Digital Output Orders ###

    # 0x0301: Assignment of relay function (R/W)
    def assign_relay_function(self, channel: int, code: int):
        function_code = 0x0301
        data = bytes([channel, code])
        return self.tcp_send_command(function_code, data)

    ### Digital Input Orders ###

    # 0x0401: Assignment of function to the input (R/W)
    def assign_input_function(self, channel: int, code: int, input_number: int):
        function_code = 0x0401
        data = bytes([channel, code, input_number])
        return self.tcp_send_command(function_code, data)

    ### Analog Output Orders ###

    # 0x0501: Set analog output signal source (R/W)
    def set_analog_output_signal_source(self, channel: int, signal_source: int):
        function_code = 0x0501
        data = bytes([channel, signal_source])
        return self.tcp_send_command(function_code, data)

    ### Analog Input Orders ###

    # 0x0601: Assign input to the function (R/W)
    def assign_analog_input_function(self, channel: int, code: int):
        function_code = 0x0601
        data = bytes([channel, code])
        return self.tcp_send_command(function_code, data)
