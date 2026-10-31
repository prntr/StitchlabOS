; drift: variants=core
; drift: expect=error
; A (...) comment behind move parameters stops the job.
; drift: log=Unable to parse move
G28
G1 X10 Y10 (comment)
