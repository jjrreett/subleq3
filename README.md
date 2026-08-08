# SUBLEQ assembler and emulator

This project implements a small assembler and a 16-bit emulator for a
SUBLEQ (subtract and branch if less than or equal to zero) computer. The
assembly language adds labels, macros, data directives, and memory-mapped I/O
on top of the single native `subleq` instruction.

## Machine model

Memory is an array of unsigned 16-bit words. Signed comparisons interpret a
word as a two's-complement `int16`.

The only native instruction occupies three consecutive words:

```asm
subleq a, b, target
```

It performs the equivalent of:

```text
memory[b] = memory[b] - memory[a]
if signed(memory[b]) <= 0:
    pc = target
else:
    pc += 3
```

Branching to address `0` halts the emulator.

The first instruction in a normal program is three words long, so the example
programs place the special cells immediately after it:

```asm
jmp start
IO:      .word 0        ; address 3
INSPECT: .word 0        ; address 4
```

- Address `3` (`IO`) is memory-mapped character I/O. Reading from it prompts
  for an integer; subtracting a value into it writes that value as one byte.
- Address `4` (`INSPECT`) prints a value in decimal, hexadecimal, and binary.
- Address `0` is also the halt target.

These addresses are fixed by `subleq/const.py`; labels merely give them useful
names.

## Source syntax

- Source is line-oriented, and instructions end at a newline.
- Identifiers use letters, digits, and underscores and cannot begin with a
  digit.
- Whitespace is insignificant except for newlines.
- A semicolon starts a comment that continues to the end of the line.
- Arguments are comma-separated.
- Numeric literals may be decimal, hexadecimal with `$`, or binary with `%`.
  A leading minus sign is supported.

```asm
value: .word 42
mask:  .word $ff00
bits:  .word %10101010
minus: .word -1

subleq value, result, finished ; result -= value
```

All final values are stored modulo `65536`. For example, `-1` becomes
`$ffff` in memory.

## Labels and values

A global label is an identifier followed by a colon. Its value is the memory
address of the next emitted word:

```asm
start:
    subleq one, counter, done
    subleq zero, zero, start

done:
    subleq zero, zero, 0

zero:    .word 0
one:     .word 1
counter: .word 10
```

`?` emits the address of the following word (`current address + 1`). It is
mostly useful when constructing self-modifying instructions or data blocks.

```asm
.data
    0
    0
    ?
.endd
```

### Local labels

An `@` label is local to the most recent global label:

```asm
function:
@loop:
    subleq one, count, @done
    subleq zero, zero, @loop
@done:
```

Defining another global label starts a new scope. Macros also mangle their
internal labels per expansion so that calling the same macro multiple times
does not create duplicate names. This also applies to nested macros. A local
label passed as a macro argument remains in the caller's scope.

References may appear before or after their definition, but they cannot cross
a global-label boundary:

```asm
first:
@loop:
    jmp @loop          ; resolves to first's @loop

second:
    jmp @loop          ; error: second has no @loop
```

## Data directives

Directives emit words at the current position:

```asm
.byte  $ff, 1
.word  $1234, -1
.dword $12345678
.ascii "Hello"
.asciiz "World"
.fill  10, $00
.res   256
```

Their intended meanings are:

| Directive | Result |
| --- | --- |
| `.byte n, ...` | One word per numeric value. Byte-range checking is not currently enforced. |
| `.word n, ...` | One word per numeric value. |
| `.dword n, ...` | Two words per value, high word followed by low word. |
| `.ascii "text"` | One word per character. |
| `.asciiz "text"` | The characters followed by a zero word. |
| `.fill count, value` | `count` copies of `value`. |
| `.res count` | `count` zero words. |

`.byte`, `.word`, and `.dword` currently accept numeric literals only, not
labels or macro arguments.

The more general `.data` block accepts numbers, labels, local labels, and `?`,
one item after another until `.endd`:

```asm
dispatch_table: .data
    handler_a
    handler_b
    0
.endd
```

The existing code also uses one-line blocks:

```asm
stack_ptr: .data stack .endd
```

## Macros

Macros provide the larger instruction vocabulary used by `program.s`. Define
one with `.macro` and `.endm`:

```asm
.macro jmp, target
    subleq zero, zero, target
.endm

.macro add, source, destination
    subleq source, zero, ?
    subleq zero, destination, ?
    subleq zero, zero, ?
.endm
```

Invoke a macro like an instruction:

```asm
add value, total
jmp finished
```

Arguments are substituted as assembler tokens. A macro must be defined before
it is used, and each invocation must supply exactly the declared number of
arguments. Macro bodies may invoke previously defined macros.

The larger sample program builds operations such as `clr`, `add`, `cpy`,
`inc`, `dec`, conditional branches, shifts, multiplication, stack operations,
subroutine calls, and decimal printing from `subleq` plus self-modifying code.
These are library macros, not native opcodes.

## Building and running

The project requires Python 3.12 or newer and uses `uv` for its environment.

```powershell
uv sync
```

Compile an assembly file:

```powershell
uv run python -m subleq.compile program.s
```

This creates `program.npy`. Add `-l` to also write `program.labels`, or use
`-o` to select another output name:

```powershell
uv run python -m subleq.compile program.s -o build/program.npy -l
```

Run the resulting image:

```powershell
uv run python -m subleq.run program.npy -l
```

`-l` loads the matching labels file for more useful debug output. Add `-g` to
either command to enable its verbose diagnostics.

After installing the project, the shorter script names are also available:

```powershell
uv pip install .
compile program.s -l
run program.npy -l
```

## Regenerating the parser

`subleq/subleq.py` is a generated standalone Lark parser. After changing
`subleq.lark`, regenerate it from the project directory:

```powershell
uv run python -m subleq.gen_grammar
```

Do not edit the generated parser by hand.

## Current development status

Scoped local labels are implemented and covered by automated compiler tests,
including forward and backward references, repeated macro calls, caller-local
arguments, and nested macros.

- `program.s` compiles to a 1,926-word image.
- `test_local_labels.s` is a preserved, intermediate experiment that still
  uses unsupported syntax such as a macro parameter with `.word`; the current
  tests in `tests/test_compile.py` replace it as the local-label test suite.
- `ode.s` now gets through local-label resolution. Its next compiler error is
  an unrelated missing global constant (`literal_16`), and its numerical model
  remains unfinished.
