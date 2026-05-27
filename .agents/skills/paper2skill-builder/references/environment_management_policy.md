# Environment Management Policy

Generated child skills must check Python, R, and CLI dependencies before any
run. Missing dependencies must block execution and produce install plans. In
non-interactive mode, `ask` behaves as `never`. Installation requires
`--confirm yes`.
