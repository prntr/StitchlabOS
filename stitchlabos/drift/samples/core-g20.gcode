; drift: variants=core
; drift: expect=error
; The intake blocks G20 because Klipper rejects it.
; drift: log=Machine does not support G20 (inches) command
G28
G20
