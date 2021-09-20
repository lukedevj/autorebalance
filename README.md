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

### Check if it is working properly.
```bash
$ autorebalance --help
Usage: autorebalance [OPTIONS] COMMAND [ARGS]...

Options:
  -d, --lnddir TEXT   Say where is the lnd folder.  [default: ~/.lnd]
  -s, --rpc TEXT      Say what the RPC host:port is.  [default:
                      127.0.0.1:8080]
  -n, --network TEXT  Say which network lnd is using.  [default: mainnet]
  --help              Show this message and exit.

Commands:
  listchannels  List all channels.
  rebalance     Rebalance unbalanced channels.

```

## Setting up configuration file.

```bash
# You can configure the software using the configuration file or by passing arguments through the command line.
$ nano ~/.autorebalance/config.yaml
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
fee_limit: 5 # or fee_ppm_limit
max_total_fees: 5000
limit_rebalance: 1

# Rebalancing Rules while the result is True it will be executed in Loop until the expression is False.
expressions:
  - IF(LOCAL_AVAILABLE != 50 and LOCAL_FEE_RATE < 3000)

  # REMOTE_AVAILABLE_PERCENTAGE, LOCAL_AVAILABLE_PERCENTAGE, LOCAL_AVAILABLE
  # REMOTE_AVAILABLE, CAPACITY_AVAILABLE, LOCAL_FEE_RATE, LOCAL_FEE_BASE
  # REMOTE_FEE_RATE, REMOTE_FEE_BASE

# Ignore these channels.
excluded:
  - CHANNEL_ALIAS
```
### List all channels.
```python
$ autorebalance listchannels
                                         Local      Local      Remote     Remote           
    Inbound      Ratio       Outbound   Base Fee   Fee Rate   Base Fee   Fee Rate   Alias  
                                         (msat)     (ppm)      (msat)     (ppm)            
 ───────────────────────────────────────────────────────────────────────────────────────── 
          0   |··········   1,976,530    1,000        1        1,000        1       Alice  
    976,528   ·····|·····     980,002    1,000        1        1,000        1       Alice  
  1,976,530   ··········|           0    1,000        1        1,000        1       Bob    
    980,000   ······|····     976,530    1,000        1        1,000        1       Bob 
```
### Rebalance unbalanced channels.

```python
$ autorebalance rebalance

  Rebalance (Amount)   Rebalance (Fees)   Channel (Out)   Channel (Route)   Channel (In)  
 ──────────────────────────────────────────────────────────────────────────────────────── 
        50,000                2               Alice            Frank            Bob       
       ────────              ───                                                          
        50,000                2                                                                 
```
```python
$ autorebalance listchannels

    Inbound      Ratio       Outbound   Base Fee   Fee Rate   Base Fee   Fee Rate   Alias  
                                         (msat)     (ppm)      (msat)     (ppm)            
 ───────────────────────────────────────────────────────────────────────────────────────── 
     80,008   ·|·········   1,876,521    1,000        1        1,000        1       Alice  
    976,528   ·····|·····     980,002    1,000        1        1,000        1       Alice  
  1,926,529   ··········|      30,001    1,000        1        1,000        1       Bob    
    929,999   ·····|·····   1,026,531    1,000        1        1,000        1       Bob 
```

