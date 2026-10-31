; drift: variants=image,hybrid
; drift: expect=ok
; M00 must stop the job for rethreading (beta6 contract): the probe that
; follows the colour change in the job must not run.
; drift: log=Starting SD card print
; drift: log=Exiting SD card print
; drift: nolog=DRIFT pos X=20.000
G28
SDCARD_PRINT_FILE FILENAME=colour-change.gcode
