; drift: variants=core
; drift: expect=error
; virtual_sdcard registers M30 as an error. The machine's M30 macro renames
; it (rename_existing), which needs this registration to exist.
; drift: log=SD write not supported
G28
M30
