import socket
import struct

class ModbusTCP:
    def __init__(self, ip_address, port = 502):
        self.ip_address = ip_address
        self.port = port
        self.sock = None
        self.protocol_id = 0x0000 # Protocol ID for Modbus TCP
        self.device_address = 0x01 #  Modbus TCP, address is set to 0x01

    def connect(self):
        """
        Create and open a TCP socket connection to the Modbus server.
        """
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.ip_address, self.port))
            print(f"Connected to {self.ip_address}:{self.port}")
        except socket.error as e:
            print(f"Failed to connect to {self.ip_address}:{self.port}: {e}")
            self.sock = None

    def close(self):
        """Close the TCP connection."""
        if self.sock:
            self.sock.close()
            self.sock = None
            print(f"Disconnected from {self.ip_address}:{self.port}")

    def bytes_to_ascii(self, data: bytes) -> str:
        return data.decode('ascii')

    def bytes_to_float(self, data: bytes) -> float:
        return struct.unpack('>f', data)[0]

    def crc16_modbus(self, data):
        """
        Calculate the CRC-16 for Modbus RTU frame.
        """
        crc = 0xFFFF
        for pos in data:
            crc ^= pos
            for _ in range(8):
                if (crc & 0x0001) != 0:
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        return crc

    def build_data_frame(self, transaction_id, function_code, reg_address, num_words):
        """
        Build the Modbus TCP request frame and append CRC.
        """
        data_length = num_words
        data = bytearray([self.device_address, function_code])
        data.extend(reg_address.to_bytes(2, 'big'))
        data.extend(num_words.to_bytes(data_length, 'big'))
        frame_length = len(data)
        crc = self.crc16_modbus(data)
        data.extend(crc.to_bytes(2, 'little')) # historical Modbus, crc is little endian
        
        data_frame = bytearray()
        data_frame.extend(transaction_id.to_bytes(2, 'big'))
        data_frame.extend(self.protocol_id.to_bytes(2, 'big'))
        data_frame.extend(frame_length.to_bytes(2, 'big'))
        data_frame.extend(data)
        
        return data_frame

    def tcp_send_command(self, request):
        """
        Send the request to the Modbus server and receive the response.
        """
        if self.sock is None:
            raise ConnectionError("Socket is not connected. Call connect() first.")

        try:
            self.sock.sendall(request)
            response = self.sock.recv(1024)  # Buffer size is 1024 bytes
            return response
        except socket.error as e:
            print(f"Failed to send or receive data: {e}")
            return None

    def parse_response(self, response):
        """
        Extract the raw data from the Modbus TCP response based on the byte count field.
        Return the raw data bytes.
        """
        if response is None:
            return None

        # First 9 bytes are the Modbus header and metadata
        byte_count = response[8]  # Byte count field is the 9th byte (index 8)

        # Extract the data bytes as indicated by byte count
        modbus_data = response[9:9 + byte_count]
        return modbus_data  # Return the raw data to be converted by the calling function

    def read_vacuum(self, channel_number, status=0):
        """
        Read vacuum value (float) or status (uint8) based on the channel and status flag.
        
        :param channel_number: Channel number (1-7)
        :param status: 0 = read vacuum value (float), 1 = read status (uint8) (default is 0)
        :return: The value read from the register (float or uint8)
        """
        # Validate the inputs
        if channel_number < 1 or channel_number > 7:
            raise ValueError("Channel number must be between 1 and 7")
        if status not in [0, 1]:
            raise ValueError("Status must be 0 (vacuum value) or 1 (status)")

        # Map the Modbus register address based on the channel and status
        if status == 0:  # Read vacuum value (float)
            reg_address = (channel_number - 1) * 3   # Addresses 0, 3, 6, 9, 12, 15, 18
            num_words = 2  # Float uses 2 registers
        elif status == 1:  # Read status (uint8)
            reg_address = (channel_number - 1) * 3 + 2  # Addresses 2, 5, 8, 11, 14, 17, 20
            num_words = 1  # Status uses 1 register

        # Build the Modbus TCP request frame
        transaction_id = 1  # Example transaction ID
        function_code = 0x03  # Read holding registers
        request = self.build_data_frame(transaction_id, function_code, reg_address, num_words)

        # Send the request and receive the response
        response = self.tcp_send_command(request)

        # Parse the response to extract the raw data
        raw_data = self.parse_response(response)
        
        # Convert the raw data into the appropriate format
        if status == 0 and raw_data:  # Vacuum value (float)
            high_register = raw_data[0:2]
            low_register = raw_data[2:4]
            register_value = high_register + low_register
            return self.bytes_to_float(register_value)  # Convert to float
        elif status == 1 and raw_data:  # Status value (uint8)
            return raw_data[0]  # Convert to uint8
        else:
            return None

    def read_product_number(self):
        """
        Read product number 15⋅CHAR.

        """

        # Build the Modbus TCP request frame
        transaction_id = 1  # Example transaction ID
        function_code = 0x03  # Read holding registers
        reg_address = 0x1001  # Address
        num_words = 15         #15 characters
        request = self.build_data_frame(transaction_id, function_code, reg_address, num_words)

        response = self.tcp_send_command(request)
        raw_data = self.parse_response(response)
        return self.bytes_to_ascii(raw_data)

    def read_serial_number(self):
        """
        Read seiral number 13⋅CHAR.

        """

        # Build the Modbus TCP request frame
        transaction_id = 1  # Example transaction ID
        function_code = 0x03  # Read holding registers
        reg_address = 0x1009  # Address
        num_words = 13         #13 characters
        request = self.build_data_frame(transaction_id, function_code, reg_address, num_words)

        response = self.tcp_send_command(request)
        raw_data = self.parse_response(response)
        return self.bytes_to_ascii(raw_data)
