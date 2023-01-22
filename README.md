# Derailed API

The most powerful API of the lands.
Handles nearly every interaction except for
process-heavy interactions, ultra-frequent
or high-speed interactions, and our real-time infrastructure
which is instead based on Elixir 

## Deploying

Deploying the Derailed API is quite easy, just fill in the
required `.env` variables and launch either using
the `gunicorn` command or just running our development build.

You can also use our docker-compose config,
although this isn't recommended since it
could make scaling in the future much more
of a struggle and increase any pain of running
our services separately.

## How events are sent

Events are sent through an asynchronous,
taskful, and stateless gRPC request to either
our gRPC User or gRPC Guild service.

That service then handles it from there.

## Speedups

At every step, we try to use every speedup possible.

We use msgspec as an alternative json library which is
faster than the stdlib json, and orjson.

We also use uvloop which is a faster implementation
of the asyncio event loop which **only works on Linux.**
Don't worry, we don't force it upon Windows users at all,
and it's only used when launching our Gunicorn server
which *also* requires Linux, or our Docker image.

## Benchmarks

We have yet to perform benchmarks on Derailed,
but in the future we may to see any bottlenecks and other such.

First off though a good starting point may just be writing tests.
