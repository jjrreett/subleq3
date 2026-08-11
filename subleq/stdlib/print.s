; SUBLEQ standard library: integer output subroutines
;
; Include this runtime module after the program's reset jump and fixed I/O
; cells because, unlike the macro-only modules, it emits executable words.
;
; Required program cells:
;   IO:        address 3 memory-mapped I/O cell
;   z:         .word 0
;   stack:     .res <capacity>
;   stack_ptr: .word stack
;
; The program must also reserve a sufficiently large `.literals` pool.

.include <subroutine.s>
.include <io.s>
.include <math.s>

; `func_print_bin`
;
; Pop one 16-bit value, print all 16 binary digits followed by a newline, and
; return. The argument is consumed and there is no result.
func_print_bin:
    rts
    pop @value
    cpy #16, @counter
    @check_msb:
        bmi @value, @print_one
        sub #48, IO
        jmp @shift
    @print_one:
        sub #49, IO
    @shift:
        subleq #1, @counter, @return
        dbl @value
        jmp @check_msb
    @return:
        newline
        jmp func_print_bin

        .data
            @value: 0
            @counter: 0
        .endd

; `func_print_dec`
;
; Pop one unsigned 16-bit value, print all five decimal digits (including
; leading zeroes) followed by a newline, and return. The argument is consumed
; and there is no result.
func_print_dec:
    rts
    pop @input
    clr @ones
    clr @tens
    clr @hundreds
    clr @thousands
    clr @ten_thousands
    cpy #16, @counter
    @shift:
        double_dabble_add_3 @thousands
        double_dabble_add_3 @hundreds
        double_dabble_add_3 @tens
        double_dabble_add_3 @ones

        dbl @ten_thousands
        nibble_lslo @thousands, @ten_thousands
        nibble_lslo @hundreds, @thousands
        nibble_lslo @tens, @hundreds
        nibble_lslo @ones, @tens
        lslo @input, @ones

        subleq #1, @counter, @print
        jmp @shift
    @print:
        cpy #48, @character
        add @ten_thousands, @character
        sub @character, IO
        cpy #48, @character
        add @thousands, @character
        sub @character, IO
        cpy #48, @character
        add @hundreds, @character
        sub @character, IO
        cpy #48, @character
        add @tens, @character
        sub @character, IO
        cpy #48, @character
        add @ones, @character
        sub @character, IO
        newline
        jmp func_print_dec

        .data
            @input: 0
            @counter: 0
            @character: 0
            @ones: 0
            @tens: 0
            @hundreds: 0
            @thousands: 0
            @ten_thousands: 0
        .endd
