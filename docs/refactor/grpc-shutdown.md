# gRPC startup and shutdown ownership

The transport now owns its executor and pooled factory explicitly. Startup
validates port range, worker count, paired TLS settings, and successful binding.
Registration or startup failures stop the created server, close/defer-close the
pool, and shut down queued executor work. Signal handlers are restored on exit.

SIGTERM/SIGINT request a thirty-second RPC grace period; a second signal requests
immediate RPC cancellation. The server then leaves its termination wait and
performs final stop cleanup. These operations use the
[gRPC server lifecycle API](https://grpc.github.io/grpc/python/grpc.html).
The candidate overlay retains a forty-second container stop grace.

`PooledDatabaseFactory.close()` prevents new borrows. It closes all physical
connections immediately when drained, or after the last active release. Release
holds the factory lock through transaction completion and pool return, so close
cannot race with a transaction still being cleaned up. This serializes release
cleanup, not handler query execution; measure contention before scaling.
Repeated close requests do not call closeall again. Existing duplicate/foreign
release guards and discard-on-transaction-failure behavior remain.

## Limits and remaining acceptance

RPC termination does not guarantee every application thread has returned.
Cancelled/noncooperative handlers may hold their borrows until their finally
blocks run. Executor shutdown does not forcibly interrupt Python threads;
container stop grace remains the outer bound. No new database statement timeout
or thread-kill mechanism is introduced. Generator cancellation can occur after
stream responses have been emitted; transaction and connection cleanup need
runtime validation on those paths.

Pending checks: normal drain, repeated signals, cancellation during unary and
streaming handlers, active borrow during close, no borrow after close, last
release closes pool once, failed commit disposal, startup failure cleanup,
invalid port/worker settings, partial TLS configuration, failed bind, and
container stop timing. No runtime tests, RPC calls, or service starts were
performed. Static lint, provider boundary, dependency, and diff checks passed.

Rollback by reverting lifecycle/factory cleanup while keeping the optional
transport stopped until its replacement is validated. No schema, credential,
schedule, or business data changes are involved.
