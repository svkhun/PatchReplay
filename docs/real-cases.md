# Reviewed upstream function cases

Case contract version 2 adds `provenance_sha256` to version 1. The existing bounded
integer protocol and host decision rules are unchanged. Provenance snapshots contain
raw upstream source, source URLs, license notices, the fixed observation adapter and
adaptation record. They are checked before execution, stored in evidence, verified
offline and transitively bound by case/input identities and signatures.

| Case | Pinned fix | Declared behavior |
| --- | --- | --- |
| boltons-fix | [mahmoud/boltons 4bae3f5](https://github.com/mahmoud/boltons/commit/4bae3f55894e78ec6326d6dba8ac7e3eb39440aa), parent `230b856dc31cc0702d77ef978daec9cff45944eb` | Calling clamp with omitted bounds should preserve the input; the parent raises TypeError on Python 3.11/3.12. Explicit bounds remain regression probes. |
| lcm-fix | [TheAlgorithms/Python 4aca14b](https://github.com/TheAlgorithms/Python/commit/4aca14b650a238e4906c3d753b075cc324774e67), parent `d9027b034699aa60f3e89e1344211b686274af27` | LCM(0,0) should equal zero; the parent's fast function divides by zero. Positive pairs and one-zero input remain regression probes. |

The boltons license is BSD-style; its complete notice is retained. TheAlgorithms
source is MIT-licensed; its complete notice is retained. See the packaged provenance
directories for exact bytes and source URLs. Tests evaluate historical fixes, not
claims that current upstream versions remain broken.

The boltons candidate retains its full mathutils module with a fixed appended wrapper.
Zero/zero bound arguments select the upstream default-argument call; TypeError maps
to `-9007199254740991`. All declared successful default-call inputs are positive and
the explicit-bound probes cannot return that reserved sentinel.

The LCM candidate retains the full upstream module, replaces its gcd import with the
exact pinned gcd function body and appends a fixed wrapper for nonnegative inputs.
ZeroDivisionError maps to `-1`, outside the declared nonnegative result domain. The
dependency module's unrelated CLI footer uses newer Python syntax, so it is retained
as provenance but excluded from the extracted function. No candidate is imported
or executed on the host while authoring or admitting cases.

The sentinel is an explicitly reviewed numeric observation of the adapter. It is
not a guest assertion of PASS/FAIL. Other exceptions, malformed output and execution
failure remain errors. A match does not prove which implementation ran internally.
This is function-extract validation, not full-project integration or the complete
upstream test suite. Integer properties and `math.lcm` define the expected behaviors
independently of the patched output; the pinned upstream fixes support the selection.

Each project also has `-noop` and `-regression` synthetic controls. They are labeled
`synthetic-control` in provenance and are not presented as upstream patches. The six
cases form a pinned suite with two repeats and sixteen observations per case.
Maintainer authoring uses `scripts/build_real_fixtures.py`; runtime has no arbitrary
repository, source, patch or command intake and performs no dependency installation.
