# gRPC pooled database boundary

`services/grpc/database.py:PooledDatabaseFactory` adapts the existing threaded
psycopg2 pool to `services/common/database.py:DatabaseConnection`. Authentication
and service handlers now receive `.text`, `.execute`, `.mappings`, and named
parameter support rather than a raw connection. The callable factory and
`factory.release(conn)` interface remain available to the existing handlers.

Borrowed wrappers are tracked under a lock. Release accepts only a wrapper
borrowed from that factory, and rejects a duplicate or foreign release. On
release from a handler's finally block, Python's active exception state controls
the transaction outcome: commit on normal return, rollback while unwinding an
exception or RPC abort. A commit/rollback failure closes/discards the raw
connection rather than recycling an uncertain transaction. Query cursors use
the shared wrapper's existing finally cleanup. The pool retains ownership of
physical connection lifetime.

This fixes the source-level interface mismatch identified during the first
transport build and defines transaction completion for RPC domain writes.
Domain lifecycle, authorization, credit custody, and human confirmation rules
remain in their existing services; successful transaction completion does not
grant new write authority.

## Constraints and acceptance

Release must occur in the handler's existing finally block, while any exception
is still active. A handler that catches a failure and returns normally must
explicitly roll back before returning; suppressing failures is not automatically
detected. Do not call wrapper.close() or use its context manager to own a pooled
borrow: its physical connection belongs to the pool. Always use factory.release.
Pool exhaustion behavior is inherited; no waiting/retry policy is introduced.
The later [shutdown change](grpc-shutdown.md) defers physical pool closure until
borrows drain. Transaction cleanup is serialized with borrowing/close to avoid
a closure race; contention remains to be measured. Authenticated context is
corrected separately in source; both changes retain runtime acceptance gates.

Pending runtime checks: named-parameter reads through a real pooled connection,
authentication lookup, successful write commit, raised exception and RPC abort
rollback, failed transaction disposal, pool exhaustion, concurrent borrowing,
duplicate/foreign release, and subsequent connection reuse. No runtime tests,
RPC writes, or deployment changes were performed. Static lint, provider
boundaries, requirement grouping, and diff checks passed.

The previously built image predates this source correction and must be rebuilt
before use. Rollback restores the old factory, but also restores its interface
mismatch; keep the optional transport stopped until a compatible implementation
is available. No schema or persisted business data changed in this slice.
