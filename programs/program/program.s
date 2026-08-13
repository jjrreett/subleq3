.bootstrap

.res 1


;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;;;;;;;;;;;;;;;;;;;; CODE ;;;;;;;;;;;;;;;;;;;;;;
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

.include <subroutine.s>
.include <io.s>
.include <math.s>

.include <print.s>


main:
    print_asciiz boot_prompt
    jmp test

test:
    print_asciiz input_prompt
    clr input
    sub IO, input
    psh input
    jsr func_print_dec
    jmp test



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
.literals 16
boot_prompt: .asciiz "Welcome to the Subleq CPU Emulator!\n"
input_prompt: .asciiz "> "

