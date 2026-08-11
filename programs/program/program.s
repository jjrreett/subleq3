.include <subroutine.s>
.include <io.s>
.include <math.s>

;;;;;;; b = b * a ;;;;;;;;; WIP
.macro fmul, a, b
    @while:
        bleq b, @return                    ; if b <= 0: return
        cpy b, @temporary
        lsl #15, @temporary
        bpl @temporary, @shift             ; if b & 1:
        add a, @result                     ; result += a
        sub @result, IO
    @shift:
        dbl a                              ; double a
        lsr #1, b                          ; halve b
        jmp @while

        .data
            @result: 0
            @temporary: 0
        .endd

    @return:
        cpy @result, b

.endm




;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;;;;;;;;;;;;;;;;;;;; CODE ;;;;;;;;;;;;;;;;;;;;;;
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
.bootstrap

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

.byte $ff
.word $1234
.dword $12345678
.ascii "Hello"
.asciiz "World"
.fill 10, $0000
.res 10
