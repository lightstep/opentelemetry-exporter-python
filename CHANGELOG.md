## Unreleased

v0.6b2
======

### Changes

* Resources now added to span tags. [alrex]

  Adding support for resources. They will be added to a span's tags. Also adding a parameter to allow users to set the `service_version`.

### Fix

* Events are reported as logs. [alrex]

v0.6b1
======

* Set parent ID if present (#7) [alrex]

  Ensure the parent is set for spans with a parent span.


v0.6b0
======

* Update to support 0.6b0 opentelemetry release (#6) [alrex]

* Adding badges to readme. [alrex]

* Cleaning up repo, adding basic tests (#5) [alrex]

* Use thrift instead of http. [alrex]

* Update default host. [Isobel Redelmeier]

* Convert variable casing to snake case. [Isobel Redelmeier]

* Support empty access token. [Isobel Redelmeier]
