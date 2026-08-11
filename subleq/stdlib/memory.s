; SUBLEQ standard library: non-destructive indirect memory access
;
; Required program cells:
;   z: .word 0

.include <core.s>

; `read_word pointer, destination`
;
; Read the word addressed by `pointer` without modifying the source word.
; Unlike the stack helper `rpt`, this is a non-destructive indirect read.
; Changes: `destination`. Uses `z` (restored) and private code words as scratch.
.macro read_word pointer, destination
    cpy pointer, @source
    clr destination
    clr z
    jmp @source

    .data
        @source: 0
        z
        ?
    .endd

    sub z, destination
    clr z
.endm
