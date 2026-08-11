.macro jmp a       ; 1 instruction
    subleq z, z, a
.endm

.macro clr a       ; 1 instruction
    subleq a, a, ?
.endm

.macro sub a, b    ; 1 instruction
    subleq a, b, ?
.endm

;;;;;;;; b = b + a ;;;;;;;;
.macro add a, b    ; 3 instruction
    sub a, z
    sub z, b
    clr z
.endm

;;;;;;;; b = a ;;;;;;;;
.macro cpy a, b    ; 4 instructions
    clr b
    add a, b
.endm


;;;;;;;; a = a - 1 ;;;;;;;;
.macro dec a       ; 1 instruction
    sub p1, a
.endm

;;;;;;;; a = a + 1 ;;;;;;;;
.macro inc a       ; 1 instruction
    sub m1, a
.endm

;; Branches
;
; Branch instructions change control flow based on flag conditions.
; 
; Op Code | Instruction                 | Affected Flags
; --------|-----------------------------|----------------
; BCC     | Branch if Carry Clear       | -
; BCS     | Branch if Carry Set         | -
; BEQ     | Branch if Zero Set          | -
; BMI     | Branch if Negative Set      | -
; BNE     | Branch if Zero Clear        | -
; BPL     | Branch if Negative Clear    | -
; BVC     | Branch if Overflow Clear    | -
; BVS     | Branch if Overflow Set      | -

;;;;;;;; if a <= 0: jmp b ;;;;;;;;
.macro bleq a, b       ; 1 instruction
    subleq z, a, b
.endm

;;;;;;;; if a > 0: jmp b ;;;;;;;;
.macro bgt a, b        ; 2 instructions
                        ; not(a <= 0) -> jump
        bleq a, @return  ; a <= 0, don't take the jump to b
        jmp b
    @return:
.endm

;;;;;;;; if a == 0: jmp b ;;;;;;;;
.macro beq a, b        ; 9 instructions
                           ; not(a > 0) and (a+1 > 0) -> jump
            bgt a, @return          ; a > 0, do not jump
            inc a
            bgt a, @decjump         ; a+1 > 0, jump
            dec a                  ; fall through to de-increment a
            jmp @return
    @decjump:
            dec a
            jmp b
    @return:
.endm

;;;;;;; if a != 0: jmp b ;;;;;;;;
.macro bne a, b        ; 10 instructions
            beq a, @return
            jmp b
    @return:
.endm
;;;;;;;; if a >= 0: jmp b ;;;;;;;;
.macro bpl a, b        ; 11 instructions
                            ; (a > 0) or (a == 0) -> jump
    bgt a, b                ; a > 0, jump
    beq a, b                ; a == 0, jump
.endm

;;;;;;;; if a <  0: jmp b ;;;;;;;;
.macro bmi a, b        ; 10 instructions
                            ; not(a == 0) and (a <= 0) -> jump
    beq a, @return           ; a == 0: therefor not a < 0, return
    bleq a, b               ; a <= 0, but not 0 -> a < 0, take the jump
    @return:
.endm


;;;;;;;; b = b * a ;;;;;;;;
.macro mul a, b
        inc a
    @loop:
        subleq p1, a, @break           ; decrement 'a' by 1, break if 0
        add b, @tmp
        jmp @loop
    @break:
        clr b
        add @tmp, b
        jmp @return 

    @tmp: .word 0
    @return:
.endm

;;;;;;;; a = a + a ;;;;;;;;
.macro dbl a
    add a, a
.endm

;;;;;;;; b = b << a ;;;;;;;;
.macro lsl a, b
        cpy a, @counter
        inc @counter
    @loop:
        subleq p1, @counter, @return         ; decrement counter by 1, return if 0
        dbl b
        jmp loop
    @counter: .word 0
    @return:
.endm


;;;;;;;; b = b >> a ;;;;;;;;
.macro lsr a, b
        add literal_16, @count
        sub b, @count
        inc @count
        subleq p1, @count, @end           ; if count is <= 1: end
        jmp @rshift_start
    @shift:
        dbl a
        dbl @out


    @rshift_start:
        clr tmp
        add a, tmp
        subleq m1, tmp, @inc_out          ; if the first bit of a is 1, inc out else shift
        subleq tmp, tmp, @check_break

    @inc_out:
        inc @out

    @check_break:
        subleq p1, @count, @end           ; if count is <= 1: end
        jmp @shift

    @end:
        clr b
        add @out, b
        jmp @return

    @count: .word 0
    @tmp: .word 0
    @out: .word 0
    @return:
.endm



; dest is the place where we want the value
; ptr is the addrs of the -value (as long as we negate the number going in, we can negate it going out)
; executes the date block, falls through
;;;;;;;; dest = *ptr ;;;;;;;;
.macro rpt ptr, dest
    clr @code_a
    clr @code_a0
    clr @code_a1
    sub ptr, z
    sub z, @code_a
    sub z, @code_a0
    sub z, @code_a1
    clr z
    cpy ptr, @code_a
    subleq dest, dest, @code_a     ; clear dest and jump code_a

    .data
        ; Two self modifying instructions
        @code_a: 0                ; dest -= *code_a
                dest
                ?
       @code_a0: 0                ; clr *code_a
       @code_a1: 0
                ?
    .endd
