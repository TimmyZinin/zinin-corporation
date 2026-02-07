"""CrewAI Tool: Papaya Finance — check streaming payment positions on EVM chains.

Papaya is a non-custodial stablecoin subscription/streaming protocol.
Uses direct JSON-RPC calls via httpx — no web3.py dependency.
"""

import logging
import time
from typing import Optional

import httpx
from crewai.tools import BaseTool

logger = logging.getLogger(__name__)

# ── Precomputed function selectors (keccak256) ──────────────
SEL_BALANCE_OF = "0x70a08231"  # balanceOf(address)
SEL_USERS = "0xa87430ba"  # users(address) → (int256,int256,int256,uint256)
SEL_ALL_SUBS = "0xdaf36e74"  # allSubscriptions(address) → (address[],uint256[])

SECONDS_PER_MONTH = 2_628_000
SCALE = 10**18  # Papaya uses 18 decimals internally

# ── Papaya contract addresses (latest versions per chain) ───
PAPAYA_CONTRACTS = {
    "polygon": {
        "USDC": "0x2D69c25c7d37FdEC82C39c90fD0F3D2460ccBa9A",
        "USDT": "0x965a2957bd4655e59aF0BB362a3F457CA9002913",
    },
    "bsc": {
        "USDC": "0x737F7D6AF09Fc2748a72D40F1b3faCd925343819",
        "USDT": "0xae22e28D7FAD4f6daF09AFf2061Be05dCe4BcF1c",
    },
    "arbitrum": {
        "USDC": "0x574DeD69a731B5e19e1dD6861D1Cc33cfE7dB45c",
        "USDT": "0x1c3E45F2D9Dd65ceb6a644A646337015119952ff",
    },
    "ethereum": {
        "USDC": "0x1c3E45F2D9Dd65ceb6a644A646337015119952ff",
        "USDT": "0xb8fD71A4d29e2138056b2a309f97b96ec2A8EeD7",
        "PYUSD": "0x444a597c2DcaDF71187b4c7034D73B8Fa80744E2",
        "DAI": "0x566CBD7eB900C5eC1E7B6D872DAE845Ce6060DDE",
    },
    "base": {
        "USDC": "0x574DeD69a731B5e19e1dD6861D1Cc33cfE7dB45c",
    },
    "avalanche": {
        "USDC": "0x1c3E45F2D9Dd65ceb6a644A646337015119952ff",
        "USDT": "0x574DeD69a731B5e19e1dD6861D1Cc33cfE7dB45c",
    },
    "scroll": {
        "USDC": "0x574DeD69a731B5e19e1dD6861D1Cc33cfE7dB45c",
        "USDT": "0x1c3E45F2D9Dd65ceb6a644A646337015119952ff",
    },
}

# ── Public RPC endpoints (free, no API key needed) ──────────
RPC_URLS = {
    "polygon": "https://polygon-rpc.com",
    "bsc": "https://bsc-dataseed1.binance.org",
    "arbitrum": "https://arb1.arbitrum.io/rpc",
    "ethereum": "https://eth.llamarpc.com",
    "base": "https://mainnet.base.org",
    "avalanche": "https://api.avax.network/ext/bc/C/rpc",
    "scroll": "https://rpc.scroll.io",
}


def _pad_address(address: str) -> str:
    """Pad address to 32 bytes for ABI encoding."""
    addr = address.lower().replace("0x", "")
    return addr.zfill(64)


def _eth_call(rpc_url: str, contract: str, data: str) -> str:
    """Make a raw eth_call JSON-RPC request."""
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [{"to": contract, "data": data}, "latest"],
        "id": 1,
    }
    resp = httpx.post(rpc_url, json=payload, timeout=10)
    resp.raise_for_status()
    result = resp.json()
    if "error" in result:
        raise ValueError(f"RPC error: {result['error']}")
    return result.get("result", "0x")


def _decode_uint256(hex_str: str) -> int:
    """Decode a single uint256 from hex."""
    clean = hex_str.replace("0x", "")
    if not clean or clean == "0" * 64:
        return 0
    return int(clean, 16)


def _decode_int256(hex_str: str) -> int:
    """Decode a single int256 from hex (two's complement)."""
    val = int(hex_str, 16)
    if val >= 2**255:
        val -= 2**256
    return val


