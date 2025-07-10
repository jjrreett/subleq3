

.macro jmp a
    subleq z, z, a
.endm

.macro clr a
    subleq a, a, ?
.endm

.macro sub a b
    subleq a, b, ?
.endm

######## b = b + a ########
.macro add a b
    sub a, z
    sub z, b
    clr z
.endm


######## b = a ########
.macro cpy a b
    clr b
    add a, b
.endm


######## a = a - 1 ########
.macro dec a
    sub p1, a
.endm

######## a = a + 1 ########
.macro inc a
    sub m1, a
.endm

## Branches
#
# Branch instructions change control flow based on flag conditions.
# 
# Op Code | Instruction                 | Affected Flags
# --------|-----------------------------|----------------
# BCC     | Branch if Carry Clear       | -
# BCS     | Branch if Carry Set         | -
# BEQ     | Branch if Zero Set          | -
# BMI     | Branch if Negative Set      | -
# BNE     | Branch if Zero Clear        | -
# BPL     | Branch if Negative Clear    | -
# BVC     | Branch if Overflow Clear    | -
# BVS     | Branch if Overflow Set      | -

######## if a <= 0: jmp b ########
.macro bleq a b
    subleq z, a, b
.endm

######## if a > 0: jmp b ########
.macro bgt a b
                            # not(a <= 0) -> jump
    bleq a, return        # a <= 0, don't take the jump to b
    jmp b
return:
.endm

######## if a == 0: jmp b ########
.macro beq a b
                            # not(a > 0) and (a+1 > 0) -> jump
    bgt a, return          # a > 0, do not jump
    inc a
    bgt a, decjump         # a+1 > 0, jump
    dec a                  # fall through to de-increment a
    jmp return
decjump:
    dec a
    jmp b
return:
.endm

######## if a >= 0: jmp b ########
.macro bpl a b
                            # (a > 0) or (a == 0) -> jump
    bgt a, b              # a > 0, jump
    beq a, b              # a == 0, jump
.endm

######## if a <  0: jmp b ########
.macro bmi a b
                            # not(a == 0) and (a <= 0) -> jump
    beq a, return         # a == 0: therefor not a < 0, return
    bleq a, b             # a <= 0, but not 0 -> a < 0, take the jump
    return:
.endm



######## b = b * a ########
.macro mul a b
        inc a
    loop:
        subleq p1, a, break           # decrement 'a' by 1, break if 0
        add b, tmp
        jmp loop
    break:
        clr b
        add tmp, b
        jmp return 

    .data tmp: 0 .endd
    return:
.endm

######## a = a + a ########
.macro dbl a

    add a, a
.endm

######## b = b << a ########
.macro lsl a b

        cpy a, counter
        inc counter
    loop:
        subleq p1, counter, return         # decrement counter by 1, return if 0
        dbl b
        jmp loop
    .data counter: 0 .endd
    return:
.endm


######## b = b >> a ########
.macro lsr a b
        add literal_16, count
        sub b, count
        inc count
        subleq p1, count, end           # if count is <= 1: end
        jmp rshift_start
    shift:
        dbl a
        dbl out


    rshift_start:
        clr tmp
        add a, tmp
        subleq m1, tmp, inc_out          # if the first bit of a is 1, inc out else shift
        subleq tmp, tmp, check_break

    inc_out:
        inc out

    check_break:
        subleq p1, count, end           # if count is <= 1: end
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

####### b = b * a ######### WIP
.macro fmul a b
    while:
        bleq b, return           # if b <= 0: return
        cpy b, tmp
        lsl literal_15, tmp
        bpl tmp, shift          # if b & 1:
        add a, result           #     result += a
        sub result, IO            
    shift:
        dbl a           # double a
        lsr p1, b   # halve b
        jmp while

    .data result: 0 tmp: 0 .endd
    return:
        cpy result, b

.endm





