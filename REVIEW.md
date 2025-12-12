# Zig Code Review

## Findings

1. **Memory safety: OpenDAL option strings freed while options still live**  
   In `plugins/zig/opendal/main.zig` the endpoint and object path strings are allocated (`buildEndpointZ`, `buildObjectPathZ`) and passed into `opendal_operator_options_set`, but both are freed via `defer allocator.free(...)` before the options struct itself is freed (`opendal_operator_options_free`). The OpenDAL C API documents option setters as borrowing the provided pointer, so freeing these slices while `options` is still alive risks dangling pointers if the library keeps references past `opendal_operator_new` (e.g., for retries or lazy initialization). Keep these allocations alive for the full lifetime of the options/operator (e.g., remove the frees or move them after `opendal_operator_options_free`).

2. **Allocator leak: duplicated raw components never freed**  
   In the same file, helpers such as `componentToRawAlloc` allocate raw URI components which are then copied again by `toZ`, but the original allocations (e.g., bucket names, credential paths) are never freed. For long-lived processes or repeated calls this leaks memory proportional to the number of options constructed. Free the raw component after converting to a null-terminated string or rewrite `toZ` to work directly from the `std.Uri.Component` without an intermediate allocation.
