from os import popen
from time import time
from parser import expr as parser
from random import choice
from os.path import expanduser, exists
from requests import request
from functools import lru_cache

class Lnd:

    def __init__(self, lnddir='~/.lnd', rpc='127.0.0.1:8080', network='mainnet'):
        self.lnddir = expanduser(lnddir)
        self.network = network
        with open(f'{self.lnddir}/data/chain/bitcoin/{self.network}/admin.macaroon', 'rb', ) as file:
            self.__macaroon = {'Grpc-Metadata-macaroon': file.read().hex()}

        self.__rpc = f'https://{rpc}'
        self.__tlscert = f'{lnddir}/tls.cert'

    def fetch(self, method: str, path: str, data=None, params=None) -> dict:
        url = f'{self.__rpc}/{path}'
        return request(
            method=method, url=url, headers=self.__macaroon, verify=self.__tlscert, json=data, params=params).json()

    @lru_cache(maxsize=None)
    def get_info(self) -> dict:
        return self.fetch('get', 'v1/getinfo')

    @lru_cache(maxsize=None)
    def get_own_pubkey(self) -> str:
        return self.get_info().get('identity_pubkey')

    @lru_cache(maxsize=None)
    def get_node_alias(self, pub_key) -> str:
        return self.get_node_info(pub_key).get('alias')

    @lru_cache(maxsize=None)
    def get_node_info(self, pub_key: str) -> dict:
        return self.fetch('get', f'v1/graph/node/{pub_key}').get('node')

    def get_channel_info(self, chan_id: int) -> dict:
        return self.fetch('get', f'v1/graph/edge/{chan_id}')

    def get_policy_local(self, chan_id: int) -> dict:
        channel_info = self.get_channel_info(chan_id)
        if channel_info['node1_pub'] == self.get_own_pubkey():
            return channel_info['node1_policy']
        else:
            return channel_info['node2_policy']

    def get_policy_remote(self, chan_id: int) -> dict:
        channel_info = self.get_channel_info(chan_id)
        if channel_info['node1_pub'] != self.get_own_pubkey():
            return channel_info['node1_policy']
        else:
            return channel_info['node2_policy']

    def get_fee_rate_local(self, chan_id: int):
        return int(self.get_policy_local(chan_id)['fee_rate_milli_msat'])

    def get_fee_base_local(self, chan_id: int):
        return int(self.get_policy_local(chan_id)['fee_base_msat'])

    def get_fee_rate_remote(self, chan_id: int):
        return int(self.get_policy_remote(chan_id)['fee_rate_milli_msat'])

    def get_fee_base_remote(self, chan_id: int):
        return int(self.get_policy_remote(chan_id)['fee_base_msat'])

    def get_list_channels(self):
        channels = filter(lambda channel: channel['active'], self.fetch('get', 'v1/channels')['channels'])
        return list(channels)

    def filter_list_channel(self, chan_id: int):
        return list(filter(lambda channel: channel['chan_id'] == chan_id, self.get_list_channels()))

    