# dest is the place where we want the value
# ptr is the addrs of the -value (as long as we negate the number going in, we can negate it going out)
# executes the date block, falls through
######## dest = *ptr ########
.macro rpt ptr dest
    clr code_a
    clr code_a0
    clr code_a1
    sub ptr, z
    sub z, code_a
    sub z, code_a0
    sub z, code_a1
    clr z
    cpy ptr, code_a
    subleq dest, dest, code_a     # clear dest and jump code_a

    .data
        # Two self modifying instructions
        code_a: 0                # dest -= *code_a
                dest
                ?
       code_a0: 0                # clr *code_a
       code_a1: 0
                ?
    .endd
.endm

######## *ptr = src ########
.macro wpt src ptr
    cpy ptr, code_b
    jmp code_a

    .data
        code_a:  src              # This will become: subleq val, dest, ...
        code_b:  0
        code_c:  ?                # next instruction
    .endd
.endm

.macro psh a
    wpt a, stack_ptr
    inc stack_ptr
.endm

.macro pop a
    dec stack_ptr
    rpt stack_ptr, a
.endm

.macro jsr func_addr
    wpt return_addr, stack_ptr
    inc stack_ptr
    jmp func_addr
    .data return_addr: ? .endd
.endm

# This isn't exactly how return from subroutine typically works
# the first pass pops the return addr off the stack
# the second pass actually returns
.macro rts

        bleq second_pass, setup       # if second_pass <= 0 then jmp to setup 
        clr second_pass               #     else clean up second_pass and ...
        .data
            0                         # self modifying jmp to return_addr
            0
            return_addr: 0

            second_pass: 0            # flag to branch on rerun
        .endd
    setup:
        inc second_pass
        pop return_addr             # pop the return addr from the stack and put into self modifying jmp
.endm

######## 4 bit shift, inc output if overflow ########
.macro byte_lshift_o input output

                           
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
        sub literal_16, input
    no_overflow:
.endm

######## 8 bit shift, inc output if overflow ########
.macro half_word_lshift_overflow input output
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
        sub literal_256, input
    no_overflow:
.endm

######## 16 bit shift, inc output if overflow ########
.macro lshift_overflow input output
        bpl input, no_overflow
        inc output             # inc output if overflow, always shift input
    no_overflow:
        dbl input
.endm


.macro newline
    sub ascii_lf, IO
    sub ascii_cr, IO
.endm

.macro double_dabble_add_3 x
    cpy x, tmp
    subleq literal_4, tmp, return      # if x ≤ 4, skip
    add literal_3, x                  # else x += 3
    jmp return
    .data tmp: 0 .endd
return:
.endm

################################################
#################### CODE ######################
################################################
jmp test

# ALIGNMENT
.data 
    0     # IO
    0     # INSPECT
.endd                    



func_print_bin:
    rts
    pop func_print_bin_a
    cpy literal_16, func_print_bin_counter
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
    cpy literal_16, counter

func_print_dec_shift:
    double_dabble_add_3 thou
    double_dabble_add_3 hund
    double_dabble_add_3 tens
    double_dabble_add_3 ones

    dbl tthou
    byte_lshift_o thou, tthou
    byte_lshift_o hund, thou
    byte_lshift_o tens, hund
    byte_lshift_o ones, tens
    lshift_overflow input, ones

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

    
test:    
    clr input
    sub IO, input
    psh input
    jsr func_print_dec
    jmp test




.data
    counter: 16

    a: 0
    b: 0
    c: 0
    d: 0
    input: 0
    stack: 0 0 0 0 0 0 0 0 0 0
    stack_ptr: stack
    dest: 0

    z: 0
    p1: 1
    m1: -1

    tmp: 0

    literal_2: 2
    literal_3: 3
    literal_4: 4
    literal_5: 5
    literal_16: 16
    literal_15: 15
    literal_256: 256

    ascii_lf: 10
    ascii_cr: 13
    ascii_0: 48
    ascii_1: 49
.endd
