import ipaddress
import logging
import signal
import sys
import time

import click
import requests

UPDATE_URL = 'https://dynv6.com/api/update'
IPV4_URL = 'https://api.ipify.org'
USER_AGENT = 'dynv6-client (+https://github.com/JgdKdoFhr/dynv6-client)'
TIMEOUT = 30

# address flags in /proc/net/if_inet6, see linux/if_addr.h
IFA_F_TEMPORARY = 0x01
IFA_F_DADFAILED = 0x08
IFA_F_DEPRECATED = 0x20
IFA_F_TENTATIVE = 0x40
SKIP_FLAGS = IFA_F_TEMPORARY | IFA_F_DADFAILED | IFA_F_DEPRECATED | IFA_F_TENTATIVE

log = logging.getLogger('dynv6-client')


class UpdateError(Exception):
    pass


def public_ipv4(session, url):
    response = session.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    return str(ipaddress.IPv4Address(response.text.strip()))


def interface_ipv6(interface):
    """First stable, globally routable IPv6 address of the interface, or None."""
    with open('/proc/net/if_inet6') as f:
        for line in f:
            address, _index, _prefixlen, _scope, flags, name = line.split()
            if name != interface or int(flags, 16) & SKIP_FLAGS:
                continue
            address = ipaddress.IPv6Address(int(address, 16))
            if address.is_global:
                return str(address)
    return None


def update(session, url, zone, token, addresses):
    response = session.get(url, params={'zone': zone, 'token': token, **addresses}, timeout=TIMEOUT)
    body = response.text.strip()
    if response.status_code != 200:
        raise UpdateError('HTTP {}: {}'.format(response.status_code, body[:200] or '(empty response)'))
    return body


def warn_once(warnings, key, message):
    if warnings.get(key) != message:
        log.warning(message)
        warnings[key] = message


@click.command()
@click.argument('zone', envvar='DYNV6_ZONE')
@click.option('--token', envvar='DYNV6_TOKEN', show_envvar=True, required=True,
              help='HTTP token of the zone.')
@click.option('--interface', envvar='DYNV6_INTERFACE', show_envvar=True, default='eth0', show_default=True,
              help='Interface to read the IPv6 address from.')
@click.option('--ipv4/--no-ipv4', envvar='DYNV6_IPV4', show_envvar=True, default=True, show_default=True,
              help='Update the A record.')
@click.option('--ipv6/--no-ipv6', envvar='DYNV6_IPV6', show_envvar=True, default=True, show_default=True,
              help='Update the AAAA record.')
@click.option('--interval', envvar='DYNV6_INTERVAL', show_envvar=True, default=300, show_default=True,
              type=click.IntRange(min=30), help='Seconds between address checks.')
@click.option('--refresh', envvar='DYNV6_REFRESH', show_envvar=True, default=86400, show_default=True,
              type=click.IntRange(min=0), help='Seconds after which an update is sent even if nothing changed '
              '(0 = only on change).')
@click.option('--ipv4-url', envvar='DYNV6_IPV4_URL', show_envvar=True, default=IPV4_URL, show_default=True,
              help='Service that returns the public IPv4 address as plain text.')
@click.option('--update-url', envvar='DYNV6_UPDATE_URL', default=UPDATE_URL, hidden=True)
def main(zone, token, interface, ipv4, ipv6, interval, refresh, ipv4_url, update_url):
    """Keep the A/AAAA records of a dynv6.com ZONE (e.g. example.dynv6.net) up to date."""
    if not token.strip():
        raise click.UsageError('--token is empty')
    if not (ipv4 or ipv6):
        raise click.UsageError('--no-ipv4 and --no-ipv6 together leave nothing to update')

    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    session = requests.Session()
    session.headers['User-Agent'] = USER_AGENT
    sent = {}
    next_refresh = 0.0
    warnings = {}
    log.info('updating %s (ipv4=%s, ipv6=%s, interface=%s) every %ss', zone, ipv4, ipv6, interface, interval)

    while True:
        addresses = {}
        if ipv4:
            try:
                addresses['ipv4'] = public_ipv4(session, ipv4_url)
                warnings.pop('ipv4', None)
            except (requests.RequestException, ValueError) as e:
                warn_once(warnings, 'ipv4', 'cannot determine public IPv4 address: {}'.format(e))
        if ipv6:
            try:
                address = interface_ipv6(interface)
            except OSError as e:
                address = None
                warn_once(warnings, 'ipv6', 'cannot read IPv6 addresses: {}'.format(e))
            if address:
                addresses['ipv6'] = address
                warnings.pop('ipv6', None)
            else:
                warn_once(warnings, 'ipv6', 'no global IPv6 address on {}'.format(interface))

        changed = any(sent.get(family) != address for family, address in addresses.items())
        due = refresh and time.monotonic() >= next_refresh
        if addresses and (changed or due):
            try:
                result = update(session, update_url, zone, token, addresses)
            except (UpdateError, requests.RequestException) as e:
                # requests puts the full URL, token included, into some exception messages
                log.error('update of %s failed, retrying in %ss: %s', zone, interval, str(e).replace(token, '***'))
            else:
                sent.update(addresses)
                next_refresh = time.monotonic() + refresh
                log.info('%s: %s (%s)', zone, ' '.join('{}={}'.format(*item) for item in addresses.items()), result)

        time.sleep(interval)


if __name__ == '__main__':
    main()
