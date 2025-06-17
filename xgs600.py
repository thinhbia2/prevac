import serial
import time

class XGS600Controller:
    def __init__(self, address: str, port: str, baudrate=9600, timeout=2):
        """Initialize the serial connection."""
        self.address = address
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_conn = None

    def connect(self):
        """Establish a serial connection."""
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            print(f"Connected to {self.port} at {self.baudrate} baud.")
            return True
        except serial.SerialException as e:
            raise ConnectionError(f"Failed to connect to device: {e}")
            return False

    def disconnect(self):
        """Close the serial connection."""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            print("Connection closed.")

    def send_command(self, command):
        """Send a command to the XGS-600 controller."""
        if not self.serial_conn or not self.serial_conn.is_open:
            raise Exception("Serial connection is not open.")

        full_command = f"{command}\r"  # Commands must end with a carriage return
        #print(full_command)
        self.serial_conn.write(full_command.encode('ascii'))
        time.sleep(0.01)  # Wait for the device to process the command
        response = self.serial_conn.read_until(b'\r')
        #print(response) 
        response_str = response.decode('ascii').strip()
        if response_str.startswith(">"):
            response_str = response_str[1:]
        return response_str

    def read_pressure(self, channel: str):
        """Read pressure from the XGS-600 controller."""
        vacuum_mapping = {
            "IG1": "I1",
            "IG2": "I2",
            "IG3": "I3",
            "CH1": "I1",
            "CH2": "I2",
            "CH3": "I3",
            "CH4": "I1"
        }

        # Check if the unit is valid, otherwise raise an error
        if channel not in vacuum_mapping:
            raise ValueError(f"Invalid unit '{channel}'. Must be one of IG1, IG2, IG3, CH1, CH2, CH3, CH4.")
            
        sensor_label = vacuum_mapping[channel]
        command = f"#{self.address}02{sensor_label}"
        response = self.send_command(command)
        return float(response)

    def read_sw_version(self):
        """Read software revision of the XGS-600 controller."""
        command = f"#{self.address}05"
        response = self.send_command(command)
        return response
