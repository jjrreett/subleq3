; SUBLEQ standard library: extended integer arithmetic
;
; Requires the core ABI cells `z`, `p1`, and `m1`. Immediate shifts require a
; program-level `.literals` pool.

.include <core.s>

; `mul source, destination`
;
; Multiply `destination` by `source` using repeated addition.
; Changes: `source` and `destination`. Uses `z` (restored) and private scratch.
.macro mul source, destination
    inc source
@loop:
    subleq p1, source, @break
    add destination, @temporary
    jmp @loop
@break:
    clr destination
    add @temporary, destination
    jmp @return

    .data @temporary: 0 .endd
@return:
.endm

; `lsl count, value`
;
; Shift `value` left by `count` bits.
; Changes: `value`. Uses `z` (restored) and a private counter.
.macro lsl count, value
    cpy count, @counter
    inc @counter
@loop:
    subleq p1, @counter, @return
    dbl value
    jmp @loop

    .data @counter: 0 .endd
@return:
.endm

; `lsr source, value`
;
; Shift `value` right using `source` as the working bit accumulator.
; Changes: both operands. Uses `z` (restored) and private scratch.
.macro lsr source, value
    add #16, @count
    sub value, @count
    inc @count
    subleq p1, @count, @end
    jmp @rshift_start
@shift:
    dbl source
    dbl @out

@rshift_start:
    clr @temporary
    add source, @temporary
    subleq m1, @temporary, @increment_out
    subleq @temporary, @temporary, @check_break

@increment_out:
    inc @out

@check_break:
    subleq p1, @count, @end
    jmp @shift

@end:
    clr value
    add @out, value
    jmp @return

    .data
        @count: 0
        @temporary: 0
        @out: 0
    .endd
@return:
.endm
