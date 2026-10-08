; Synthetic job with an Ink/Stitch colour change (M00). On the machine the
; colour change pauses the job, so the probe after it must not run.
G90 ; use absolute coordinates
G21 ; coordinates will be specified in millimeters
G0 X10.000 Y10.000
G0 Z5.0
G0 X12.500 Y10.000
G0 Z10.0
M00
G0 X20.000 Y20.000
G0 Z15.0
_DRIFT_POS
G0 X0.0 Y0.0
M30
