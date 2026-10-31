; drift: variants=image,hybrid
; drift: expect=error
; A needle macro inside a job stops the job with an error (batch mode then
; exits); the intake blocks such files as NEEDLE_MACRO_IN_JOB.
; drift: log=Starting SD card print
; drift: log=STITCH refused: a job is printing
; drift: nolog=DRIFT pos X=12.000
G28
SDCARD_PRINT_FILE FILENAME=needle-macro.gcode
