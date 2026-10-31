; drift: variants=image,hybrid
; drift: expect=ok
; A TurtleStitch job (beta6 export) through virtual_sdcard.
; drift: log=Starting SD card print
; drift: log=Exiting SD card print
G28
SDCARD_PRINT_FILE FILENAME=turtlestitch.gcode
