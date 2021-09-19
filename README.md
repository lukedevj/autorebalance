# Auto Rebalance

This software was developed to facilitate the automatic rebalancing of LN channels, with defined rules.

[![Donate](https://img.shields.io/badge/Donate-Bitcoin-green.svg)](https://coinos.io/lukedevj)

## Requirements

- [Python >= 3.6](https://www.python.org/)
- [LND](https://github.com/LightningNetwork/lnd)
- [BOS](https://github.com/alexbosworth/balanceofsatoshis)

## Install
```bash
$ git clone https://github.com/lukedevj/autorebalance.git
$ cd ./autorebalance
$ python3 setup.py install --user
```

Check if it is working properly.
```bash
$ autorebalance --help
Usage: autorebalance [OPTIONS] COMMAND [ARGS]...

Options:
  -d, --lnddir TEXT   Say where is the lnd folder.  [default: ~/lnd]
  -s, --rpc TEXT      Say what the RPC host:port is.  [default:
                      127.0.0.1:8080]
  -n, --network TEXT  Say which network lnd is using.  [default: mainnet]
  --help              Show this message and exit.

Commands:
  listchannels
  rebalance     Rebalance unbalanced channels.
```

You can configure the software using the configuration file or by passing arguments through the command line.

```bash
nano ~/.autorebalance/config.yaml
```
```yaml

# Configuration LND.
lnddir: ~/lnd
rpc: 127.0.0.1:8080
network: mainnet
node_save: BOS_NODE_ALIAS

# Configuration Rebalance.
amount: 50000
timeout: 300
fee_limit: 5
max_total_fees: 5000
limit_rebalance: 1

# Rebalancing Rules while the result is True it will be executed in Loop until the expression is False.
expressions:
  - IF(LOCAL_AVAILABLE != 50 and LOCAL_FEE_RATE < 3000)

# Ignore these channels.
excluded:
  - Alias 2
  - Alias 3
```
