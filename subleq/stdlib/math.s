; SUBLEQ standard library: extended integer arithmetic
;
; Requires the core ABI cell `z` and a program-level `.literals` pool for
; immediate constants.

.include <core.s>

; `mul source, destination`
;
; Multiply `destination` by `source` using repeated addition.
; Changes: `source` and `destination`. Uses `z` (restored) and private scratch.
.macro mul source, destination
    inc source
    @loop:
        subleq #1, source, @break
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
        subleq #1, @counter, @return
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
    subleq #1, @count, @end
    jmp @rshift_start
    @shift:
        dbl source
        dbl @out

    @rshift_start:
        clr @temporary
        add source, @temporary
        subleq #-1, @temporary, @increment_out
        subleq @temporary, @temporary, @check_break

    @increment_out:
        inc @out

    @check_break:
        subleq #1, @count, @end
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

; `double_dabble_add_3 digit`
;
; Apply the add-three step used by double-dabble binary-to-decimal conversion.
; Changes: `digit`. Uses `z` (restored) and private scratch.
.macro double_dabble_add_3 digit
    cpy digit, @temporary
    subleq #4, @temporary, @return
    add #3, digit
    jmp @return

    .data @temporary: 0 .endd
    @return:
.endm

; `nibble_lslo input, output`
;
; Shift a four-bit value left, carrying overflow into `output`.
; Changes: both operands. Uses `z` (restored) and private scratch.
.macro nibble_lslo input, output
    dbl input
    cpy input, @temporary
    dbl @temporary
    dbl @temporary
    dbl @temporary
    dbl @temporary
    dbl @temporary
    dbl @temporary
    dbl @temporary
    dbl @temporary
    dbl @temporary
    dbl @temporary
    dbl @temporary
    bpl @temporary, @return
    inc output
    sub #16, input
    jmp @return

    .data @temporary: 0 .endd
    @return:
.endm

; `lslo input, output`
;
; Shift a 16-bit value left, carrying its most-significant bit into `output`.
; Changes: both operands.
.macro lslo input, output
    bpl input, @shift
    inc output
    @shift:
        dbl input
.endm
