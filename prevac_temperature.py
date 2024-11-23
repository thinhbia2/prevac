import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import font as tkFont
from tkinter import filedialog
import threading
import time
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from prevacv2TCP import prevacV2TCP
from modbusTCP import ModbusTCP
import threading
from queue import Queue, Empty
import time
from itertools import zip_longest

def on_closing():
    plt.close('all')  # Close all matplotlib plots
    root.destroy()

class CommunicationError(Exception):
    pass

# Main class for the heating control system GUI
class HeatingControlApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Prevac Heating Control System")
        self.root.geometry("1200x1000")
        self.root.config(padx=20, pady=20)

        self.heat3 = None
        self.mg15 = None

        self.arial14 = tkFont.Font(family='Arial', size=14)
        self.arial18 = tkFont.Font(family='Arial', size=18)

        # Variables for server IPs and Ports
        self.heat3_channel = 1
        self.time_interval = 0.25
        self.time_sleep = 0.2
        self.temp_step = 5
        self.heat3_ip = tk.StringVar(value="192.168.201.252")
        self.heat3_port = tk.IntVar(value=502)
        self.mg15_ip = tk.StringVar(value="192.168.201.253")
        self.mg15_port = tk.IntVar(value=502)

        self.mode_array = ["Auto", "Manual"];
        self.ic_ue_options = ["Ic", "Ue"]
        self.heating_array = ["RES", "EB"];
        self.temp_input_array = ["Tc1", "Tc2", "D1", "D2", "RTD", "Ain1", "Ain2"];
        self.unit_array = ["K","C"];
        self.vacuum_input_array = ["IG1", "IG2", "IG3", "CH1", "CH2", "CH3", "CH4"]

        self.mode_value = tk.StringVar(value=self.mode_array[0])
        self.ic_ue_value = tk.StringVar(value=self.ic_ue_options[0])
        self.heating_value = tk.StringVar(value=self.heating_array[1])
        self.temp_input_value = tk.StringVar(value=self.temp_input_array[5])
        self.unit_value = tk.StringVar(value=self.unit_array[1])
        self.vacuum_input_value = tk.StringVar(value=self.vacuum_input_array[0])
        self.pressure_limit_value = tk.StringVar(value="5.00e-7")
        self.pressure_base_value = tk.StringVar(value="5.00e-9")

        # Variables to hold the input values
        self.temp_value = tk.DoubleVar(value=0.1)
        self.degass_factor = tk.DoubleVar(value=0.8)
        self.pressure_value = tk.DoubleVar(value=0.1)
        self.p_value = tk.StringVar(value="90")
        self.i_value = tk.StringVar(value="20")
        self.d_value = tk.StringVar(value="250")
        self.num_segments_value = tk.StringVar(value="1")
        self.repeat_value = tk.StringVar(value="0") # widget accepts string
        #self.r_values = []
        self.sp_values = []
        self.t_values = []
        self.ic_value = tk.StringVar(value="0.0")
        self.uc_value = tk.DoubleVar(value=0.0)
        self.ie_value = tk.DoubleVar(value=0.0)
        self.ue_value = tk.StringVar(value="0.0")
        self.ic_limit_value = tk.StringVar(value="4.00")
        self.uc_limit_value = tk.StringVar(value="5.00")
        self.ie_limit_value = tk.StringVar(value="20")
        self.ue_limit_value = tk.StringVar(value="1000")
        self.plot_txt_size = 14
        self.toggle_buttons = {}
    
        # Initial empty data for x and y axes
        self.x_temp = []
        self.y_temp = []
        self.x_pressure = []
        self.y_pressure = []

        self.command_queue = Queue()

        # For toggle button states
        self.heat3_connected = False
        self.mg15_connected = False
        self.heat3_thread_running = False
        self.mg15_thread_running = False

        self.run_thread = None
        self.running = False
        
        self.create_widgets()
        self.plot_data = []

        # Update the UI based on initial mode selections
        self.update_mode_settings()
        self.update_heating_settings()

    def heat3_communication_thread(self):
        """Thread dedicated to handling all TCP/IP communication with heat3."""
        #while self.heat3_thread_running:
        while self.heat3_connected:
            try:
                command, args, kwargs, response_queue = self.command_queue.get(timeout=2)
                result = command(*args, **kwargs)
                if response_queue:
                    response_queue.put(result)
            except Empty:
                continue  # No command in queue, continue loop

    def send_command(self, command, *args, **kwargs):
        response_queue = Queue()
        self.command_queue.put((command, args, kwargs, response_queue))
        try:
            return response_queue.get(timeout=2)
        except Empty:
            if self.running:
                self.running = False
                self.start_pause_button.config(text="Stop", bg="red")
                self.enable_controls()  # Re-enable Mode and Heating selection

            self.heat3_connected = False
            self.heat3_thread_running = False

            # Clear product and serial numbers
            self.heat3_product_label.config(text="")
            self.heat3_serial_label.config(text="")
            self.toggle_buttons["HEAT3-PS IP:"].config(text="Disconnect", bg="red")

            raise CommunicationError("Timeout during TCP/IP communication.")

    def create_widgets(self):
        # First row: HEAT3-PS IP and Port input with connect/disconnect button
        self.add_row_label_input_toggle_button(0, "HEAT3-PS IP:", self.heat3_ip, self.heat3_port, self.toggle_heat3_connection)

        # Labels for MG15 Product and Serial Number
        self.heat3_product_label = tk.Label(self.root, text="", font=self.arial14)
        self.heat3_product_label.grid(row=0, column=4, padx=5, sticky=tk.W)
        self.heat3_serial_label = tk.Label(self.root, text="", font=self.arial14)
        self.heat3_serial_label.grid(row=0, column=5, padx=5, sticky=tk.W)

        # Second row: MG15 IP and Port input with connect/disconnect button
        self.add_row_label_input_toggle_button(1, "MG15         IP:", self.mg15_ip, self.mg15_port, self.toggle_mg15_connection)

        # Labels for MG15 Product and Serial Number
        self.mg15_product_label = tk.Label(self.root, text="", font=self.arial14)
        self.mg15_product_label.grid(row=1, column=4, padx=5, sticky=tk.W)
        self.mg15_serial_label = tk.Label(self.root, text="", font=self.arial14)
        self.mg15_serial_label.grid(row=1, column=5, padx=5, sticky=tk.W)
        
        # Third row: Mode and Heating dropboxes, temperature display and unit selection
        self.add_third_row()

        self.add_degas_row()                                                                      
        # Fourth row: Pressure control and PID settings
        self.add_fourth_row()

        # Fifth row: Ramp/level settings and graph plot
        self.add_fifth_row()

        # Sixth row: Real-time temperature plot
        self.add_sixth_row()

        # Last row: Control buttons
        self.add_control_buttons()

    def add_row_label_input_toggle_button(self, row, label, ip_var, port_var, toggle_callback):
        tk.Label(self.root, width=11, text=label, font=self.arial14).grid(row=row, padx=0, pady=0, column=0, sticky=tk.W)
        ip_entry = tk.Entry(self.root, font=self.arial14, width=15, textvariable=ip_var)
        ip_entry.grid(row=row, column=1, padx=0, sticky=tk.W)

        #tk.Label(self.root, text=label, font=self.arial14).grid(row=row, column=2, sticky=tk.W)
        port_entry = tk.Entry(self.root, font=self.arial14, width=5, textvariable=port_var)
        port_entry.grid(row=row, column=2, padx=0, sticky=tk.W)

        toggle_button = tk.Button(self.root, text="Disconnect", font=self.arial14, bg="red", command=lambda: toggle_callback(toggle_button))
        toggle_button.grid(row=row, column=3, padx=0, sticky=tk.W)
        
        self.toggle_buttons[label] = toggle_button

    def toggle_heat3_connection(self, button):
        if not self.heat3_connected:
            # Connect
            self.heat3 = prevacV2TCP(self.heat3_ip.get(), self.heat3_port.get())
            if self.heat3.connect():

                # Start the HEAT3-PS reading thread
                self.heat3_connected = True
                self.heat3_thread_running = True
                self.comm_thread = threading.Thread(target=self.heat3_communication_thread)
                self.comm_thread.start()
                self.heat3_thread = threading.Thread(target=self.read_heat3_data)
                self.heat3_thread.start()
                #self.schedule_read_heat3_data()

                product_number = self.send_command(self.heat3.r_product_number)
                serial_number  = self.send_command(self.heat3.r_serial_number)
                self.heat3_product_label.config(text=f"{product_number}")
                self.heat3_serial_label.config(text=f"{serial_number}")
                self.send_command(self.heat3.register_new_host)

                button.config(text="Connected", bg="green")
                self.create_plot()
        else:
            if self.running:
                self.stop_heat3_master()
            self.heat3_connected = False
            self.heat3_thread_running = False
            # Stop the HEAT3-PS thread
            #self.heat3_thread.join()  # Wait for the thread to finish
            #self.comm_thread.join()

            # Clear product and serial numbers
            self.heat3_product_label.config(text="")
            self.heat3_serial_label.config(text="")
            button.config(text="Disconnect", bg="red")
            # Disconnect
            #if self.heat3:
            #    self.heat3.close()

    def toggle_mg15_connection(self, button):
        if not self.mg15_connected:
            # Connect
            self.mg15 = ModbusTCP(self.mg15_ip.get(), self.mg15_port.get())
            self.mg15.connect()
            
            # Start the MG15 reading thread
            self.mg15_thread_running = True
            self.mg15_thread = threading.Thread(target=self.read_mg15_data)
            self.mg15_thread.start()

            product_number = self.mg15.read_product_number()
            serial_number = self.mg15.read_serial_number()
            self.mg15_product_label.config(text=f"{product_number}")
            self.mg15_serial_label.config(text=f"{serial_number}")
            button.config(text="Connected", bg="green")
            self.mg15_connected = True
        else:
            self.mg15_stop()
            #if self.mg15:
            #    self.mg15.close()

    def add_third_row(self):
        tk.Label(self.root, text="Working Mode:", font=self.arial14).grid(row=2, column=0, sticky=tk.W)

        mode_frame = tk.Frame(self.root)
        self.mode = ttk.Combobox(mode_frame, font=self.arial14, values=self.mode_array, width=6, textvariable=self.mode_value)
        self.mode.pack(side="left", padx=0)
        self.mode.current(0)
        self.mode.bind("<<ComboboxSelected>>", lambda e: self.update_mode_settings())
        # Add the Ic/Ue Combobox inside the frame (hidden initially)
        self.ic_ue_combobox = ttk.Combobox(mode_frame, font=self.arial14, values=self.ic_ue_options, width=4, textvariable=self.ic_ue_value)
        self.ic_ue_combobox.pack(side="left", padx=0)  # Pack it next to the Heating Mode Combobox
        self.ic_ue_combobox.pack_forget()  # Hide initially
        self.ic_ue_combobox.bind("<<ComboboxSelected>>", lambda e: self.update_ic_ue_controls())
        mode_frame.grid(row=2, column=1, padx=0, sticky=tk.W)

        tk.Label(self.root, text="Heating Mode:", font=self.arial14).grid(row=2, column=2, sticky=tk.W)  
        self.heating = ttk.Combobox(self.root, font=self.arial14, values=self.heating_array, width=4, textvariable=self.heating_value)
        self.heating.grid(row=2, column=3, padx=0, sticky=tk.W)
        self.heating.current(0)
        self.heating.bind("<<ComboboxSelected>>", lambda e: self.update_mode_settings())

        #tk.Label(self.root, text="Input:", font=self.arial14).grid(row=2, column=4, sticky=tk.W)
        self.temp_input = ttk.Combobox(self.root, font=self.arial14, values=self.temp_input_array, width=5, textvariable=self.temp_input_value)
        self.temp_input.grid(row=2, column=4, padx=0, sticky=tk.W)
        #self.temp_input.current(0)
        #self.temp_input.bind("<<ComboboxSelected>>", lambda e: self.update_temp_input())

        self.temp_display = tk.Label(self.root, textvariable=self.temp_value, font=self.arial18, width=8)
        self.temp_display.grid(row=2, column=5, padx=0, sticky="e")

        #tk.Label(self.root, font=self.arial14).grid(row=2, column=7, sticky=tk.W)
        self.temp_unit = ttk.Combobox(self.root, font=self.arial18, values=self.unit_array, width=3, textvariable=self.unit_value)
        self.temp_unit.grid(row=2, column=6, padx=0, sticky=tk.W)
        self.temp_unit.current(1)
        #self.temp_input.bind("<<ComboboxSelected>>", lambda e: self.update_temp_unit())

    def add_degas_row(self):
        self.degas_var = tk.IntVar()
        self.degas_check = tk.Checkbutton(self.root, text="Degas", font=self.arial14, variable=self.degas_var, command=self.toggle_degas)
        self.degas_check.grid(row=3, column=0, sticky=tk.W)

        tk.Label(self.root, text="Limit:", font=self.arial14).grid(row=3, column=1, sticky=tk.W)
        self.pressure_limit = tk.Entry(self.root, font=self.arial14, width=7, textvariable=self.pressure_limit_value)
        self.pressure_limit.grid(row=3, column=1, padx=0, sticky=tk.E)

        tk.Label(self.root, text="Base:", font=self.arial14).grid(row=3, column=2, sticky=tk.W)
        self.pressure_base = tk.Entry(self.root, font=self.arial14, width=7, textvariable=self.pressure_base_value)
        self.pressure_base.grid(row=3, column=2, padx=0, sticky=tk.E)

        self.pressure_label = tk.Label(self.root, text="mbar", font=self.arial14)
        self.pressure_label.grid(row=3, column=3, sticky=tk.W)

        # Initial state is greyed out
        self.toggle_degas()

        #tk.Label(self.root, text="Channel:", font=self.arial14).grid(row=3, column=13, sticky=tk.W)
        self.channel = ttk.Combobox(self.root, font=self.arial14, values=self.vacuum_input_array, width=5, textvariable=self.vacuum_input_value)
        self.channel.grid(row=3, column=4, padx=0, sticky=tk.W)

        self.pressure_display = tk.Label(self.root, textvariable=self.pressure_value, font=self.arial18, width=8)
        self.pressure_display.grid(row=3, column=5, padx=0, sticky='e')
        tk.Label(self.root, text="mbar", font=self.arial18).grid(row=3, column=6, sticky=tk.W)

    def toggle_degas(self):
        if self.degas_var.get():
            self.pressure_limit.config(state="normal")
            self.pressure_base.config(state="normal")
            self.pressure_label.config(state="normal")
        else:
            self.pressure_limit.config(state="disabled")
            self.pressure_base.config(state="disabled")
            self.pressure_label.config(state="disabled")

    def add_fourth_row(self):
        # Frame to contain the two columns
        self.fourth_row_frame = tk.Frame(self.root)
        self.fourth_row_frame.grid(row=4, column=0, columnspan=17, pady=10, sticky=tk.W)

        # First Column (PID Settings)
        self.pid_frame = tk.LabelFrame(self.fourth_row_frame, text="PID Settings", font=self.arial14)
        self.pid_frame.grid(row=0, column=0, padx=10, sticky=tk.W)

        tk.Label(self.pid_frame, text="P:", font=self.arial14).grid(row=0, column=0, sticky=tk.E)
        self.p_entry = tk.Entry(self.pid_frame, font=self.arial14, width=5, textvariable=self.p_value)
        self.p_entry.grid(row=0, column=1, padx=5, sticky=tk.W)

        tk.Label(self.pid_frame, text="I:", font=self.arial14).grid(row=0, column=2, sticky=tk.E)
        self.i_entry = tk.Entry(self.pid_frame, font=self.arial14, width=5, textvariable=self.i_value)
        self.i_entry.grid(row=0, column=3, padx=5, sticky=tk.W)

        tk.Label(self.pid_frame, text="D:", font=self.arial14).grid(row=0, column=4, sticky=tk.E)
        self.d_entry = tk.Entry(self.pid_frame, font=self.arial14, width=5, textvariable=self.d_value)
        self.d_entry.grid(row=0, column=5, padx=5, sticky=tk.W)

        tk.Label(self.pid_frame, text="Number of Segments:", font=self.arial14).grid(row=1, column=0, sticky=tk.W)
        self.num_segments_entry = tk.Entry(self.pid_frame, font=self.arial14, width=5, textvariable=self.num_segments_value)
        self.num_segments_entry.grid(row=1, column=1, padx=5, sticky=tk.W)

        tk.Label(self.pid_frame, text="Repeat:", font=self.arial14).grid(row=1, column=2, sticky=tk.W)
        self.repeat_entry = tk.Entry(self.pid_frame, font=self.arial14, width=5, textvariable=self.repeat_value)
        self.repeat_entry.grid(row=1, column=3, padx=5, sticky=tk.W)

        # Second Column (Manual Control Inputs)
        self.manual_frame = tk.LabelFrame(self.fourth_row_frame, text="Manual Control", font=self.arial14)
        self.manual_frame.grid(row=0, column=1, padx=10, sticky=tk.W)

        tk.Label(self.manual_frame, text="Ic:", font=self.arial14).grid(row=0, column=0, sticky=tk.W)
        self.ic_entry = tk.Entry(self.manual_frame, font=self.arial14, width=6, textvariable=self.ic_value)
        self.ic_entry.grid(row=0, column=1, padx=5)
        self.ic_entry.bind("<MouseWheel>", self.change_ic_value)
        self.ic_entry.bind("<Return>", self.ic_value_entered)  # Bind keyboard "Enter" for Ic entry
        self.ic_entry.bind("<FocusOut>", self.ic_value_entered)
        tk.Label(self.manual_frame, text="A", font=self.arial14).grid(row=0, column=2, sticky=tk.W)

        tk.Label(self.manual_frame, text="Uc:", font=self.arial14).grid(row=0, column=3, sticky=tk.W)
        self.uc_display = tk.Label(self.manual_frame, font=self.arial14, width=6, textvariable=self.uc_value)
        self.uc_display.grid(row=0, column=4, padx=5)
        tk.Label(self.manual_frame, text="V", font=self.arial14).grid(row=0, column=5, sticky=tk.W)

        # Second row in manual frame
        tk.Label(self.manual_frame, text="Ie:", font=self.arial14)
        self.ie_display = tk.Label(self.manual_frame, font=self.arial14, width=6, textvariable=self.ie_value)
        #self.ie_display.grid(row=0, column=4, padx=5, sticky=tk.W)
        tk.Label(self.manual_frame, text="mA", font=self.arial14)

        tk.Label(self.manual_frame, text="Ue:", font=self.arial14)
        self.ue_entry = tk.Entry(self.manual_frame, font=self.arial14, width=6, textvariable=self.ue_value)
        self.ue_entry.bind("<MouseWheel>", self.change_ue_value)
        self.ue_entry.bind("<Return>", self.ue_value_entered)  # Bind keyboard "Enter" for Ic entry
        self.ue_entry.bind("<FocusOut>", self.ue_value_entered)
        tk.Label(self.manual_frame, text="V", font=self.arial14)

        # Third Column (Limit Control Inputs)
        self.limit_frame = tk.LabelFrame(self.fourth_row_frame, text="Limit", font=self.arial14)
        self.limit_frame.grid(row=0, column=2, padx=10, sticky=tk.W)

        tk.Label(self.limit_frame, text="Ic:", font=self.arial14).grid(row=0, column=0, sticky=tk.W)
        self.ic_limit_entry = tk.Entry(self.limit_frame, font=self.arial14, width=6, textvariable=self.ic_limit_value)
        self.ic_limit_entry.grid(row=0, column=1, padx=5)
        self.ic_limit_entry.bind("<Return>", self.ic_limit_value_entered)
        self.ic_limit_entry.bind("<FocusOut>", self.ic_limit_value_entered)
        tk.Label(self.limit_frame, text="A", font=self.arial14).grid(row=0, column=2, sticky=tk.W)

        tk.Label(self.limit_frame, text="Uc:", font=self.arial14).grid(row=0, column=3, sticky=tk.W)
        self.uc_limit_entry = tk.Entry(self.limit_frame, font=self.arial14, width=6, textvariable=self.uc_limit_value)
        self.uc_limit_entry.grid(row=0, column=4, padx=5)
        self.uc_limit_entry.bind("<Return>", self.uc_limit_value_entered)
        self.uc_limit_entry.bind("<FocusOut>", self.uc_limit_value_entered)
        tk.Label(self.limit_frame, text="V", font=self.arial14).grid(row=0, column=5, sticky=tk.W)

        # Second row in manual frame
        tk.Label(self.limit_frame, text="Ie:", font=self.arial14)
        self.ie_limit_entry = tk.Entry(self.limit_frame, font=self.arial14, width=6, textvariable=self.ie_limit_value)
        self.ie_limit_entry.bind("<Return>", self.ie_limit_value_entered)
        self.ie_limit_entry.bind("<FocusOut>", self.ie_limit_value_entered)
        tk.Label(self.limit_frame, text="mA", font=self.arial14)

        tk.Label(self.limit_frame, text="Ue:", font=self.arial14)
        self.ue_limit_entry = tk.Entry(self.limit_frame, font=self.arial14, width=6, textvariable=self.ue_limit_value)
        self.ue_limit_entry.bind("<Return>", self.ue_limit_value_entered)
        self.ue_limit_entry.bind("<FocusOut>", self.ue_limit_value_entered)
        tk.Label(self.limit_frame, text="V", font=self.arial14)
        # Place these widgets conditionally based on Heating mode
        #self.update_heating_settings()
        
    def change_ic_value(self, event):
        """Change Ic value based on scroll up or down and send the new value to heat3."""
        if event.delta > 0:  # Scroll up
            new_value = float(self.ic_value.get()) + 0.01  # Increment by 0.1 (adjust as needed)
        else:  # Scroll down
            new_value = float(self.ic_value.get()) - 0.01  # Decrement by 0.1 (adjust as needed)

        new_value = max(0, new_value)  # Ensure the value doesn't go below 0
        self.ic_value.set(new_value)  # Update the entry field with the new value

        # Send the new Ic target value to heat3
        if self.running and self.heat3_thread_running:
            self.send_command(self.heat3.set_Ic_target_value,self.heat3_channel, new_value)

    def change_ue_value(self, event):
        """Change Ue value based on scroll up or down and send the new value to heat3."""
        if event.delta > 0:  # Scroll up
            new_value = float(self.ue_value.get()) + 1  # Increment by 0.1 (adjust as needed)
        else:  # Scroll down
            new_value = float(self.ue_value.get()) - 1  # Decrement by 0.1 (adjust as needed)

        new_value = max(0, new_value)  # Ensure the value doesn't go below 0
        self.ue_value.set(new_value)  # Update the entry field with the new value

        # Send the new Ue target value to heat3
        if self.running and self.heat3_thread_running:
            self.send_command(self.heat3.set_Ue_target_value,new_value)
        
    def ic_value_entered(self, event):
        """Update Ic target value when the user presses Enter or leaves the entry field."""
        try:
            new_value = float(self.ic_value.get())  # Get the new value from the entry
            if self.running and self.heat3_thread_running:
                self.send_command(self.heat3.set_Ic_target_value,self.heat3_channel, new_value)  # Send the updated value to heat3
        except ValueError:
            print("Invalid input for Ic value. Please enter a valid number.")

    def ue_value_entered(self, event):
        """Update Ue target value when the user presses Enter or leaves the entry field."""
        try:
            new_value = float(self.ue_value.get())  # Get the new value from the entry
            if self.running and self.heat3_thread_running:
                self.send_command(self.heat3.set_Ue_target_value,new_value)  # Send the updated value to heat3
        except ValueError:
            print("Invalid input for Ue value. Please enter a valid number.")

    def ic_limit_value_entered(self, event):
        try:
            new_value = float(self.ic_limit_value.get())  # Get the new value from the entry
            if self.mode_value.get() == "RES":
                if self.running and self.heat3_thread_running:
                    self.send_command(self.heat3.set_Ic_limit_res_mode,self.heat3_channel, new_value)
            else:
                if self.running and self.heat3_thread_running:
                    self.send_command(self.heat3.set_Ic_limit_eb_mode, new_value)
        except ValueError:
            print("Invalid input for limit Ic value. Please enter a valid number.")

    def uc_limit_value_entered(self, event):
        try:
            new_value = float(self.uc_limit_value.get())  # Get the new value from the entry
            if self.mode_value.get() == "RES":
                if self.running and self.heat3_thread_running:
                    self.send_command(self.heat3.set_Uc_limit_res_mode,self.heat3_channel, new_value)
            else:
                if self.running and self.heat3_thread_running:
                    self.send_command(self.heat3.set_Uc_limit_eb_mode, new_value)
        except ValueError:
            print("Invalid input for limit Uc value. Please enter a valid number.")

    def ie_limit_value_entered(self, event):
        try:
            new_value = float(self.ie_limit_value.get())  # Get the new value from the entry
            if self.running and self.heat3_thread_running:
                self.send_command(self.heat3.set_Ie_limit_eb_mode, new_value)
        except ValueError:
            print("Invalid input for limit Ie value. Please enter a valid number.")

    def ue_limit_value_entered(self, event):
        try:
            new_value = float(self.ue_limit_value.get())  # Get the new value from the entry
            if self.running and self.heat3_thread_running:
                self.send_command(self.heat3.set_Ue_limit_eb_mode, new_value)
        except ValueError:
            print("Invalid input for limit Ue value. Please enter a valid number.")

    def update_mode_settings(self):
        mode = self.mode_value.get()
        heating = self.heating_value.get()
        #print(f"Working Mode: {mode}, Heating Mode: {heating}") 

        # Show the Ic/Ue Combobox only if mode is Auto and heating is EB
        if mode == "Auto" and heating == "EB":
            self.ic_ue_combobox.pack(side="right")  # Show the Ic/Ue Combobox
            # Enable Manual Control in this specific case
            for child in self.manual_frame.winfo_children():
                child.configure(state="normal")
        else:
            self.ic_ue_combobox.pack_forget()  # Hide the Ic/Ue Combobox
            # Disable Manual Control in Auto mode unless conditions are met
            if mode == "Auto":
                for child in self.manual_frame.winfo_children():
                    child.configure(state="disabled")
                if heating == "EB":
                    self.update_ic_ue_controls()
            else:
                for child in self.manual_frame.winfo_children():
                    child.configure(state="normal")

        # Enable or disable PID Settings based on mode
        if mode == "Auto":
            for child in self.pid_frame.winfo_children():
                child.configure(state="normal")
            if heating == "EB":
                self.update_ic_ue_controls()
        else:
            for child in self.pid_frame.winfo_children():
                child.configure(state="disabled")

        # Always update the heating settings to display the correct fields
        self.update_heating_settings()

    def update_heating_settings(self):
        mode = self.mode_value.get()
        heating = self.heating_value.get()

        #print("Heating Mode settings")
        if heating == "RES":
            # Hide Ie and Ue inputs
            for widget in self.manual_frame.grid_slaves(row=1):
                widget.grid_remove()
            for widget in self.limit_frame.grid_slaves(row=1):
                widget.grid_remove()
        else:
            # Show Ie and Ue inputs
            tk.Label(self.manual_frame, text="Ie:", font=self.arial14).grid(row=1, column=0, sticky=tk.W)
            self.ie_display = tk.Label(self.manual_frame, font=self.arial14, width=6, textvariable=self.ie_value)
            self.ie_display.grid(row=1, column=1, padx=0)
            tk.Label(self.manual_frame, text="mA", font=self.arial14).grid(row=1, column=2, sticky=tk.W)

            tk.Label(self.manual_frame, text="Ue:", font=self.arial14).grid(row=1, column=3, sticky=tk.W)
            self.ue_entry = tk.Entry(self.manual_frame, font=self.arial14, width=6, textvariable=self.ue_value)
            self.ue_entry.bind("<MouseWheel>", self.change_ue_value)
            self.ue_entry.bind("<Return>", self.ue_value_entered)
            self.ue_entry.bind("<FocusOut>", self.ue_value_entered)   
            self.ue_entry.grid(row=1, column=4, padx=0)
            tk.Label(self.manual_frame, text="V", font=self.arial14).grid(row=1, column=5, sticky=tk.W)

            # Show Ie and Ue Limit
            tk.Label(self.limit_frame, text="Ie:", font=self.arial14).grid(row=1, column=0, sticky=tk.W)
            self.ie_limit_entry = tk.Entry(self.limit_frame, font=self.arial14, width=6, textvariable=self.ie_limit_value)
            self.ie_limit_entry.bind("<Return>", self.ie_limit_value_entered)
            self.ie_limit_entry.bind("<FocusOut>", self.ie_limit_value_entered)   
            self.ie_limit_entry.grid(row=1, column=1, padx=0)
            tk.Label(self.limit_frame, text="mA", font=self.arial14).grid(row=1, column=2, sticky=tk.W)

            tk.Label(self.limit_frame, text="Ue:", font=self.arial14).grid(row=1, column=3, sticky=tk.W)
            self.ue_limit_entry = tk.Entry(self.limit_frame, font=self.arial14, width=6, textvariable=self.ue_limit_value)
            self.ue_limit_entry.bind("<Return>", self.ue_limit_value_entered)
            self.ue_limit_entry.bind("<FocusOut>", self.ue_limit_value_entered)   
            self.ue_limit_entry.grid(row=1, column=4, padx=0)
            tk.Label(self.limit_frame, text="V", font=self.arial14).grid(row=1, column=5, sticky=tk.W)

        if mode == "Auto":
            # If in Auto mode, ensure manual frame is disabled
            for child in self.manual_frame.winfo_children():
                child.configure(state="disabled")
            if heating == "EB":
                self.update_ic_ue_controls()
        
    def update_ic_ue_controls(self):
        selected_value = self.ic_ue_value.get()

        if selected_value == "Ic":
            # Enable Ue controls and disable Ic controls
            self.ue_entry.config(state="normal")
            self.ic_entry.config(state="disabled")
        elif selected_value == "Ue":
            # Enable Ic controls and disable Ue controls
            self.ic_entry.config(state="normal")
            self.ue_entry.config(state="disabled")

    def create_segment_inputs(self):
        # Clear any existing segment inputs
        for widget in self.segment_frame.winfo_children():
            widget.destroy()

        num_segments_str = self.num_segments_value.get() 

        # Handle empty input or invalid string
        if not num_segments_str.strip():  # If it's empty or just whitespace
            num_segments = 1  # Set a default
            #self.num_segments_value.set("1")  # Reset the Entry to show 1
        else:
            try:
                num_segments = int(num_segments_str)  # Convert the valid string to integer
            except ValueError:
                num_segments = 1  # Handle any unexpected invalid input
                #self.num_segments_value.set("1")

        # Check if we need to add more entries to the lists (new columns)
        current_segments = len(self.t_values)
        
        if num_segments > current_segments:
            # Add new segments with default zero values for SP, and T
            for i in range(current_segments, num_segments):
                self.sp_values.append(tk.DoubleVar(value=25))  # Append new DoubleVar with default 25
                self.t_values.append(tk.DoubleVar(value=1))    # Append new DoubleVar with default 1

        # No need to change old segments, we just create the GUI inputs for the updated number of segments
        for i in range(num_segments):
            column_index = i * 2  # Each segment gets its own two columns

            # SP input (Setpoint temperature) and label in the same row
            sp_label = tk.Label(self.segment_frame, text=f"SP{i + 1}", font=self.arial14, anchor='w', justify='right')
            sp_label.grid(row=0, column=column_index, sticky="w", padx=10, pady=5)
            sp_input = tk.Entry(self.segment_frame, width=4, textvariable=self.sp_values[i], font=self.arial14)
            sp_input.grid(row=0, column=column_index + 1, padx=0, pady=5, sticky="w")

            # T input (Time for segment) and label in the same row
            t_label = tk.Label(self.segment_frame, text=f"T{i + 1}", font=self.arial14, anchor='w', justify='right')
            t_label.grid(row=1, column=column_index, sticky="w", padx=10, pady=5)
            t_input = tk.Entry(self.segment_frame, width=4, textvariable=self.t_values[i], font=self.arial14)
            t_input.grid(row=1, column=column_index + 1, padx=0, pady=5, sticky="w")

    def add_fifth_row(self):
        # Create a frame for the segment inputs
        self.segment_frame = tk.Frame(self.root)
        self.segment_frame.grid(row=5, column=0, columnspan=17, sticky="w")  # Align to the left

        self.create_segment_inputs()
        self.num_segments_value.trace("w", lambda *args: self.create_segment_inputs())

    def add_sixth_row(self):
        # Create a frame for the plot if necessary, or embed the plot directly
        self.plot_frame = tk.Frame(self.root)
        self.plot_frame.grid(row=6, column=0, columnspan=8, sticky="w")

        # Call the create_plot function to initialize the plot
        self.create_plot()

    def create_plot(self):
        # Create a larger figure for the plot
        self.fig, self.ax = plt.subplots(figsize=(12, 6))  # Adjust size as needed
        self.ax.set_title('Real-Time Plot', fontsize=self.plot_txt_size)
        self.ax.set_xlabel('Time (secs)', fontsize=self.plot_txt_size)
        self.ax.set_ylabel('Temperature (°C)', fontsize=self.plot_txt_size, color='tomato')
        
        # Adjust ticks size (both major and minor)
        self.ax.tick_params(axis='y', labelcolor='tomato', color='tomato')
        self.ax.spines['left'].set_color('tomato')  # Set spine color

        self.ax.tick_params(axis='both', which='major', labelsize=self.plot_txt_size)  # Major ticks
        self.ax.tick_params(axis='both', which='minor', labelsize=self.plot_txt_size)  # Minor ticks

        # Create the secondary y-axis
        self.ax_pressure = self.ax.twinx()
        self.ax_pressure.set_ylabel('Pressure (mbar)', fontsize=self.plot_txt_size, color='cornflowerblue')  # Set y-axis label color to blue
        
        # Set pressure y-axis ticks and labels to blue
        self.ax_pressure.tick_params(axis='y', labelcolor='cornflowerblue', color='cornflowerblue')
        self.ax_pressure.spines['right'].set_color('cornflowerblue')  # Set spine color
        self.ax_pressure.spines['left'].set_color('tomato')  # Set spine color
        self.ax_pressure.tick_params(axis='both', which='major', labelsize=self.plot_txt_size)
        self.ax_pressure.tick_params(axis='both', which='minor', labelsize=self.plot_txt_size)

        # Initialize Line2D objects for temperature and pressure
        self.temp_line, = self.ax.plot([], [], color='tomato')  # Set line color to orange
        self.pressure_line, = self.ax_pressure.plot([], [], color='cornflowerblue')  # Set line color to blue

        # Set up the canvas for embedding the plot in the Tkinter window
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.get_tk_widget().grid(row=0, column=0, columnspan=8)

        # Start updating the plot continuously
        #self.update_plot()

    def update_plot_temp(self):
        if self.heat3_connected and self.heat3_thread_running:  # Only update the plot if connected to HEAT3-PS
            # Append the current time and temperature to the data
            current_time = len(self.x_temp) * self.time_interval  # Assuming the plot updates every 0.3s
            current_temp = self.temp_value.get()

            self.x_temp.append(current_time)
            self.y_temp.append(current_temp)
            self.temp_line.set_data(self.x_temp, self.y_temp)
            self.ax.relim()
            self.ax.autoscale_view()
            self.canvas.draw()

    def update_plot_pressure(self):
        if self.heat3_connected and self.heat3_thread_running:  # Only update the plot if connected to HEAT3-PS
            # Append the current time and temperature to the data
            current_time = len(self.x_pressure) * self.time_interval  # Assuming the plot updates every 0.3s
            current_pressure = self.pressure_value.get()

            self.x_pressure.append(current_time)
            self.y_pressure.append(current_pressure)
            self.pressure_line.set_data(self.x_pressure, self.y_pressure)
            self.ax_pressure.relim()
            self.ax_pressure.autoscale_view()
            self.canvas.draw()

    def add_control_buttons(self):
        self.start_pause_button = tk.Button(self.root, text="Stop", bg="red", font=self.arial14, command=self.start_pause)
        self.start_pause_button.grid(row=8, column=2, padx=0, pady=10, sticky='e')

        self.save_button = tk.Button(self.root, text="Save", font=self.arial14, command=self.save_data)
        self.save_button.grid(row=8, column=3, padx=10, pady=10, sticky='w')

    def start_pause(self):
        if self.heat3_connected and self.heat3_thread_running:
            if not self.running:
                # Start the operation
                self.start_pause_button.config(text="Running", bg="green")
                self.disable_controls()  # Disable Mode and Heating selection
                self.send_command(self.heat3.master_mode,1)
                self.running = True

                self.run_thread = threading.Thread(target=self.run_control)
                self.run_thread.start()
            else:
                # Pause/Stop the operation
                self.stop_heat3_master()

    def stop_heat3_master(self):        
        self.running = False
        self.send_command(self.heat3.set_Ue_target_value, 0)
        self.send_command(self.heat3.operate_control,self.heat3_channel, 0)
        self.send_command(self.heat3.run_hold_control,self.heat3_channel, 0)
        self.send_command(self.heat3.master_mode,0)
        self.start_pause_button.config(text="Stop", bg="red")
        self.enable_controls()  # Re-enable Mode and Heating selection
        
    def disable_controls(self):
        # Disable the Mode and Heating comboboxes
        self.mode.config(state="disabled")
        self.heating.config(state="disabled")

    def enable_controls(self):
        # Enable the Mode and Heating comboboxes
        self.mode.config(state="normal")
        self.heating.config(state="normal")

    def run_control(self):
        num_segments = int(self.num_segments_value.get())
        repeat_count = int(self.repeat_value.get())  # Get the number of repeats
        current_sp = 0  # This will hold the current setpoint value
        init = True

        while self.running and self.heat3_thread_running:  # Keep running while the process is active
            try:
                if self.mode_value.get() == "Auto":
                    if init:
                        # Set heating mode and control parameters
                        self.send_command(self.heat3.set_heating_mode,self.heating_value.get())
                        self.send_command(self.heat3.set_p_parameter_t_mode,self.heat3_channel,float(self.p_value.get()))
                        self.send_command(self.heat3.set_i_parameter_t_mode,self.heat3_channel,float(self.i_value.get()))
                        self.send_command(self.heat3.set_d_parameter_t_mode,self.heat3_channel,float(self.d_value.get()))
                        self.send_command(self.heat3.set_work_mode,self.heat3_channel, "PID")
                        self.heat3.set_ramp_rate_unit_t_mode(self.heat3_channel,1)

                        if self.heating_value.get() == "EB":
                            self.send_command(self.heat3.set_Ic_limit_eb_mode, float(self.ic_limit_value.get()))
                            self.send_command(self.heat3.set_Uc_limit_eb_mode, float(self.uc_limit_value.get()))
                            self.send_command(self.heat3.set_Ie_limit_eb_mode, float(self.ie_limit_value.get()))
                            self.send_command(self.heat3.set_Ue_limit_eb_mode, float(self.ue_limit_value.get()))
                            self.send_command(self.heat3.set_output_signal_Ue_UcIc,self.ic_ue_value.get())
                            if(self.ic_ue_value.get() == 'Ue'):
                                self.send_command(self.heat3.set_Ic_target_value, self.heat3_channel, float(self.ic_value.get()))
                            else:
                                self.send_command(self.heat3.set_Ue_target_value, float(self.ue_value.get()))
                        else:
                            self.send_command(self.heat3.set_Ue_target_value, 0)
                            self.send_command(self.heat3.set_Ic_limit_res_mode,self.heat3_channel, float(self.ic_limit_value.get()))
                            self.send_command(self.heat3.set_Uc_limit_res_mode,self.heat3_channel, float(self.uc_limit_value.get()))
                            
                        self.send_command(self.heat3.set_input_selection_for_process_value,self.heat3_channel, self.temp_input_value.get())
                        self.send_command(self.heat3.operate_control,self.heat3_channel, 1)
                        self.send_command(self.heat3.run_hold_control,self.heat3_channel, 1)
                        init = False
                    # Repeat the sequence of segments
                    for repeat in range(repeat_count + 1):  # Repeat the sequence the specified number of times
                        if not self.running:
                            break  # Stop if the running flag is turned off

                        # Loop through each segment
                        for segment in range(num_segments):
                            if not self.running:
                                break

                            if segment == 0:
                                current_temperature = self.temp_value.get()
                            else:
                                current_temperature = self.sp_values[segment-1].get()
                            sp_value = self.sp_values[segment].get()
                            t_value = self.t_values[segment].get()
                            diff = sp_value - current_temperature

                            if diff > 0:
                                ramp = diff/t_value
                                self.send_command(self.heat3.set_ramp_rate_t_mode,self.heat3_channel,ramp)
                                self.send_command(self.heat3.set_setpoint_t_mode,self.heat3_channel,self.celsius_to_kelvin(sp_value))
                                while self.temp_value.get() < (sp_value - 0.2) and self.running and self.heat3_thread_running:
                                    if self.degas_var.get():
                                        self.degas_function(sp_value)
                                    time.sleep(self.time_sleep)
                            elif diff < 0:
                                ramp = abs(diff)/t_value
                                self.send_command(self.heat3.set_ramp_rate_t_mode,self.heat3_channel,ramp)
                                self.send_command(self.heat3.set_setpoint_t_mode,self.heat3_channel,self.celsius_to_kelvin(sp_value))
                                while self.temp_value.get() > (sp_value + 0.2) and self.running and self.heat3_thread_running:
                                    if self.degas_var.get():
                                        self.degas_function(sp_value)
                                    time.sleep(self.time_sleep)
                            else:
                                # Start the timer for the segment
                                t_value = self.t_values[segment].get()*60 # Convert to second time.time() returns second
                                #print(f"Inside No Ramp")
                                start_time = time.time()
                                while (time.time() - start_time < t_value) and self.running and self.heat3_thread_running:
                                    if self.degas_var.get():
                                        start_degas_time = time.time()
                                        self.degas_function(sp_value)
                                        end_degas_time = time.time()
                                        t_value = t_value + (end_degas_time - start_degas_time)
                                    time.sleep(self.time_sleep)

                    # End of the operation, reset the button and re-enable controls
                    #print(f"Finish Heating Cycle")
                    self.stop_heat3_master()

                else:
                    if self.heat3_thread_running:
                        # Manual Mode
                        # Just send run_hold_control and skip ramp/setpoint logic
                        self.send_command(self.heat3.set_work_mode, self.heat3_channel, self.mode_value.get())
                        self.send_command(self.heat3.set_heating_mode, self.heating_value.get())
                        self.send_command(self.heat3.set_Ic_target_value,self.heat3_channel, float(self.ic_value.get()))
                        if self.heating_value.get() == "EB":
                            self.send_command(self.heat3.set_Ue_target_value, float(self.ue_value.get()))
                        self.send_command(self.heat3.operate_control, self.heat3_channel, 1)
                        self.send_command(self.heat3.run_hold_control, self.heat3_channel, 1)
                    while self.running:
                        time.sleep(self.time_sleep)

            except CommunicationError:
                return
            # Exit loop if stopped during the run
            #if not self.running:
            #    break

    def save_data(self):
        filename = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("TXT files", "*.txt")])
        if filename:
            # Write the x_data (time) and y_data (temperature) to a TXT file
            try:
                with open(filename, mode='w') as file:
                    # Write the data points, tab-separated (no header)
                    for x, y, w, z in zip_longest(self.x_temp, self.y_temp, self.x_pressure, self.y_pressure, fillvalue=-1):
                        file.write(f"{x:.2f}\t{y:.1f}\t{w:.2f}\t{z:.2e}\n")

            except Exception as e:
                print(f"Error saving data: {e}")

    def get_temp(self):
        temp_source = self.temp_input_value.get()

        if temp_source in ["Tc1", "Tc2"]:
            # Read temperature from thermocouple
            temperature = self.send_command(self.heat3.r_temperature_from_thermocouple, temp_source)
            return temperature
        elif temp_source in ["D1", "D2"]:
            # Read temperature from diode
            temperature = self.send_command(self.heat3.r_temperature_from_diode, temp_source)
            return temperature
        elif temp_source == "RTD":
            # Read temperature from resistance (RTD)
            temperature = self.send_command(self.heat3.r_temperature_from_resistance)
            return temperature
        elif temp_source in ["Ain1", "Ain2"]:
            # Read process value from Ain1 or Ain2
            temperature = self.send_command(self.heat3.r_actual_process_value, self.heat3_channel)
            return temperature
        else:
            # Handle unexpected input source if needed
            print(f"Unknown temperature source: {temp_source}")
            return 0.0

    def read_heat3_data(self):
        # Run continuously until heat3_thread_running is set to False
        temperature = 0
        uc_actual = 0
        ic_actual = 0
        ue_actual = 0
        ie_actual = 0
        
        while self.heat3_connected and self.heat3_thread_running:
            try:
                # Read temperature from HEAT3-PS (or any other data)
                # Check the value of temp_input_value and call the corresponding function
                temperature = self.get_temp()
                self.temp_value.set(f"{self.kelvin_to_celsius(temperature):.1f}")
                #self.root.after(0, self.update_temperature_display)

                # Read Uc and Ic values and update in a thread-safe way
                uc_actual = self.send_command(self.heat3.r_actual_value_Uc, self.heat3_channel)
                self.uc_value.set(f"{uc_actual:.2f}")
                if self.mode_value.get() == "Auto":
                    if self.heating_value.get() == "RES" or self.ic_ue_value.get() == "Ic":
                        ic_actual = self.send_command(self.heat3.r_actual_value_Ic, self.heat3_channel)
                        self.ic_value.set(f"{ic_actual:.2f}")
                    if self.ic_ue_value.get() == "Ue":
                        ue_actual = self.send_command(self.heat3.r_actual_value_Ue)
                        self.ue_value.set(f"{ue_actual:.1f}")
                if self.heating_value.get() == "EB":
                    ie_actual = self.send_command(self.heat3.r_actual_value_Ie)*1000
                    self.ie_value.set(f"{ie_actual:.1f}")
                #self.root.after(0, self.update_uc_ic_display)
                
                # Start updating the plot continuously
                self.root.after(0, self.update_plot_temp)

                # Sleep for a short period (e.g., 0.3 seconds) before the next read
                time.sleep(self.time_interval)

            except CommunicationError:
                return

            #finally:
                # Re-schedule the next data read
                #self.schedule_read_heat3_data()

    def read_mg15_data(self):
        vacuum_value = 0
        while self.mg15_thread_running:
            try:
                vacuum_input_str = self.vacuum_input_value.get()
                vacuum_value = self.mg15.read_vacuum(vacuum_input_str)
                self.pressure_value.set(f"{vacuum_value:.2e}")
                self.root.after(0, self.update_plot_pressure)
                time.sleep(self.time_interval)

            except Exception as e:
                print(f"Error reading from MG15: {e}")
                # Stop the MG15 thread
                self.mg15_stop()
                break
            except TimeoutError:
                print(f"Error reading from MG15 Timeout")
                # Stop the MG15 thread
                self.mg15_stop()
                break

    def mg15_stop(self):
        # Stop the MG15 thread
        self.mg15_thread_running = False
        self.mg15_connected = False
        self.mg15_product_label.config(text="")
        self.mg15_serial_label.config(text="")
        self.toggle_buttons["MG15         IP:"].config(text="Disconnect", bg="red")

    def degas_function(self, set_temp):
        sp_value = set_temp
        current_pressure = self.pressure_value.get()
        while current_pressure > float(self.pressure_base_value.get()) and self.running and self.heat3_thread_running and self.mg15_thread_running:
            degas_nominal_pressure = (float(self.pressure_base_value.get()) + float(self.pressure_limit_value.get()))/2
            if current_pressure > degas_nominal_pressure:
                # Adjust the setpoint downward to maintain pressure below the limit
                sp_value -= self.temp_step                                                                              
                self.send_command(self.heat3.set_setpoint_t_mode,self.heat3_channel,self.celsius_to_kelvin(sp_value))
            else:
                if set_temp > sp_value:
                    sp_value += 1  # Return setpoint incrementally (adjust as needed)
                    self.send_command(self.heat3.set_setpoint_t_mode,self.heat3_channel,self.celsius_to_kelvin(sp_value))
            time.sleep(self.time_sleep)

    def kelvin_to_celsius(self, temp):
        if self.unit_value.get() == "C":
            return (temp - 273.15)  # Convert Kelvin to Celsius
        else:
            return temp  # Keep Kelvin

    def celsius_to_kelvin(self, temp):
        if self.unit_value.get() == "C":
            return (temp + 273.15)  # Convert Celsius to Kelvin
        else:
            return temp  # Keep Kelvin

# Create the main window and run the app
if __name__ == "__main__":
    root = tk.Tk()
    app = HeatingControlApp(root)
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

