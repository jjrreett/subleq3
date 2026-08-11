; SUBLEQ standard library: subroutine
;
; Provides indirect memory access, an upward-growing stack, and subroutine
; calls. Importing this module also imports <core.s>.
;
; Required program cells:
;   stack_ptr: .word stack
;   stack:     .res <capacity>
;
; The core ABI cell `z` is also required. `stack_ptr` points to the next free
; stack word. The stack has no bounds checking. Stack operations use the
; program's immediate-literal pool for positive and negative one.

.include <memory.s>

; **Destructive stack transfer.**
;
; Subtract the word addressed by `pointer` into `destination`, then clear that
; addressed word. This is the inverse of `wpt` used by `pop`; for an ordinary
; non-destructive indirect read, use `read_word` from `memory.s`.
; Changes: `destination` and the addressed word. Uses `z` (restored) and
; private code words as scratch.
.macro rpt pointer, destination
    clr @code_a
    clr @code_a0
    clr @code_a1
    sub pointer, z
    sub z, @code_a
    sub z, @code_a0
    sub z, @code_a1
    clr z
    cpy pointer, @code_a
    subleq destination, destination, @code_a

    .data
        @code_a: 0
        destination
        ?
        @code_a0: 0
        @code_a1: 0
        ?
    .endd
.endm

; Write the value in `source` to the address stored in `pointer` using
; self-modifying code. Neither input cell is changed.
; Changes: the addressed word. Uses private code words as scratch.
.macro wpt source, pointer
    cpy pointer, @code_b
    jmp @code_a

    .data
        @code_a: source
        @code_b: 0
        @code_c: ?
    .endd
.endm

; Push the value in `source`, then advance `stack_ptr`.
; Changes: `stack_ptr` and the next stack word. Uses private code as scratch.
.macro psh source
    wpt source, stack_ptr
    inc stack_ptr
.endm

; Retreat `stack_ptr`, then pop into `destination`.
; Changes: `destination`, `stack_ptr`, and the popped stack word. Uses private
; code as scratch.
.macro pop destination
    dec stack_ptr
    rpt stack_ptr, destination
.endm

; Push the return address and jump to `target`. Arguments and return values are
; passed explicitly on the data stack with `psh` and `pop`.
; Changes: `stack_ptr` and the next stack word. Uses private code as scratch.
.macro jsr target
    wpt @return_address, stack_ptr
    inc stack_ptr
    jmp target
    @return_address: .word ?
.endm

; Two-phase subroutine return. Place this at a function's entry point and jump
; back to that entry after the function body. The first pass captures the
; caller's return address; the second pass jumps to it.
; Changes: `stack_ptr`. Uses private state and code words as scratch.
.macro rts
    bleq @second_pass, @setup
    clr @second_pass
    .data
        0
        0
        @return_address: 0
        @second_pass: 0
    .endd
    @setup:
        inc @second_pass
        pop @return_address
.endm
