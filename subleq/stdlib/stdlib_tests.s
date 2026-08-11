; Executable test harnesses for the packaged standard library.
;
; Run from the project root with:
;   subleq test subleq/stdlib/stdlib_tests.s

.include <subroutine.s>
.include <io.s>
.include <math.s>

.test "core/add and copy"
    .bootstrap
main:
    cpy left, result
    add right, result
    jmp halt
halt:
    subleq z, z, 0
z:      .word 0
left:   .word 19
right:  .word 23
result: .word 0
    .assert result, 42
    .assert z, 0
.endt

.test "math/double dabble add three"
    .bootstrap
main:
    double_dabble_add_3 low_digit
    double_dabble_add_3 high_digit
    jmp halt
halt:
    subleq z, z, 0
z:          .word 0
low_digit:  .word 4
high_digit: .word 5
.literals 2
    .assert low_digit, 4
    .assert high_digit, 8
.endt

.test "memory/non-destructive read"
    .bootstrap
main:
    read_word pointer, destination
    jmp halt
halt:
    subleq z, z, 0
z:           .word 0
source:      .word $1234
pointer:     .word source
destination: .word 0
    .assert source, $1234
    .assert destination, $1234
.endt

.test "subroutine/stack round trip"
    .bootstrap
double:
    rts
    pop argument
    dbl argument
    psh argument
    jmp double
main:
    psh input
    jsr double
    pop output
    jmp halt
halt:
    subleq z, z, 0
z:         .word 0
input:     .word 21
output:    .word 0
argument:  .word 0
stack:     .res 16
stack_ptr: .word stack
.literals 2
    .assert output, 42
    .assert stack_ptr, stack
.endt

.test "io/string and newline"
    .bootstrap
main:
    print_asciiz message
    newline
    jmp halt
halt:
    subleq z, z, 0
z:       .word 0
message: .asciiz "OK"
.literals 4
    .assert-output "OK\n\r"
.endt

.test "print/binary and decimal"
    .bootstrap
    .include <print.s>
main:
    psh value
    jsr func_print_bin
    psh value
    jsr func_print_dec
    jmp halt
halt:
    subleq z, z, 0
z:         .word 0
value:     .word 42
stack:     .res 16
stack_ptr: .word stack
.literals 16
    .assert-output "0000000000101010\n\r00042\n\r"
.endt
