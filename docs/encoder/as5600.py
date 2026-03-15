# Support for AS5600 magnetic encoder with continuous monitoring
# and closed-loop position hold control
#
# Copyright (C) 2025  Custom Sewing Machine Project
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import logging, math
import chelper

# AS5600 I2C address
AS5600_ADDR = 0x36

# AS5600 Registers
REG_RAW_ANGLE_H = 0x0C # Raw angle high byte
REG_RAW_ANGLE_L = 0x0D # Raw angle low byte
REG_STATUS = 0x0B      # Status register
REG_AGC = 0x1A         # Automatic gain control
REG_MAGNITUDE_H = 0x1B # Magnitude high byte
REG_MAGNITUDE_L = 0x1C # Magnitude low byte

class AS5600:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name().split()[-1]
        
        # Setup I2C using Klipper's standard infrastructure
        from . import bus
        self.i2c = bus.MCU_I2C_from_config(
            config,
            default_addr=AS5600_ADDR,
            default_speed=100000)  # 100kHz
        
        self.mcu = self.i2c.get_mcu()
        
        # Position tracking state
        self.last_angle = 0
        self.last_raw_angle = 0
        self.total_revolutions = 0
        self.absolute_position = 0.0  # In degrees
        
        # Continuous monitoring
        self.monitoring_active = False
        self.monitor_timer = None
        self.monitor_rate = config.getfloat('monitor_rate', 0.0, minval=0.0)
        self.angle_history = []
        self.max_history = 1000
        
        # Closed-loop control mode
        self.mode = config.getchoice('mode', 
            {'monitor': 'monitor',      # Read only
             'hold': 'hold',            # Active position hold
             'track': 'track'},         # Track commanded position
            default='monitor')
        
        # Closed-loop parameters
        self.target_position = None  # Target position in degrees
        self.tolerance = config.getfloat('position_tolerance', 2.0, minval=0.1)
        self.deadband = config.getfloat('deadband', 3.0, minval=0.0)
        self.max_correction = config.getfloat('max_correction', 10.0, minval=1.0)
        self.correction_speed = config.getfloat('correction_speed', 10.0, above=0.)
        self.kp = config.getfloat('control_kp', 0.5, minval=0.0)
        
        # Stepper control (for hold/track modes)
        self.stepper_name = config.get('stepper', None)
        self.manual_stepper = None
        self.correction_in_progress = False
        
        # Statistics
        self.sample_count = 0
        self.error_count = 0
        self.correction_count = 0
        
        # Register event handlers
        self.printer.register_event_handler("klippy:ready", self._handle_ready)
        
        # Register G-code commands
        gcode = self.printer.lookup_object('gcode')
        gcode.register_mux_command("QUERY_AS5600", "SENSOR", self.name,
                                   self.cmd_QUERY_AS5600,
                                   desc=self.cmd_QUERY_AS5600_help)
        gcode.register_mux_command("AS5600_STATUS", "SENSOR", self.name,
                                   self.cmd_AS5600_STATUS,
                                   desc=self.cmd_AS5600_STATUS_help)
        gcode.register_mux_command("AS5600_START_MONITOR", "SENSOR", self.name,
                                   self.cmd_START_MONITOR,
                                   desc=self.cmd_START_MONITOR_help)
        gcode.register_mux_command("AS5600_STOP_MONITOR", "SENSOR", self.name,
                                   self.cmd_STOP_MONITOR,
                                   desc=self.cmd_STOP_MONITOR_help)
        gcode.register_mux_command("AS5600_RESET_POSITION", "SENSOR", self.name,
                                   self.cmd_RESET_POSITION,
                                   desc=self.cmd_RESET_POSITION_help)
        gcode.register_mux_command("AS5600_SET_TARGET", "SENSOR", self.name,
                                   self.cmd_SET_TARGET,
                                   desc=self.cmd_SET_TARGET_help)
        
        logging.info("AS5600 '%s' initialized (monitor_rate=%.1fHz, mode='%s')" 
                     % (self.name, self.monitor_rate, self.mode))
    
    def _handle_ready(self):
        """Called when Klipper is ready"""
        # Setup stepper control if needed
        if self.stepper_name and self.mode in ['hold', 'track']:
            try:
                self.manual_stepper = self.printer.lookup_object(self.stepper_name)
                logging.info("AS5600 '%s': Closed-loop '%s' mode with stepper '%s'" 
                           % (self.name, self.mode, self.stepper_name))
            except Exception as e:
                logging.error("AS5600 '%s': Could not find stepper '%s': %s" 
                            % (self.name, self.stepper_name, str(e)))
                self.mode = 'monitor'  # Fall back to monitor mode
        
        # Start continuous monitoring if configured
        if self.monitor_rate > 0.0:
            self.start_monitoring()
    
    def read_reg(self, reg):
        """Read single byte from register"""
        params = self.i2c.i2c_read([reg], 1)
        return bytearray(params['response'])[0]
    
    def read_reg16(self, reg_high):
        """Read 16-bit value from two consecutive registers"""
        params = self.i2c.i2c_read([reg_high], 2)
        data = bytearray(params['response'])
        return (data[0] << 8) | data[1]
    
    def read_angle(self):
        """Read raw 12-bit angle (0-4095) and update position tracking"""
        # Try up to 3 times with I2C errors
        for retry in range(3):
            try:
                angle = self.read_reg16(REG_RAW_ANGLE_H)
                angle = angle & 0x0FFF  # Mask to 12 bits
                
                # Track revolutions (detect wraparound)
                if self.last_raw_angle > 3072 and angle < 1024:
                    # Wrapped forward (0° crossing going up)
                    self.total_revolutions += 1
                elif self.last_raw_angle < 1024 and angle > 3072:
                    # Wrapped backward (0° crossing going down)
                    self.total_revolutions -= 1
                
                self.last_raw_angle = angle
                
                # Calculate absolute position
                angle_deg = (angle / 4095.0) * 360.0
                self.absolute_position = (self.total_revolutions * 360.0) + angle_deg
                
                self.sample_count += 1
                
                return angle
            except Exception as e:
                self.error_count += 1
                if retry < 2:
                    # Small delay before retry
                    import time
                    time.sleep(0.001)  # 1ms delay
                    continue
                else:
                    # After 3 failures, disable hold mode for safety
                    if self.mode == 'hold' and self.target_position is not None:
                        logging.error("AS5600 '%s': I2C communication failed, disabling hold mode!" 
                                    % self.name)
                        self.target_position = None
                    logging.warning("AS5600 '%s': Error reading angle (retry %d/3): %s" 
                                  % (self.name, retry+1, str(e)))
                    return self.last_raw_angle
    
    def read_status(self):
        """Read status register"""
        status = self.read_reg(REG_STATUS)
        return {
            'magnet_detected': bool(status & 0x20),
            'magnet_too_strong': bool(status & 0x08),
            'magnet_too_weak': bool(status & 0x10),
            'status_raw': status
        }
    
    def start_monitoring(self, rate=None):
        """Start continuous angle monitoring"""
        if rate is not None:
            self.monitor_rate = rate
        
        if self.monitor_rate <= 0.0:
            return
        
        if self.monitoring_active:
            return
        
        reactor = self.printer.get_reactor()
        self.monitor_timer = reactor.register_timer(
            self._monitor_callback, reactor.NOW)
        self.monitoring_active = True
        
        logging.info("AS5600 '%s': Started monitoring at %.1f Hz" 
                     % (self.name, self.monitor_rate))
    
    def stop_monitoring(self):
        """Stop continuous monitoring"""
        if not self.monitoring_active:
            return
        
        reactor = self.printer.get_reactor()
        reactor.unregister_timer(self.monitor_timer)
        self.monitor_timer = None
        self.monitoring_active = False
        
        logging.info("AS5600 '%s': Stopped monitoring" % self.name)
    
    def _monitor_callback(self, eventtime):
        """Periodic monitoring callback"""
        try:
            # Read current angle
            angle = self.read_angle()
            
            # Store in history (keep limited size)
            if len(self.angle_history) >= self.max_history:
                self.angle_history.pop(0)
            self.angle_history.append({
                'time': eventtime,
                'angle': angle,
                'position': self.absolute_position
            })
            
            # Closed-loop control based on mode
            if self.mode == 'hold' and self.target_position is not None:
                self._update_position_hold()
            elif self.mode == 'track' and self.manual_stepper is not None:
                self._update_position_tracking()
            
        except Exception as e:
            logging.error("AS5600 '%s': Monitor callback error: %s" 
                         % (self.name, str(e)))
        
        # Schedule next callback
        return eventtime + (1.0 / self.monitor_rate)
    
    def _update_position_hold(self):
        """Active position hold - correct deviations from target"""
        if not self.manual_stepper or self.target_position is None:
            return
        
        # Skip if already correcting
        if self.correction_in_progress:
            return
        
        # Calculate error (use absolute position for multi-revolution support)
        current_pos = self.absolute_position
        error = self.target_position - current_pos
        
        # Check if within deadband
        if abs(error) < self.deadband:
            return  # Close enough, no correction needed
        
        # Calculate correction distance (limit to max_correction)
        correction_deg = min(abs(error), self.max_correction)
        if error < 0:
            correction_deg = -correction_deg
        
        # Convert degrees to mm (using rotation_distance)
        # rotation_distance is mm per 360 degrees
        rotation_distance = self.manual_stepper.rail.steppers[0].get_rotation_distance()[0]
        correction_mm = (correction_deg / 360.0) * rotation_distance
        
        # Calculate target position in mm
        target_mm = self.manual_stepper.commanded_pos + correction_mm
        
        # Issue correction move (non-blocking)
        try:
            self.correction_in_progress = True
            self.manual_stepper.do_move(
                target_mm,
                self.correction_speed,
                self.manual_stepper.accel,
                sync=False)
            self.correction_count += 1
            
            # Log significant corrections
            if abs(error) > 5.0:
                logging.info("AS5600 '%s': Hold correction: error=%.2f° move=%.2fmm" 
                            % (self.name, error, correction_mm))
            
            # Reset flag after move completes (approximate timing)
            reactor = self.printer.get_reactor()
            move_time = abs(correction_mm) / self.correction_speed
            reactor.register_timer(
                lambda t: self._clear_correction_flag(),
                reactor.monotonic() + move_time)
        except Exception as e:
            logging.error("AS5600 '%s': Correction move failed: %s" 
                        % (self.name, str(e)))
            self.correction_in_progress = False
    
    def _update_position_tracking(self):
        """Track mode - monitor deviation from commanded position"""
        if not self.manual_stepper:
            return
        
        # Get commanded position from stepper
        commanded_mm = self.manual_stepper.commanded_pos
        
        # Convert to degrees
        rotation_distance = self.manual_stepper.rail.steppers[0].get_rotation_distance()[0]
        commanded_deg = (commanded_mm / rotation_distance) * 360.0
        
        # Calculate tracking error
        actual_deg = self.absolute_position
        error = commanded_deg - actual_deg
        
        # Log if error exceeds tolerance
        if abs(error) > self.tolerance:
            logging.warning("AS5600 '%s': Position tracking error: %.2f° (commanded=%.1f actual=%.1f)" 
                          % (self.name, error, commanded_deg, actual_deg))
    
    def _clear_correction_flag(self):
        """Clear correction in progress flag"""
        self.correction_in_progress = False
        return self.printer.get_reactor().NEVER
    
    cmd_QUERY_AS5600_help = "Query AS5600 encoder angle and position"
    def cmd_QUERY_AS5600(self, gcmd):
        """Read and display encoder angle"""
        try:
            # Read angle
            angle_raw = self.read_angle()
            angle_deg = (angle_raw / 4095.0) * 360.0
            
            response = "AS5600 '%s':\n" % self.name
            response += "  Mode: %s\n" % self.mode
            response += "  Raw angle: %d / 4095\n" % angle_raw
            response += "  Degrees: %.2f°\n" % angle_deg
            response += "  Revolutions: %d\n" % self.total_revolutions
            response += "  Absolute position: %.2f°\n" % self.absolute_position
            response += "  Samples: %d (errors: %d)" % (self.sample_count, self.error_count)
            
            if self.monitoring_active:
                response += "\n  Monitoring: ACTIVE (%.1f Hz)" % self.monitor_rate
            
            if self.mode in ['hold', 'track']:
                response += "\n  Corrections: %d" % self.correction_count
            
            if self.target_position is not None:
                error = self.target_position - self.absolute_position
                response += "\n  Target: %.2f° (error: %.2f°)" % (self.target_position, error)
                if abs(error) < self.deadband:
                    response += " [OK]"
                else:
                    response += " [CORRECTING]"
            
            gcmd.respond_info(response)
            
        except Exception as e:
            gcmd.respond_info("Error reading AS5600: %s" % str(e))
    
    cmd_AS5600_STATUS_help = "Query AS5600 magnet detection status"
    def cmd_AS5600_STATUS(self, gcmd):
        """Read and display magnet status"""
        try:
            status = self.read_status()
            
            detected = "YES" if status['magnet_detected'] else "NO"
            weak = "YES" if status['magnet_too_weak'] else "NO"
            strong = "YES" if status['magnet_too_strong'] else "NO"
            
            gcmd.respond_info("AS5600 '%s' Status:\n"
                             "  Magnet detected: %s\n"
                             "  Magnet too weak: %s\n"
                             "  Magnet too strong: %s\n"
                             "  Status register: 0x%02x"
                             % (self.name, detected, weak, strong, 
                                status['status_raw']))
        except Exception as e:
            gcmd.respond_info("Error reading AS5600 status: %s" % str(e))
    
    cmd_START_MONITOR_help = "Start continuous angle monitoring"
    def cmd_START_MONITOR(self, gcmd):
        """Start monitoring"""
        rate = gcmd.get_float('RATE', self.monitor_rate, minval=0.1, maxval=100.0)
        self.start_monitoring(rate)
        gcmd.respond_info("AS5600 '%s': Monitoring started at %.1f Hz" 
                         % (self.name, rate))
    
    cmd_STOP_MONITOR_help = "Stop continuous angle monitoring"
    def cmd_STOP_MONITOR(self, gcmd):
        """Stop monitoring"""
        self.stop_monitoring()
        gcmd.respond_info("AS5600 '%s': Monitoring stopped (collected %d samples)" 
                         % (self.name, len(self.angle_history)))
    
    cmd_RESET_POSITION_help = "Reset revolution counter and absolute position"
    def cmd_RESET_POSITION(self, gcmd):
        """Reset position tracking"""
        self.total_revolutions = 0
        angle_raw = self.read_angle()
        gcmd.respond_info("AS5600 '%s': Position reset (current angle: %d)" 
                         % (self.name, angle_raw))
    
    cmd_SET_TARGET_help = "Set target position for closed-loop hold"
    def cmd_SET_TARGET(self, gcmd):
        """Set target position for hold mode"""
        if gcmd.get_int('CLEAR', 0):
            self.target_position = None
            gcmd.respond_info("AS5600 '%s': Target cleared, hold disabled" % self.name)
        else:
            position = gcmd.get_float('POSITION', None)
            if position is None:
                # If no position given, use current absolute position
                position = self.absolute_position
                gcmd.respond_info("AS5600 '%s': Holding current position: %.2f°" 
                                % (self.name, position))
            else:
                gcmd.respond_info("AS5600 '%s': Target position set to %.2f°" 
                                % (self.name, position))
            
            self.target_position = position
            
            if self.mode != 'hold':
                gcmd.respond_info("Warning: Mode is '%s', should be 'hold' for position hold" 
                                % self.mode)
    
    def get_status(self, eventtime):
        """Get current status dict (for other modules)"""
        return {
            'angle': self.last_raw_angle,
            'degrees': (self.last_raw_angle / 4095.0) * 360.0,
            'revolutions': self.total_revolutions,
            'absolute_position': self.absolute_position,
            'monitoring': self.monitoring_active,
            'samples': self.sample_count,
            'errors': self.error_count,
        }

def load_config(config):
    return AS5600(config)

def load_config_prefix(config):
    return AS5600(config)
