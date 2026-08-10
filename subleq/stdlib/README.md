# SUBLEQ standard library

The standard library is a collection of source modules imported with angle
brackets. It favors explicit machine state and documents every macro in terms
of its signature, effects, required cells, and clobbers.

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
p1: .word 1
m1: .word -1
```

`z` is shared scratch storage and is restored to zero after every library
operation. `p1` and `m1` are read-only constants. Library macros are not
reentrant or interrupt-safe because they share `z` and may contain private
self-modifying words.

## `core.s`

Arithmetic and control-flow macros. Import directly with:

```asm
.include <core.s>
```

| Macro | Effect | Native instructions | Clobbers |
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

In addition to the core ABI cells, programs provide an upward-growing stack:

```asm
stack:     .res 256
stack_ptr: .word stack
```

`stack_ptr` always addresses the next free word. The library performs no stack
overflow or underflow checks.

| Macro | Effect | Clobbers |
| --- | --- | --- |
| `rpt pointer, destination` | Read `memory[memory[pointer]]` | `destination`, private code, `z` restored |
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
