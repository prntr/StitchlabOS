; Synthetic job with a panel macro inside: the machine refuses STITCH while
; a job prints (beta6 contract), so the job stops there and the probe after
; it must not run. The intake blocks such files before they start.
G90
G21
G0 X10.000 Y10.000
G0 Z5.0
STITCH
G0 X12.000 Y10.000
_DRIFT_POS
M30
