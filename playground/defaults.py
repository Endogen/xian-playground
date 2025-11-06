"""Shared defaults for the playground UI."""

DEFAULT_CONTRACT = """\
balances = Hash(default_value=0)


@construct
def seed():
    balances['treasury'] = 1_000


@export
def transfer(to: str, amount: int):
    assert amount > 0, 'Amount must be positive.'
    assert balances[ctx.caller] >= amount, 'Insufficient balance.'

    balances[ctx.caller] -= amount
    balances[to] += amount


@export
def balance_of(account: str):
    return balances[account]
"""

DEFAULT_CONTRACT_NAME = "con_demo_token"
DEFAULT_KWARGS_INPUT = "{}"
