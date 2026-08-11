; SUBLEQ standard library: core
;
; Provides arithmetic, data movement, and conditional branches.
;
; Required program cells:
;   z:  .word 0
;
; `z` is scratch storage but every macro restores it to zero. Operations that
; need positive or negative one use the program's immediate-literal pool. This
; module emits no words.

; Jump unconditionally to `target`.
; Instructions: 1. Changes: no data cells (`z` remains zero).
.macro jmp target
    subleq z, z, target
.endm

; Set `target` to zero.
; Instructions: 1. Changes: `target`.
.macro clr target
    subleq target, target, ?
.endm

; Compute `destination = destination - source`.
; Instructions: 1. Changes: `destination`.
.macro sub source, destination
    subleq source, destination, ?
.endm

; Compute `destination = destination + source` without changing `source`.
; Instructions: 3. Changes: `destination`; uses `z` as restored scratch.
.macro add source, destination
    sub source, z
    sub z, destination
    clr z
.endm

; Copy `source` into `destination`.
; Instructions: 4. Changes: `destination`; uses `z` as restored scratch.
.macro cpy source, destination
    clr destination
    add source, destination
.endm

; Decrement `target` by one.
; Instructions: 1. Changes: `target`.
.macro dec target
    sub #1, target
.endm

; Increment `target` by one.
; Instructions: 1. Changes: `target`.
.macro inc target
    sub #-1, target
.endm

; Double `target` in place.
; Instructions: 3. Changes: `target`; uses `z` as restored scratch.
.macro dbl target
    add target, target
.endm

; Branch to `target` when signed `value <= 0`.
; Instructions: 1. Changes: no data cells.
.macro bleq value, target
    subleq z, value, target
.endm

; Branch to `target` when signed `value > 0`.
; Instructions: 2. Changes: no data cells.
.macro bgt value, target
    bleq value, @return
    jmp target
    @return:
.endm

; Branch to `target` when `value == 0`. The tested value is restored before
; either path continues.
; Instructions: 9. Changes: `value` temporarily, restoring it before return.
.macro beq value, target
    bgt value, @return
    inc value
    bgt value, @restore_and_jump
    dec value
    jmp @return
    @restore_and_jump:
        dec value
        jmp target
    @return:
.endm

; Branch to `target` when `value != 0`.
; Instructions: 10. Changes: `value` temporarily, restoring it before return.
.macro bne value, target
    beq value, @return
    jmp target
    @return:
.endm

; Branch to `target` when signed `value >= 0`.
; Instructions: 11. Changes: `value` temporarily, restoring it before return.
.macro bpl value, target
    bgt value, target
    beq value, target
.endm

; Branch to `target` when signed `value < 0`.
; Instructions: 10. Changes: `value` temporarily, restoring it before return.
.macro bmi value, target
    beq value, @return
    bleq value, target
    @return:
.endm