class Rebalance:

    def __init__(
            self,
            lnd: object,
            amount=0,
            timeout=300,
            node_save=None,
            max_total_fees=0,
            fee_limit_fixed=0,
            fee_limit_percent=0,
            excluded=[],
            expressions=[],
            limit_rebalance=1
        ):
        self.lnd = lnd
        self.amount = int(amount)
        self.excluded = list(excluded)
        self.timeout = int(timeout)
        self.node_save = node_save
        self.timestamp = time()
        self.expressions = list(expressions)

        self.max_total_fees = int(max_total_fees)
        self.limit_rebalance = limit_rebalance
        self.fee_limit_fixed = fee_limit_fixed
        self.fee_limit_percent = fee_limit_percent

        self.total_rebalance_fees = 0
        self.total_rebalance_amount = 0
        self.total_rebalance_channels = 0

    @staticmethod
    def get_local_available(channel: dict):
        return max(0, int(channel['local_balance']) - int(channel['local_chan_reserve_sat']))

    @staticmethod
    def get_remote_available(channel: dict):
        return max(0, int(channel['remote_balance']) - int(channel['remote_chan_reserve_sat']))

    def get_capacity_available(self, channel: dict):
        return self.get_local_available(channel) + self.get_remote_available(channel)
    
    def get_ratio_channel(self, channel: dict):
        ratio = int(10 * self.get_local_available(channel) / self.get_capacity_available(channel))
        return {'remote': 10 - ratio, 'local': ratio}

    def ignore_channel_excluded(self, channel: dict) -> bool:
        get_node_pubkey = channel.get('remote_pubkey')
        get_node_alias = self.lnd.get_node_alias(get_node_pubkey)
        get_chan_id = channel.get('chan_id')
        if get_node_alias in self.excluded:
            return True
        elif get_node_alias in self.excluded:
            return True
        elif get_chan_id in self.excluded:
            return True
        else:
            return False

    def get_list_channels(self):
        channels = []
        for channel in self.lnd.get_list_channels():
            if not self.ignore_channel_excluded(channel):
                channels.append(channel)
        return channels

    def get_list_channels_low_outbound(self):
        channels = []
        for channel in self.get_list_channels():
            ratio = self.get_ratio_channel(channel)
            if ratio['local'] < 5:
                channels.append(channel)
        return sorted(channels, key=lambda x: self.get_local_available(x))

    def get_list_channels_high_outbound(self):
        channels = []
        for channel in self.get_list_channels():
            ratio = self.get_ratio_channel(channel)
            if ratio['local'] < ratio['remote']:
                channels.append(channel)
        return sorted(channels, key=lambda x: self.get_remote_available(x), reverse=True)

    def get_local_available_percentage(self, channel: dict):
        local_available = self.get_local_available(channel)
        capacity_available = self.get_capacity_available(channel)
        return round((local_available / float(capacity_available)) * 100)

    def get_remote_available_percentage(self, channel: dict):
        remote_available = self.get_remote_available(channel)
        capacity_available = self.get_capacity_available(channel)
        return round((remote_available / float(capacity_available)) * 100)

    def parser_expr(self, channel: dict):
        SPECIAL_CHARS = [
            'REMOTE_AVAILABLE_PERCENTAGE', 'LOCAL_AVAILABLE_PERCENTAGE',
            'LOCAL_AVAILABLE', 'REMOTE_AVAILABLE', 'CAPACITY_AVAILABLE',
            'LOCAL_FEE_RATE', 'LOCAL_FEE_BASE',
            'REMOTE_FEE_RATE', 'REMOTE_FEE_BASE'
        ]
        channel['local_fee_rate'] = self.lnd.get_fee_rate_local(channel['chan_id'])
        channel['local_fee_base'] = self.lnd.get_fee_base_local(channel['chan_id'])

        channel['remote_fee_rate'] = self.lnd.get_fee_rate_remote(channel['chan_id'])
        channel['remote_fee_base'] = self.lnd.get_fee_base_remote(channel['chan_id'])

        channel['local_available'] = self.get_local_available(channel)
        channel['remote_available'] = self.get_remote_available(channel)
        channel['capacity_available'] = self.get_capacity_available(channel)

        channel['local_available_percentage'] = self.get_local_available_percentage(channel)
        channel['remote_available_percentage'] = self.get_remote_available_percentage(channel)

        for expr in self.expressions:
            expr = expr[3:-1] if ('IF' in expr) else expr
            expr = ' '.join(
                list(map(lambda x: str(channel[x.lower()]) if x in SPECIAL_CHARS else x, expr.split()))
            )
            if (not '__import__' in expr) or (not 'eval' in expr) or (not '__' in expr):
                return eval(parser(expr).compile(), {'__builtins__': {}}, {})
            else:
                return False
        return True

    def loop_rebalance(self, channel: dict):
        rebalanced_channels = []
        while int(time() - self.timestamp) < self.timeout:
            if not self.parser_expr(self.lnd.filter_list_channel(channel['chan_id'])[0]):
                break
            if self.total_rebalance_fees >= self.max_total_fees:
                break
            if self.total_rebalance_channels >= self.limit_rebalance:
                break

            rebalance = self.rebalance(channel['remote_pubkey'])
            if rebalance['error']:
                break
            else:
                self.total_rebalance_fees += int(float(rebalance['rebalance']['rebalance_fees_spent']) * pow(10, 8))
                self.total_rebalance_amount += self.amount
                self.total_rebalance_channels += 1
                rebalanced_channels.append(rebalance)
        return rebalanced_channels

    @staticmethod
    def parser_rebalance(rebalance: str):
        print(rebalance)
        if 'err' in rebalance:
            message = rebalance[rebalance.index('err:') + 4:].replace('-', '').replace('\n', '').split()[1]
            return {'error': True, 'message': message}
        else:
            d = {'error': False, 'hops': [], 'rebalance': {}}
            k = ''
            for x in rebalance.split('\n'):
                x = x.strip().replace(':', '').replace('-', '')
                if 'evaluating' != k and 'evaluating' == x:
                    k = 'evaluating'
                elif 'rebalance' != k and 'rebalance' == x:
                    k = 'rebalance'
                else:
                    z = x.split()
                    if len(z) == 6 and k == 'evaluating':
                        d['hops'].append({'alias': z[0], 'pubkey': z[1][:-1]})
                    elif len(z) == 2 and k == 'rebalance':
                        d['rebalance'].update({z[0]: z[1]})
                    elif len(z) == 3 and k == 'rebalance':
                        d['rebalance'].update({z[0]: z[2][1:-1]})
                    else:
                        if len(z) == 3:
                            d[z[0]] = {'alias': z[1], 'pubkey': z[2]}
                        if len(z) == 2:
                            d[z[0]] = z[1]
            return d

    def rebalance(self, channel_in: str):
        if exists('/usr/local/bin/bos'):
            command = '/usr/local/bin/bos rebalance'
        else:
            command = '/usr/bin/bos rebalance'

        channel_in = self.lnd.get_node_alias(channel_in)
        self.excluded.append(channel_in)
        channel_out = self.lnd.get_node_alias(
            choice(self.get_list_channels_high_outbound())['remote_pubkey']
        )
        self.excluded.remove(channel_in)

        command += f' --amount {int(self.amount)} --out {channel_out} --in {channel_in}'
        if self.fee_limit_fixed:
            command += f' --max-fee {int(self.fee_limit_fixed)}'
        elif self.fee_limit_percent:
            command += f' --max-fee-rate {int(self.fee_limit_percent)}'
        for channel in self.excluded:
            command += f' --avoid {channel.replace(" ", "")}'

        command += ' --no-color --minutes 1'
        if self.node_save:
            command += f' --node {self.node_save}'
        return self.parser_rebalance(popen(f'{command} 2>&1').read().strip())
