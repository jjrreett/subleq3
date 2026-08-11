# SUBLEQ standard library

The standard library is a collection of source modules imported with angle
brackets. It favors explicit machine state and documents every macro in terms
of its signature, effects, required cells, changed state, and restored scratch.

```asm
.include <core.s>
```

Standard modules are imported once per link, including transitive imports.
They emit no global data, so importing a module does not move the program entry
point. Programs allocate the ABI cells they use.

## Core ABI

Programs using `core.s` provide these cells:

```asm
z:  .word 0
.literals 2
```

`z` is shared scratch storage and is restored to zero after every library
operation. Positive and negative one use immediate literals instead of ABI
cells. Library macros are not reentrant or interrupt-safe because they share
`z` and may contain private self-modifying words.

## `core.s`

Arithmetic and control-flow macros. Import directly with:

```asm
.include <core.s>
```

| Macro | Effect | Native instructions | State changed |
| --- | --- | ---: | --- |
| `jmp target` | Unconditional jump | 1 | — |
| `clr target` | `target = 0` | 1 | `target` |
| `sub source, destination` | `destination -= source` | 1 | `destination` |
| `add source, destination` | `destination += source` | 3 | `destination`, `z` restored |
| `cpy source, destination` | `destination = source` | 4 | `destination`, `z` restored |
| `dec target` | `target -= 1` | 1 | `target` |
| `inc target` | `target += 1` | 1 | `target` |
| `dbl target` | `target *= 2` | 3 | `target`, `z` restored |
| `bleq value, target` | Branch if signed `value <= 0` | 1 | — |
| `bgt value, target` | Branch if signed `value > 0` | 2 | — |
| `beq value, target` | Branch if `value == 0` | 9 | `value` temporarily |
| `bne value, target` | Branch if `value != 0` | 10 | `value` temporarily |
| `bpl value, target` | Branch if signed `value >= 0` | 11 | `value` temporarily |
| `bmi value, target` | Branch if signed `value < 0` | 10 | `value` temporarily |

## `subroutine.s`

Indirect memory, stack, and call support. This module imports `core.s`, so a
program normally imports only:

```asm
.include <subroutine.s>
```

In addition to `z` and an immediate-literal pool, programs provide an
upward-growing stack:

```asm
stack:     .res 256
stack_ptr: .word stack
```

`stack_ptr` always addresses the next free word. The library performs no stack
overflow or underflow checks.

| Macro | Effect | State changed |
| --- | --- | --- |
| `rpt pointer, destination` | Subtract the addressed word into `destination`, then clear it; paired with `wpt` | addressed word, `destination`; private code and restored `z` as scratch |
| `wpt source, pointer` | Write `memory[source]` to `memory[memory[pointer]]` | private code |
| `psh source` | Push one word | `stack_ptr`, next stack word, private code |
| `pop destination` | Pop one word | `destination`, `stack_ptr`, private code |
| `jsr target` | Push return address and jump | `stack_ptr`, next stack word, private code |
| `rts` | Capture/execute a two-phase return | `stack_ptr`, private state and code |

### Calling convention

Arguments and results are stack words; there are no implicit registers. A
function begins with `rts`, pops its arguments, pushes any result, and jumps
back to its own entry label to activate the return pass.

```asm
.include <subroutine.s>

double:
    rts
    pop value
    dbl value
    psh value
    jmp double

main:
    psh input
    jsr double
    pop output
```

`rts` is deliberately unusual because SUBLEQ has no native indirect jump. It
uses macro-private self-modifying code, making each expanded call site
independent but not recursively reentrant.

`rpt` is a short, low-level name retained for the stack implementation. It is
destructive and paired with `wpt`; it is not the long spelling of `read_word`.
Use `read_word` for a normal non-destructive indirect load. Both hovers state
this distinction.

## `memory.s`

Non-destructive indirect memory access. It imports `core.s` and uses the core
`z` scratch cell.

| Macro | Effect | State changed |
| --- | --- | --- |
| `read_word pointer, destination` | Copy `memory[memory[pointer]]` without changing the source | `destination`, private code, `z` restored |

Unlike the stack-oriented `rpt`, `read_word` leaves the addressed source word
intact, making it suitable for traversing strings and tables. Importing
`subroutine.s` also makes this macro available.

## `io.s`

Character-output helpers. It imports `memory.s`, requires the fixed `IO` cell,
and expects the program to reserve `.literals` capacity for newline values.

| Macro | Effect | State changed |
| --- | --- | --- |
| `newline` | Write line feed and carriage return to `IO` | device output only |
| `print_asciiz string` | Write characters through the terminating zero | `IO`, private pointer/character cells, `z` restored |

## `math.s`

Extended integer arithmetic. It imports `core.s`; shift macros that use
immediates require capacity in the program's `.literals` pool.

| Macro | Effect | State changed |
| --- | --- | --- |
| `mul source, destination` | Multiply by repeated addition | both operands, private scratch, `z` restored |
| `fmul multiplicand, multiplier` | Multiply with binary shift-and-add | both operands, private scratch, `z` restored |
| `lsl count, value` | Shift `value` left by `count` bits | `value`, private counter, `z` restored |
| `lsr source, value` | Shift `value` right with a working bit accumulator | both operands, private scratch, `z` restored |
| `double_dabble_add_3 digit` | Apply double-dabble's add-three step | `digit`, private scratch, `z` restored |
| `nibble_lslo input, output` | Shift a nibble left and carry into `output` | both operands, private scratch, `z` restored |
| `lslo input, output` | Shift a 16-bit word left and carry into `output` | both operands |

## `print.s`

Callable integer-output routines. Unlike the macro-only modules, this module
emits executable words and must be included after the reset jump and fixed
`IO`/`INSPECT` cells. It imports `subroutine.s`, `io.s`, and `math.s`, requires
their ABI cells and stack, and expects a sufficiently large program-level
`.literals` pool.

| Subroutine | Effect | Stack effect |
| --- | --- | --- |
| `func_print_bin` | Print all 16 binary digits and a newline | consumes one argument |
| `func_print_dec` | Print all five unsigned decimal digits and a newline | consumes one argument |

## Tests

The standard library has executable assembly test cases for core arithmetic,
double-dabble conversion, indirect memory, stack-based calls, text output, and
integer printing. Run them from the project root:

```powershell
subleq test subleq/stdlib/stdlib_tests.s
```