.endm

;;;;;;;; *ptr = src ;;;;;;;;
.macro wpt src, ptr
    cpy ptr, @code_b
    jmp @code_a

    @code_a:  .word src              ; This will become: subleq val, dest, ...
    @code_b:  .word 0
    @code_c:  .word ?                ; next instruction
.endm

.macro psh a
    wpt a, SP
    inc SP
.endm

.macro pop a
    dec SP
    rpt SP, a
.endm

.macro jsr func_addr
    wpt @return_addr, SP
    inc SP
    jmp func_addr
@return_addr: .word ?
.endm

; This isn't exactly how return from subroutine typically works
; the first pass pops the return addr off the stack
; the second pass actually returns
.macro rts
        bleq @second_pass, setup       ; if second_pass <= 0 then jmp to setup 
        clr @second_pass              ;     else clean up second_pass and ...
        .word 0                         ; self modifying jmp to return_addr
        .word 0
        @return_addr: .word 0

        @second_pass: .word 0            ; flag to branch on rerun
    setup:
        inc @second_pass
        pop @return_addr             ; pop the return addr from the stack and put into self modifying jmp
.endm

;;;;;;;; 4 bit shift, inc output if overflow ;;;;;;;;
.macro nibble_lslo input, output
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
        sub literal_16, input
    @no_overflow:
.endm

;;;;;;;; 8 bit shift, inc output if overflow ;;;;;;;;
.macro byte_lslo input, output
        dbl input
        cpy input, tmp
        dbl tmp
        dbl tmp
        dbl tmp

        dbl tmp
        dbl tmp
        dbl tmp
        dbl tmp

        bpl tmp, @no_overflow
        inc @no_overflow
        sub literal_256, input
    @no_overflow:
.endm

;;;;;;;; 16 bit shift, inc output if overflow ;;;;;;;;
.macro lslo input, output
        bpl input, @no_overflow
        inc output             ; inc output if overflow, always shift input
    @no_overflow:
        dbl input
.endm


.macro newline
    sub ascii_lf, IO
    sub ascii_cr, IO
.endm

.macro double_dabble_add_3 x
        cpy x, @tmp
        subleq literal_4, @tmp, @return      ; if x ≤ 4, skip
        add literal_3, x                  ; else x += 3
        jmp @return
        @tmp: .word 0
    @return:
.endm


func_print_dec:
        rts
        pop                     @input
        psh                     AC
        psh                     XR
        clr                     @ones
        clr                     @tens
        clr                     @hund
        clr                     @thou
        clr                     @tthou
        cpy                     literal_16, XR

    @shift:
        double_dabble_add_3     @thou
        double_dabble_add_3     @hund
        double_dabble_add_3     @tens
        double_dabble_add_3     @ones

        dbl                     @tthou
        nibble_lslo             @thou,  @tthou
        nibble_lslo             @hund,  @thou
        nibble_lslo             @tens,  @hund
        nibble_lslo             @ones,  @tens
        lslo                    @input, @ones

        subleq                  p1, XR, @print
        jmp @shift

    @print:
        cpy           ascii_0,    a
        add           @tthou,     a
        sub           a,          IO
        cpy           ascii_0,    a
        add           @thou,      a
        sub           a,          IO
        cpy           ascii_0,    a
        add           @hund,      a
        sub           a,          IO
        cpy           ascii_0,    a
        add           @tens,      a
        sub           a,          IO
        cpy           ascii_0,    a
        add           @ones,      a
        sub           a,          IO
        newline
        pop           a
        pop           counter
        jmp           func_print_dec

    @input:           .word 0
    @ones:            .word 0
    @tens:            .word 0
    @hund:            .word 0
    @thou:            .word 0
    @tthou:           .word 0



;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;;;;;;;;;;;;;;;;;;;; CODE ;;;;;;;;;;;;;;;;;;;;;;
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
jmp start
IO:         .word $00       ; expected to be at addr 3
INSPECT:    .word $00       ; expected to be at addr 4
AC:         .word $00       ; accumulator
XR:         .word $00       ; x register
YR:         .word $00       ; y register
SP:         .word $00       ; stack pointer
SR:         .fill 5, $00  ; stack register
_20:        .word -20
z:          .word 0
m1:         .word -1
p1:         .word 1
counter:    .word 16
a:          .word 0
tmp:        .word 0
literal_3:  .word 3
literal_4:  .word 4
literal_16: .word 16
literal_256: .word 256
ascii_lf:   .word 10
ascii_cr:   .word 13
ascii_0:    .word 48

start:
            sub AC, INSPECT
            inc AC


Clear:  clr    AC               ; Global label
        sub    _20, YR
@Loop:  add    YR, AC            ; Local label
        dec    YR
        sub    AC, INSPECT
        bne    YR, @Loop            ; Ok
Sub:                            ; New global label
@Loop:  bne    YR, @Loop        ; Distinct from Clear's local @Loop
