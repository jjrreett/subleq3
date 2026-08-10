; SUBLEQ standard library: non-destructive indirect memory access
;
; Required program cells:
;   z: .word 0

; `read_word pointer, destination`
;
; Read the word addressed by `pointer` without modifying the source word.
; Clobbers: `destination`, `z` (restored), macro-private code words.
.include <core.s>

.macro read_word, pointer, destination
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
