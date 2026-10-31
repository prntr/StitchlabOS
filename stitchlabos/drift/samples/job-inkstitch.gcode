; drift: variants=image,hybrid
; drift: expect=ok
; An Ink/Stitch job through virtual_sdcard, as Mainsail starts it.
; drift: log=Starting SD card print
; drift: log=Exiting SD card print
; drift: log=Finished SD card print
G28
SDCARD_PRINT_FILE FILENAME=inkstitch.gcode
