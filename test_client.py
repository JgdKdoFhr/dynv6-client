import unittest
from unittest import mock

import requests

import client

TOKEN = 'SECRET-TOKEN-123'

# /proc/net/if_inet6: address, ifindex, prefix length, scope, flags, interface
IF_INET6 = '''\
fe800000000000007270fcfffe00729a 02 40 20 80   enp1s0
200300c68f238e77ec10d5ce800bb9ea 02 40 00 01   enp1s0
fd000000000000000000000000000001 02 40 00 80   enp1s0
200300c68f238e770000000000000001 02 40 00 20   enp1s0
200300c68f238e770000000000000002 03 40 00 00     eth1
200300c68f238e777270fcfffe00729a 02 40 00 00   enp1s0
'''


class Response:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError('HTTP {}'.format(self.status_code))


class StopLoop(Exception):
    pass


class InterfaceIPv6Test(unittest.TestCase):
    def test_skips_link_local_temporary_ula_deprecated_and_other_interfaces(self):
        with mock.patch('builtins.open', mock.mock_open(read_data=IF_INET6)):
            self.assertEqual(client.interface_ipv6('enp1s0'), '2003:c6:8f23:8e77:7270:fcff:fe00:729a')

    def test_none_without_global_address(self):
        with mock.patch('builtins.open', mock.mock_open(read_data=IF_INET6)):
            self.assertIsNone(client.interface_ipv6('wlan0'))


class LoopTest(unittest.TestCase):
    def run_rounds(self, rounds, args=()):
        """One loop iteration per round: (ipify answer or 'fail', interface IPv6 or None,
        update response as (status, body), 'conn' for a connection error, or None if no update is expected)."""
        state = {'round': 0, 'updates': []}

        def get(session, url, params=None, timeout=None):
            ipv4, _ipv6, answer = rounds[state['round']]
            if url == client.IPV4_URL:
                if ipv4 == 'fail':
                    raise requests.ConnectionError('ipify unreachable')
                return Response(200, ipv4 + '\n')
            state['updates'].append((state['round'], {k: v for k, v in params.items() if k != 'token'}))
            self.assertEqual(params['token'], TOKEN)
            self.assertIsNotNone(answer, 'unexpected update in round {}'.format(state['round']))
            if answer == 'conn':
                raise requests.ConnectionError('Max retries exceeded with url: /api/update?token=' + TOKEN)
            return Response(*answer)

        def sleep(seconds):
            state['round'] += 1
            if state['round'] == len(rounds):
                raise StopLoop

        with mock.patch.object(requests.Session, 'get', get), \
                mock.patch.object(client, 'interface_ipv6', lambda interface: rounds[state['round']][1]), \
                mock.patch.object(client.time, 'sleep', sleep), \
                mock.patch.object(client.signal, 'signal'), \
                self.assertLogs('dynv6-client', level='INFO') as logs, \
                self.assertRaises(StopLoop):
            client.main.main(['--token', TOKEN, *args, 'example.dynv6.net'], standalone_mode=False)
        for line in logs.output:
            self.assertNotIn(TOKEN, line)
        return state['updates'], logs.output

    def test_updates_only_on_change_and_survives_errors(self):
        updates, logs = self.run_rounds([
            ('1.2.3.4', '2003::1', (200, 'addresses updated')),
            ('1.2.3.4', '2003::1', None),
            ('5.6.7.8', '2003::1', (500, '')),
            ('5.6.7.8', '2003::1', 'conn'),
            ('5.6.7.8', '2003::1', (200, 'addresses updated')),
            ('5.6.7.8', '2003::1', None),
        ])
        self.assertEqual([number for number, _ in updates], [0, 2, 3, 4])
        self.assertEqual(updates[0][1], {'zone': 'example.dynv6.net', 'ipv4': '1.2.3.4', 'ipv6': '2003::1'})
        self.assertEqual(updates[3][1], {'zone': 'example.dynv6.net', 'ipv4': '5.6.7.8', 'ipv6': '2003::1'})
        self.assertTrue(any('HTTP 500: (empty response)' in line for line in logs))
        self.assertTrue(any('token=***' in line for line in logs))

    def test_lookup_problems_are_logged_once_and_skip_the_update(self):
        updates, logs = self.run_rounds([
            ('1.2.3.4', '2003::1', (200, 'addresses updated')),
            ('fail', '2003::1', None),
            ('fail', '2003::1', None),
            ('1.2.3.4', None, None),
            ('1.2.3.4', None, None),
        ])
        self.assertEqual([number for number, _ in updates], [0])
        self.assertEqual(sum('cannot determine public IPv4 address' in line for line in logs), 1)
        self.assertEqual(sum('no global IPv6 address' in line for line in logs), 1)

    def test_ipv4_only(self):
        updates, _ = self.run_rounds([('1.2.3.4', '2003::1', (200, 'addresses updated'))], ['--no-ipv6'])
        self.assertEqual(updates[0][1], {'zone': 'example.dynv6.net', 'ipv4': '1.2.3.4'})


if __name__ == '__main__':
    unittest.main()
