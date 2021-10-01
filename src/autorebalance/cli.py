from time import time
from rich import box
from .rebalance import Rebalance, Lnd

from rich.live import Live
from rich.table import Table
from rich.syntax import Syntax
from rich.console import Console

import click

console = Console()

@click.group()
@click.option(
    '--lnddir', '-d', default='~/.lnd', show_default=True,
    help='Say where is the lnd folder.'
)
@click.option(
    '--rpc', '-s', default='127.0.0.1:8080', show_default=True,
    help='Say what the RPC host:port is.'
)
@click.option(
    '--network', '-n', default='mainnet', show_default=True,
    help='Say which network lnd is using.'
)
@click.pass_context
def cli(ctx: object, lnddir: str, rpc: str, network: str):
    from yaml import safe_load
    from pathlib import Path
    from os.path import expanduser

    path = Path(expanduser('~/.autorebalance/config.yaml'))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)

    ctx.ensure_object(dict)
    config = safe_load(path.open())
    config = config if config else {}

    if config.get('lnddir') and lnddir == '~/.lnd':
        lnddir = config.get('lnddir')
        del config['lnddir']

    if config.get('rpc') and rpc == '127.0.0.1:8080':
        rpc = config.get('rpc')
        del config['rpc']

    if config.get('network') and network == 'mainnet':
        network = config.get('network')
        del config['network']

    lnddir = expanduser(lnddir)
    ctx.obj.update(config)
    ctx.obj.update({'lnddir': lnddir, 'rpc': rpc, 'network': network})


@cli.command()
@click.pass_context
def listchannels(ctx: object):
    """List all channels."""
    table = Table(box=box.SIMPLE)
    table.add_column('\nInbound', justify='right', style='bright_red')
    table.add_column('\nRatio', justify='center', style='bright_red')
    table.add_column('\nOutbound', justify='right', style='green')
    table.add_column('Local\nBase Fee\n(msat)', justify='center', style='bright_blue')
    table.add_column('Local\nFee Rate\n(ppm)', justify='center', style='bright_blue')
    table.add_column('Remote\nBase Fee\n(msat)', justify='center', style='bright_yellow')
    table.add_column('Remote\nFee Rate\n(ppm)', justify='center', style='bright_yellow')
    table.add_column('\nAlias', max_width=25, no_wrap=True)

    lightning = Lnd(
        lnddir=ctx.obj['lnddir'], rpc=ctx.obj['rpc'], network=ctx.obj['network']
    )
    rebalance = Rebalance(
        lnd=lightning, excluded=ctx.obj.get('excluded', [])
    )
    for channel in rebalance.get_list_channels():
        alias = lightning.get_node_alias(channel['remote_pubkey'])
        ratio = rebalance.get_ratio_channel(channel)
        ratio = (
                '[bright_red]'
                + ('·' * ratio['remote'])
                + '[/bright_red]'
                + '|' + '[green]'
                + ('·' * ratio['local'])
                + '[/green]'
        )
        local_available = rebalance.get_local_available(channel)
        local_base_fee = lightning.get_fee_base_local(channel['chan_id'])
        local_fee_rate = lightning.get_fee_rate_local(channel['chan_id'])

        remote_available = rebalance.get_remote_available(channel)
        remote_base_fee = lightning.get_fee_base_remote(channel['chan_id'])
        remote_fee_rate = lightning.get_fee_rate_remote(channel['chan_id'])

        table.add_row(
            f'{remote_available:,}',
            ratio,
            f'{local_available:,}',
            f'{local_base_fee:,}',
            f'{local_fee_rate:,}',
            f'{remote_base_fee:,}',
            f'{remote_fee_rate:,}',
            alias
        )
    if table.rows:
        console.print(table)


