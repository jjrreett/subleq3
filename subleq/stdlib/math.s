; SUBLEQ standard library: extended integer arithmetic
;
; Requires the core ABI cell `z` and a program-level `.literals` pool for
; immediate constants.

.include <core.s>

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

; Multiply `multiplier` by `multiplicand` using binary shift-and-add.
; Changes: both operands. Uses `z` (restored) and private scratch.
.macro fmul multiplicand, multiplier
    clr @result
    @while:
        bleq multiplier, @return
        cpy multiplier, @remainder
        clr @quotient
    @halve:
        beq @remainder, @shift
        dec @remainder
        beq @remainder, @odd
        dec @remainder
        inc @quotient
        jmp @halve
    @odd:
        add multiplicand, @result
    @shift:
        cpy @quotient, multiplier
        dbl multiplicand
        jmp @while

        .data
            @result: 0
            @remainder: 0
            @quotient: 0
        .endd
    @return:
        cpy @result, multiplier
.endm

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

; Shift a 16-bit value left, carrying its most-significant bit into `output`.
; Changes: both operands.
.macro lslo input, output
    bpl input, @shift
    inc output
    @shift:
        dbl input
.endm
