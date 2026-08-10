.include <subroutine.s>


;;;;;;;; b = b * a ;;;;;;;;
.macro mul, a, b
        inc a
    loop:
        subleq p1, a, break           ; decrement 'a' by 1, break if 0
        add b, tmp
        jmp loop
    break:
        clr b
        add tmp, b
        jmp return 

    .data tmp: 0 .endd
    return:
.endm

;;;;;;;; b = b << a ;;;;;;;;
.macro lsl, a, b

        cpy a, counter
        inc counter
    loop:
        subleq p1, counter, return         ; decrement counter by 1, return if 0
        dbl b
        jmp loop
    .data counter: 0 .endd
    return:
.endm


;;;;;;;; b = b >> a ;;;;;;;;
.macro lsr, a, b
        add #16, count
        sub b, count
        inc count
        subleq p1, count, end           ; if count is <= 1: end
        jmp rshift_start
    shift:
        dbl a
        dbl out


    rshift_start:
        clr tmp
        add a, tmp
        subleq m1, tmp, inc_out          ; if the first bit of a is 1, inc out else shift
        subleq tmp, tmp, check_break

    inc_out:
        inc out

    check_break:
        subleq p1, count, end           ; if count is <= 1: end
        jmp shift

    end:
        clr b
        add out, b
        jmp return

    .data 
        count: 0
        tmp: 0
        out: 0
    .endd

    return:
.endm

;;;;;;; b = b * a ;;;;;;;;; WIP
.macro fmul, a, b
    while:
        bleq b, return           ; if b <= 0: return
        cpy b, tmp
        lsl #15, tmp
        bpl tmp, shift          ; if b & 1:
        add a, result           ;     result += a
        sub result, IO            
    shift:
        dbl a           ; double a
        lsr p1, b   ; halve b
        jmp while

    .data result: 0 tmp: 0 .endd
    return:
        cpy result, b

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
        
        bpl tmp, no_overflow
        inc output
        sub #16, input
    no_overflow:
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

        bpl tmp, return
        inc no_overflow
        sub #256, input
    no_overflow:
.endm

;;;;;;;; 16 bit shift, inc output if overflow ;;;;;;;;
.macro lslo, input, output
        bpl input, no_overflow
        inc output             ; inc output if overflow, always shift input
    no_overflow:
        dbl input
.endm


.macro newline
    sub ascii_lf, IO
    sub ascii_cr, IO
.endm

; `read_word pointer, destination`
;
; Read the word addressed by `pointer` without modifying the source word.
.macro read_word, pointer, destination
    cpy pointer, @source
    clr destination
    clr z
    jmp @source

    .data
        @source: 0
        z
        ?
    .endd

    sub z, destination
    clr z
.endm

; `print_asciiz string`
;
; Copy a null-terminated string to the memory-mapped character output.
; The pointer is reset on every expansion, so the same call can run repeatedly.
.macro print_asciiz, string
    cpy @string_address, @pointer
@next:
    read_word @pointer, @character
    beq @character, @return
    sub @character, IO
    inc @pointer
    jmp @next

    .data
        @string_address: string
        @pointer: 0
        @character: 0
    .endd
@return:
.endm

.macro double_dabble_add_3, x
    cpy x, tmp
    subleq #4, tmp, return      ; if x ≤ 4, skip
    add #3, x                  ; else x += 3
    jmp return
    .data tmp: 0 .endd
return:
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
    sub ascii_0, IO
    jmp func_print_bin_shift

func_print_bin_print_1:
    sub ascii_1, IO

func_print_bin_shift:
    subleq p1, func_print_bin_counter, func_print_bin_return
    dbl func_print_bin_a
    jmp func_print_bin_check_msb

func_print_bin_return:
    sub ascii_lf, IO
    sub ascii_cr, IO
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
    cpy ascii_0, a
    add tthou, a
    sub a, IO
    cpy ascii_0, a
    add thou, a
    sub a, IO
    cpy ascii_0, a
    add hund, a
    sub a, IO
    cpy ascii_0, a
    add tens, a
    sub a, IO
    cpy ascii_0, a
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
ascii_lf:    .word 10
ascii_cr:    .word 13
ascii_0:     .word 48
ascii_1:     .word 49
boot_prompt: .asciiz "Welcome to the Subleq CPU Emulator!\n"

.byte $ff
.word $1234
.dword $12345678
.ascii "Hello"
.asciiz "World"
.fill 10, $0000
.res 10