@cli.command('rebalance')
@click.option(
    '--amount', '-a', default=50_000, help='Enter the rebalancing amount.'
)
@click.option(
    '--timeout', '-t', default=300, show_default=True, help='Specify a timeout'
)
@click.option(
    '--fee-limit', '-f', default=0, show_default=True, help='Specify a fee limit on sats.'
)
@click.option(
    '--fee-ppm-limit', default=0, show_default=True, help='Specify a fee rate limit on sats.'
)
@click.option(
    '--max-total-fees', default=5_000, show_default=True, help='Specify a total accumulated fees.'
)
@click.option(
    '--excluded', multiple=True, show_default=True, help='Specify channels that should be ignored.'
)
@click.option(
    '--expressions', multiple=True, show_default=True,
    help='Specify expressions that will be used to determine whether a channel continues to be rebalanced or not.'
)
@click.option(
    '--limit-rebalance', default=1, show_default=True, help='Limits the rebalancing amount.'
)
@click.option(
    '--node-save', help='Node to use for rebalance.'
)
@click.pass_context
def rebalance_channels(ctx: object, **kwargs: dict):
    """Rebalance unbalanced channels."""
    if ctx.obj.get('amount') and int(kwargs.get('amount')) == 50_000:
        kwargs['amount'] = ctx.obj.get('amount')

    if ctx.obj.get('timeout') and (kwargs.get('timeout') == 300):
        kwargs['timeout'] = ctx.obj.get('timeout')

    if ctx.obj.get('fee_limit') and (not kwargs.get('fee_limit')):
        kwargs['fee_limit'] = ctx.obj.get('fee_limit')

    if ctx.obj.get('fee_ppm_limit') and (not kwargs.get('fee_ppm_limit')):
        kwargs['fee_ppm_limit'] = ctx.obj.get('fee_ppm_limit')

    if ctx.obj.get('max_total_fees') and (kwargs.get('max_total_fees') == 5_000):
        kwargs['max_total_fees'] = ctx.obj.get('max_total_fees')

    if ctx.obj.get('excluded') and (not kwargs.get('excluded')):
        kwargs['excluded'] = ctx.obj.get('excluded')

    if ctx.obj.get('expressions') and (not kwargs.get('expressions')):
        kwargs['expressions'] = ctx.obj.get('expressions')

    if ctx.obj.get('limit_rebalance') and kwargs.get('limit_rebalance') == 1:
        kwargs['limit_rebalance'] = ctx.obj.get('limit_rebalance')

    if ctx.obj.get('node_save') and (not kwargs.get('node_save')):
        kwargs['node_save'] = ctx.obj.get('node_save')

    lightning = Lnd(
        lnddir=ctx.obj['lnddir'], rpc=ctx.obj['rpc'], network=ctx.obj['network']
    )
    if not kwargs.get('fee_limit') and not kwargs.get('fee_ppm_limit'):
        console.print('[bright_yellow]You have not set --fee-limit or --fee-ppm-limit![/bright_yellow]')
        raise click.Abort()

    if int(kwargs.get('amount')) < 50_000:
        console.print('[bright_yellow]Amount must be greater than 50K sats.[/bright_yellow]')
        raise click.Abort()

    table = Table(box=box.SIMPLE)
    table.add_column('Rebalance (Amount)', justify='center', style='#26a99f')
    table.add_column('Rebalance (Fees)', justify='center', style='bright_yellow')
    table.add_column('Channel (Out)', justify='center', style='bright_red')
    table.add_column('Channel (Route)', justify='center', style='#326d5e')
    table.add_column('Channel (In)', justify='center', style='bright_green')

    rebalance = Rebalance(
        lnd=lightning,
        amount=kwargs.get('amount'),
        timeout=kwargs.get('timeout'),
        node_save=kwargs.get('node_save'),
        max_total_fees=kwargs.get('max_total_fees'),
        fee_limit_fixed=kwargs.get('fee_limit'),
        fee_limit_percent=kwargs.get('fee_ppm_limit'),
        excluded=kwargs.get('excluded'),
        expressions=kwargs.get('expressions'),
        limit_rebalance=kwargs.get('limit_rebalance')
    )
    print(rebalance.get_list_channels_low_outbound())
    for channel_low_outbound in rebalance.get_list_channels_low_outbound():
        loop_rebalanced_channel = rebalance.loop_rebalance(channel_low_outbound)
        if loop_rebalanced_channel:
            for rebalanced_channel in loop_rebalanced_channel:
                rebalanced_fees = int(
                    float(rebalanced_channel['rebalance']['rebalance_fees_spent']) * pow(10, 8)
                )
                rebalanced_hop_in = rebalanced_channel['hops'][-1]['alias']
                rebalanced_hop_out = rebalanced_channel['hops'][0]['alias']

                rebalanced_hop_route = rebalanced_channel['hops']
                rebalanced_hop_route = rebalanced_hop_route[
                    int(len(rebalanced_channel['hops']) / 2)]['alias']

                table.add_row(
                    f'{int(kwargs["amount"]):,}',
                    f'{rebalanced_fees:,}',
                    str(rebalanced_hop_out),
                    str(rebalanced_hop_route),
                    str(rebalanced_hop_in)
                )

    if table.rows:
        table.add_row(
            '─' * (len(f'{rebalance.total_rebalance_amount:,}') + 2),
            '─' * (len(f'{rebalance.total_rebalance_fees:,}') + 2),
            )
        table.add_row(
            f'{rebalance.total_rebalance_amount:,}',
            f'{rebalance.total_rebalance_fees:,}',
        )
        console.print(table)
    else:
        console.print('[bright_yellow]No channels have been rebalanced.[/bright_yellow]')
        raise click.Abort()
