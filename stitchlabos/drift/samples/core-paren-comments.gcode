; drift: variants=core
; drift: expect=ok
; Klipper has no (...) comments. The intake rewrites them before a job
; because "G90 (...)" is the unknown command "G90 (" and leaves the
; machine in relative mode: the second move lands at 20/20, not 10/10.
; drift: log=Unknown command:"G90 ("
; drift: log=Unknown command:"(STITCH_COUNT:3)"
; drift: log=DRIFT pos X=20.000 Y=20.000 Z=0.000 absolute=False
G28
G91
G90 (use absolute coordinates)
G1 X10 Y10 F3000
G1 X10 Y10
_DRIFT_POS
(STITCH_COUNT:3)