def get_papaya_balance(address: str, chain: str, token: str) -> Optional[dict]:
    """Get Papaya position for one address on one chain/token."""
    if chain not in PAPAYA_CONTRACTS or token not in PAPAYA_CONTRACTS[chain]:
        return None
    if chain not in RPC_URLS:
        return None

    contract = PAPAYA_CONTRACTS[chain][token]
    rpc = RPC_URLS[chain]
    padded = _pad_address(address)

    # 1) balanceOf(address) → uint256
    data = SEL_BALANCE_OF + padded
    raw = _eth_call(rpc, contract, data)
    balance_raw = _decode_uint256(raw)

    # 2) users(address) → (int256 balance, int256 incomeRate, int256 outgoingRate, uint256 updated)
    data = SEL_USERS + padded
    raw = _eth_call(rpc, contract, data)
    clean = raw.replace("0x", "")
    if len(clean) < 256:
        clean = clean.ljust(256, "0")

    stored_balance = _decode_int256(clean[0:64])
    income_rate = _decode_int256(clean[64:128])
    outgoing_rate = _decode_int256(clean[128:192])
    updated = int(clean[192:256], 16)

    # Skip if completely empty
    if balance_raw == 0 and stored_balance == 0 and income_rate == 0 and outgoing_rate == 0:
        return None

    net_rate = income_rate - outgoing_rate
    balance_human = balance_raw / SCALE

    result = {
        "chain": chain,
        "token": token,
        "balance": round(balance_human, 6),
        "balance_raw": balance_raw,
        "income_monthly": round(income_rate * SECONDS_PER_MONTH / SCALE, 4),
        "outgoing_monthly": round(outgoing_rate * SECONDS_PER_MONTH / SCALE, 4),
        "net_monthly": round(net_rate * SECONDS_PER_MONTH / SCALE, 4),
        "last_updated": updated,
    }

    # Time until zero (if depleting)
    if net_rate < 0 and balance_raw > 0:
        secs = int(balance_raw / abs(net_rate))
        result["days_until_zero"] = round(secs / 86400, 1)

    return result


def get_all_papaya_positions(addresses: list[str]) -> list[dict]:
    """Check all Papaya contracts across all chains for multiple addresses."""
    positions = []
    for address in addresses:
        for chain, tokens in PAPAYA_CONTRACTS.items():
            if chain not in RPC_URLS:
                continue
            for token in tokens:
                try:
                    pos = get_papaya_balance(address, chain, token)
                    if pos:
                        pos["address"] = address
                        positions.append(pos)
                except Exception as e:
                    logger.debug(f"Papaya {chain}/{token}/{address[:10]}: {e}")
    return positions


def _load_evm_addresses() -> list[str]:
    """Load EVM addresses from financial config."""
    import os
    import yaml

    for path in ["config/financial_sources.yaml", "/app/config/financial_sources.yaml"]:
        if os.path.exists(path):
            with open(path, "r") as f:
                config = yaml.safe_load(f) or {}
            addrs = config.get("crypto_wallets", {}).get("evm", {}).get("addresses", [])
            return [a for a in addrs if a]
    return []


class PapayaPositionsTool(BaseTool):
    name: str = "papaya_positions"
    description: str = (
        "Баланс в протоколе Papaya Finance (стриминговые платежи стейблкоинами).\n"
        "Проверяет все EVM-адреса Тима на всех цепях (Polygon, BSC, Arbitrum, Base, Ethereum, Avalanche, Scroll).\n"
        "Показывает: баланс USDC/USDT, входящие/исходящие подписки, дней до обнуления.\n"
        "Параметр: EVM-адрес (опционально — если не указан, берёт из конфига)."
    )

    def _run(self, argument: str = "") -> str:
        try:
            # Use provided address or load from config
            if argument.strip().startswith("0x"):
                addresses = [argument.strip()]
            else:
                addresses = _load_evm_addresses()

            if not addresses:
                return (
                    "Нет EVM-адресов для проверки Papaya. "
                    "Укажи адрес: papaya_positions address=0x... "
                    "или добавь адреса в config/financial_sources.yaml → crypto_wallets.evm.addresses"
                )

            positions = get_all_papaya_positions(addresses)

            if not positions:
                checked = len(addresses) * sum(len(t) for t in PAPAYA_CONTRACTS.values())
                return (
                    f"Papaya Finance: позиций не найдено.\n"
                    f"Проверено: {len(addresses)} адрес(ов) × {checked // len(addresses)} контрактов "
                    f"на {len(RPC_URLS)} сетях."
                )

            lines = ["PAPAYA FINANCE — позиции:", ""]
            total_usd = 0

            for pos in positions:
                addr_short = pos["address"][:6] + "..." + pos["address"][-4:]
                lines.append(f"  {pos['chain'].upper()} / {pos['token']}  [{addr_short}]")
                lines.append(f"    Баланс: {pos['balance']:,.4f} {pos['token']}")
                total_usd += pos["balance"]

                if pos["income_monthly"] > 0 or pos["outgoing_monthly"] > 0:
                    lines.append(f"    Входящие: +{pos['income_monthly']:,.4f}/мес")
                    lines.append(f"    Исходящие: -{pos['outgoing_monthly']:,.4f}/мес")
                    lines.append(f"    Нетто: {pos['net_monthly']:+,.4f}/мес")

                if pos.get("days_until_zero"):
                    lines.append(f"    ⚠️ Обнулится через {pos['days_until_zero']} дней!")

                lines.append("")

            lines.append(f"ИТОГО в Papaya: ~${total_usd:,.2f}")
            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Papaya positions fetch failed: {e}")
            return f"Ошибка Papaya: {e}"
