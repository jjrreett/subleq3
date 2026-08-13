.bootstrap

.res 1


;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;;;;;;;;;;;;;;;;;;;; CODE ;;;;;;;;;;;;;;;;;;;;;;
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

.include <subroutine.s>
.include <io.s>
.include <math.s>

.include <print.s>

handle_input:
    rts
    pop @input
    dbl @input
    add @input, board_pointer
    sub 'X, tmp
    cpt board_pointer
    wpt tmp, board_pointer
    clr tmp
    sub @input, board_pointer
    jmp handle_input    ; jump back to the start of the routine to rerun rts to return to the caller

    .data
        @input: 0
    .endd
    .res 2

main:
    print_asciiz board
    print_asciiz input_prompt
    clr input
    sub IO, input
    psh input
    jsr handle_input
    jmp main





.literals 16
counter:    .word 16
a:          .word 0
b:          .word 0
c:          .word 0
d:          .word 0
input:      .word 0
stack:      .res 256
stack_ptr:  .word stack
z:          .word 0
tmp:         .word 0
ascii_zero: .word 48

board: .asciiz "0 1 2\n3 4 5\n6 7 8\n"
board_pointer: .word board
input_prompt: .asciiz "> "

literal_x: .char 'X'

