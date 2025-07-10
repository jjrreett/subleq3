# 6502 Instructions

## The Instruction Set

The 6502 has a relatively basic set of instructions, many having similar functions (e.g. memory access, arithmetic, etc.). The following sections list the complete set of 56 instructions in functional groups.

### Load/Store Operations

These instructions transfer a single byte between memory and one of the registers.
Load operations set the negative ([N](http://www.6502.org/users/obelisk/6502/registers.html#N)) and zero ([Z](http://www.6502.org/users/obelisk/6502/registers.html#Z)) flags depending on the value of transferred.
Store operations do not affect the flag settings.

Op Code | Instruction       | Affected Flags
------- | ----------------- | -------------
LDA     | Load Accumulator  | NZ
LDX     | Load X Register   | NZ
LDY     | Load Y Register   | NZ
STA     | Store Accumulator | -
STX     | Store x Register  | -
STY     | Store Y Register  | -

### Register Transfers

The contents of the X and Y registers can be moved to or from the accumulator, setting the negative ([N](http://www.6502.org/users/obelisk/6502/registers.html#N)) and zero ([Z](http://www.6502.org/users/obelisk/6502/registers.html#Z)) flags as appropriate.

Op Code | Instruction                 | Affected Flags
--------|-----------------------------|----------------
TAX     | Transfer Accumulator to X   | N Z
TAY     | Transfer Accumulator to Y   | N Z
TXA     | Transfer X to Accumulator   | N Z
TYA     | Transfer Y to Accumulator   | N Z

### Stack Operations

The 6502 microprocessor supports a 256-byte stack fixed between memory locations $0100 and $01FF. A special 8-bit register, S, is used to keep track of the next free byte of stack space.  
Pushing a byte onto the stack stores it at the current free location and then decrements the stack pointer.  
Pull operations reverse this.  
The stack register can only be accessed via the X register. It is modified automatically by push/pull instructions, subroutine calls/returns, and interrupt handling.

Op Code | Instruction                      | Affected Flags
--------|----------------------------------|----------------
TSX     | Transfer Stack Pointer to X      | N Z
TXS     | Transfer X to Stack Pointer      | –
PHA     | Push Accumulator on Stack        | –
PHP     | Push Processor Status on Stack   | –
PLA     | Pull Accumulator from Stack      | N Z
PLP     | Pull Processor Status from Stack | All

### Logical

These instructions perform logical operations on the accumulator and memory values.  
The `BIT` instruction performs a logical AND to set flags but does not store the result.

Op Code | Instruction            | Affected Flags
--------|------------------------|----------------
AND     | Logical AND            | N Z
EOR     | Exclusive OR           | N Z
ORA     | Logical Inclusive OR   | N Z
BIT     | Bit Test               | N V Z

### Arithmetic Instructions

The arithmetic operations perform addition and subtraction on the accumulator.  
Compare instructions test the relationship between registers and memory values and affect flags accordingly.

Op Code | Instruction         | Affected Flags
--------|---------------------|----------------
ADC     | Add with Carry      | N V Z C
SBC     | Subtract with Carry | N V Z C
CMP     | Compare Accumulator | N Z C
CPX     | Compare X Register  | N Z C
CPY     | Compare Y Register  | N Z C

### Increments & Decrements

These instructions increment or decrement memory or register values by one.  
They set the negative (N) and zero (Z) flags based on the result.

Op Code | Instruction             | Affected Flags
--------|-------------------------|----------------
INC     | Increment Memory        | N Z
INX     | Increment X Register    | N Z
INY     | Increment Y Register    | N Z
DEC     | Decrement Memory        | N Z
DEX     | Decrement X Register    | N Z
DEY     | Decrement Y Register    | N Z

### Shifts

Shift instructions move bits within a memory location or the accumulator.  
Rotate instructions use the carry flag to rotate bits in or out.  
All shift/rotate operations affect the N, Z, and C flags.

Op Code | Instruction           | Affected Flags
--------|-----------------------|----------------
ASL     | Arithmetic Shift Left | N Z C
LSR     | Logical Shift Right   | N Z C
ROL     | Rotate Left           | N Z C
ROR     | Rotate Right          | N Z C

### Jumps & Calls

These instructions change the program counter, altering control flow.

Op Code | Instruction             | Affected Flags
--------|-------------------------|----------------
JMP     | Jump to Location        | –
JSR     | Jump to Subroutine      | –
RTS     | Return from Subroutine  | –

### Branches

Branch instructions change control flow based on flag conditions.

Op Code | Instruction                 | Affected Flags
--------|-----------------------------|----------------
BCC     | Branch if Carry Clear       | –
BCS     | Branch if Carry Set         | –
BEQ     | Branch if Zero Set          | –
BMI     | Branch if Negative Set      | –
BNE     | Branch if Zero Clear        | –
BPL     | Branch if Negative Clear    | –
BVC     | Branch if Overflow Clear    | –
BVS     | Branch if Overflow Set      | –

### Status Flag Changes

These instructions set or clear specific processor status flags.

Op Code | Instruction                  | Affected Flags
--------|------------------------------|----------------
CLC     | Clear Carry Flag             | C
CLD     | Clear Decimal Mode Flag      | D
CLI     | Clear Interrupt Disable Flag | I
CLV     | Clear Overflow Flag          | V
SEC     | Set Carry Flag               | C
SED     | Set Decimal Mode Flag        | D
SEI     | Set Interrupt Disable Flag   | I

### System Functions

Instructions that provide system-level behavior or are rarely used.

Op Code | Instruction            | Affected Flags
--------|------------------------|----------------
BRK     | Force Interrupt        | B
NOP     | No Operation           | –
RTI     | Return from Interrupt  | All
