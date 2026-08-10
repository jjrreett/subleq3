.include <subroutine.s>
.include <io.s>
.include <math.s>

;;;;;;; b = b * a ;;;;;;;;; WIP
.macro fmul, a, b
@while:
        bleq b, @return           ; if b <= 0: return
        cpy b, @temporary
        lsl #15, @temporary
        bpl @temporary, @shift          ; if b & 1:
        add a, @result           ;     result += a
        sub @result, IO
@shift:
        dbl a           ; double a
        lsr p1, b   ; halve b
        jmp @while

    .data @result: 0 @temporary: 0 .endd
@return:
        cpy @result, b

.endm




;;;;;;;; 4 bit shift, inc output if overflow ;;;;;;;;
.macro nibble_lslo, input, output                
        dbl input
        cpy input, tmp
        dbl tmp
        dbl tmp
        dbl tmp

        dbl tmp
        dbl tmp
        dbl tmp
        dbl tmp

        dbl tmp
        dbl tmp
        dbl tmp
        dbl tmp
        
        bpl tmp, @no_overflow
        inc output
        sub #16, input
@no_overflow:
.endm

;;;;;;;; 8 bit shift, inc output if overflow ;;;;;;;;
.macro byte_lslo, input, output
        dbl input
        cpy input, tmp
        dbl tmp
        dbl tmp
        dbl tmp

        dbl tmp
        dbl tmp
        dbl tmp
        dbl tmp

        bpl tmp, @return
        inc @no_overflow
        sub #256, input
@no_overflow:
@return:
.endm

;;;;;;;; 16 bit shift, inc output if overflow ;;;;;;;;
.macro lslo, input, output
        bpl input, @no_overflow
        inc output             ; inc output if overflow, always shift input
@no_overflow:
        dbl input
.endm


.macro double_dabble_add_3, x
    cpy x, @temporary
    subleq #4, @temporary, @return      ; if x ≤ 4, skip
    add #3, x                  ; else x += 3
    jmp @return
    .data @temporary: 0 .endd
@return:
.endm

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;;;;;;;;;;;;;;;;;;;; CODE ;;;;;;;;;;;;;;;;;;;;;;
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
jmp boot
IO:         .word $00       ; expected to be at addr 1
INSPECT:    .word $00       ; expected to be at addr 2
AC:         .word $00       ; accumulator
XR:         .word $00       ; x register
YR:         .word $00       ; y register
SP:         .word $00       ; stack pointer
SR:         .fill 146, $00  ; stack register

func_print_bin:
    rts
    pop func_print_bin_a
    cpy #16, func_print_bin_counter
func_print_bin_check_msb:
    bmi func_print_bin_a, func_print_bin_print_1

func_print_bin_print_0:
    sub #48, IO
    jmp func_print_bin_shift

func_print_bin_print_1:
    sub #49, IO

func_print_bin_shift:
    subleq p1, func_print_bin_counter, func_print_bin_return
    dbl func_print_bin_a
    jmp func_print_bin_check_msb

func_print_bin_return:
    newline
    jmp func_print_bin

.data
    func_print_bin_a: 0
    func_print_bin_counter: 0
.endd



func_print_dec:
    rts
    pop func_print_dec_input
    psh a
    psh counter
    clr ones
    clr tens
    clr hund
    clr thou
    clr tthou
    cpy #16, counter

func_print_dec_shift:
    double_dabble_add_3 thou
    double_dabble_add_3 hund
    double_dabble_add_3 tens
    double_dabble_add_3 ones

    dbl tthou
    nibble_lslo thou, tthou
    nibble_lslo hund, thou
    nibble_lslo tens, hund
    nibble_lslo ones, tens
    lslo input, ones

    subleq p1, counter, func_print_dec_cleanup
    jmp func_print_dec_shift


func_print_dec_cleanup:
    cpy #48, a
    add tthou, a
    sub a, IO
    cpy #48, a
    add thou, a
    sub a, IO
    cpy #48, a
    add hund, a
    sub a, IO
    cpy #48, a
    add tens, a
    sub a, IO
    cpy #48, a
    add ones, a
    sub a, IO
    newline

    pop a
    pop counter
    jmp func_print_dec


.data
    func_print_dec_input: 0
    ones: 0
    tens: 0
    hund: 0
    thou: 0
    tthou: 0
.endd
boot:
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
stack_ptr:  .data stack .endd
z:          .word 0
p1:         .word 1
m1:         .word -1
tmp:         .word 0
.literals
boot_prompt: .asciiz "Welcome to the Subleq CPU Emulator!\n"
input_prompt: .asciiz "> "

.byte $ff
.word $1234
.dword $12345678
.ascii "Hello"
.asciiz "World"
.fill 10, $0000
.res 10
