; drift: variants=core
; drift: expect=ok
; Without the machine's macros these are unknown to Klipper. M00 is its own
; command, not M0, so the machine defines both (embroidery_macros.cfg).
; drift: log=Unknown command:"M00"
; drift: log=Unknown command:"M0"
; drift: log=Unknown command:"M2"
; drift: log=Unknown command:"M600"
; drift: log=Unknown command:"COLOR_CHANGE"
G28
M00
M0
M2
M600
COLOR_CHANGE
