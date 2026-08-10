; SUBLEQ standard library: subroutine
;
; Provides indirect memory access, an upward-growing stack, and subroutine
; calls. Importing this module also imports <core.s>.
;
; Required program cells:
;   stack_ptr: .word stack
;   stack:     .res <capacity>
;
; The core ABI cells `z`, `p1`, and `m1` are also required. `stack_ptr` points
; to the next free stack word. The stack has no bounds checking.

.include <core.s>

; `rpt pointer, destination`
;
; Read the word addressed by `pointer` into `destination` using self-modifying
; code. The pointer cell is not changed.
; Clobbers: `destination`, `z` (restored), macro-private code words.
.macro rpt, pointer, destination
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

; `wpt source, pointer`
;
; Write the value in `source` to the address stored in `pointer` using
; self-modifying code. Neither input cell is changed.
; Clobbers: macro-private code words.
.macro wpt, source, pointer
    cpy pointer, @code_b
    jmp @code_a

    .data
        @code_a: source
        @code_b: 0
        @code_c: ?
    .endd
.endm

; `psh source`
;
; Push the value in `source`, then advance `stack_ptr`.
; Clobbers: the next stack word, `stack_ptr`, macro-private code words.
.macro psh, source
    wpt source, stack_ptr
    inc stack_ptr
.endm

; `pop destination`
;
; Retreat `stack_ptr`, then pop into `destination`.
; Clobbers: `destination`, `stack_ptr`, macro-private code words.
.macro pop, destination
    dec stack_ptr
    rpt stack_ptr, destination
.endm

; `jsr target`
;
; Push the return address and jump to `target`. Arguments and return values are
; passed explicitly on the data stack with `psh` and `pop`.
; Clobbers: `stack_ptr`, the next stack word, macro-private code words.
.macro jsr, target
    wpt @return_address, stack_ptr
    inc stack_ptr
    jmp target
@return_address: .word ?
.endm

; `rts`
;
; Two-phase subroutine return. Place this at a function's entry point and jump
; back to that entry after the function body. The first pass captures the
; caller's return address; the second pass jumps to it.
; Clobbers: `stack_ptr`, macro-private state and code words.
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
