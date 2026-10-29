# dynv6-client

A small client that keeps the A and AAAA records of a [dynv6.com](https://dynv6.com/) zone pointed at your current addresses. It runs as a container on amd64, arm64 and arm/v7 (e.g. Raspberry Pi).

> [!NOTE]
> **This build is maintained mainly by AI.** Code changes, the build pipeline and the documentation in this fork are written by an AI coding assistant (Claude, via Claude Code), and a human reviews and merges them. Dependabot proposes dependency updates automatically. Review the code before you rely on it.

## How it works

Every `--interval` seconds (default 300) the client checks:

- **IPv4:** the public address, as reported by https://api.ipify.org (change with `--ipv4-url`)
- **IPv6:** the first stable, globally routable address on `--interface`. Temporary, deprecated, link-local and ULA addresses are skipped.

It calls the [dynv6 Update API](https://dynv6.com/docs/apis) only when an address has changed, and once every `--refresh` seconds (default 86400) even if nothing changed. That way a record edited elsewhere is put back.

If an update fails, the client logs the HTTP status and response in one line and tries again at the next check. It doesn't exit. Your token never appears in the log.

## Run

```bash
docker run -d --name dynv6-client --restart unless-stopped --network host \
  -e DYNV6_TOKEN=<your-token> \
  ghcr.io/jgdkdofhr/dynv6-client:latest --interface eth0 example.dynv6.net
```

`--network host` is only needed for IPv6, because the client reads the address from the host's interface. For IPv4 only:

```bash
docker run -d --name dynv6-client --restart unless-stopped \
  -e DYNV6_TOKEN=<your-token> \
  ghcr.io/jgdkdofhr/dynv6-client:latest --no-ipv6 example.dynv6.net
```

Passing the token as an environment variable keeps it out of the host's process list. `--token=<your-token>` still works.

### Docker Compose

```yaml
services:
  dynv6-client:
    image: ghcr.io/jgdkdofhr/dynv6-client:latest
    container_name: dynv6-client
    restart: unless-stopped
    network_mode: host
    environment:
      DYNV6_TOKEN: ${DYNV6_TOKEN}
    command: --interface eth0 example.dynv6.net
```

## Options

| Option | Environment variable | Default | Description |
|---|---|---|---|
| `ZONE` (argument) | `DYNV6_ZONE` | | Zone to update, e.g. `example.dynv6.net` |
| `--token` | `DYNV6_TOKEN` | | HTTP token of the zone (required) |
| `--interface` | `DYNV6_INTERFACE` | `eth0` | Interface to read the IPv6 address from |
| `--ipv4/--no-ipv4` | `DYNV6_IPV4` | on | Update the A record |
| `--ipv6/--no-ipv6` | `DYNV6_IPV6` | on | Update the AAAA record |
| `--interval` | `DYNV6_INTERVAL` | `300` | Seconds between address checks (minimum 30) |
| `--refresh` | `DYNV6_REFRESH` | `86400` | Seconds after which an update is sent even if nothing changed, `0` = only on change |
| `--ipv4-url` | `DYNV6_IPV4_URL` | `https://api.ipify.org` | Service that returns the public IPv4 address as plain text |

## Image tags

Images are published to `ghcr.io/jgdkdofhr/dynv6-client` by GitHub Actions:

- `latest`: the current `main` branch
- `sha-<commit>`: every build from `main`
- `X.Y.Z` and `X.Y`: release tags `vX.Y.Z`

Dependabot checks weekly for new versions of the Python packages, the Python base image and the GitHub Actions. Merging its pull requests publishes a new `latest`.

## Build locally

```bash
docker build -t dynv6-client .
```

## Credits

This is a fork of [starze/dynv6-client](https://github.com/starze/dynv6-client) by Daniel Starzmann, which in turn was based on [ticosax/dynv6-client](https://github.com/ticosax/dynv6-client). MIT License, see [LICENSE](LICENSE).
