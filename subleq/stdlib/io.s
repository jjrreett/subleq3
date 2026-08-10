; SUBLEQ standard library: character output
;
; Required program cells:
;   IO: address 3 memory-mapped I/O cell
;   z:  .word 0
;
; Programs using `newline` must provide a `.literals` pool for #10 and #13.

.include <memory.s>

; `newline`
;
; Write line-feed and carriage-return characters to `IO`.
; Clobbers: `IO` device side effects only.
.macro newline
    sub #10, IO
    sub #13, IO
.endm

; `print_asciiz string`
;
; Write a null-terminated string to `IO`. The pointer is reset each time the
; expansion executes, so a call site can run repeatedly.
; Clobbers: `IO`, `z` (restored), macro-private pointer and character cells.
.macro print_asciiz, string
    cpy @string_address, @pointer
@next:
    read_word @pointer, @character
    beq @character, @return
    sub @character, IO
    inc @pointer
    jmp @next

    .data
        @string_address: string
        @pointer: 0
        @character: 0
    .endd
@return:
.endm
