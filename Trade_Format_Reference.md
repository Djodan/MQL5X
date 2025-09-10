# Trade Format Reference

This document summarizes the trade/position formats observed from:
- MQL5X EA -> HTTP Server (`Server.py`)
- TopStepX API -> Open Positions (`TopStepX_Files/Return_Open_Trades.py`)

Generated on: 2025-09-09

## MQL5X (EA -> Server.py)

The EA POSTs JSON payloads to the local server. Example fields (from `received_log.jsonl` and live run):

Top-level:
- id: number (session or feed identifier)
- mode: string (e.g., "Sender")
- open: array of open positions
- closed_offline: array of recently closed positions reconciled offline
- closed_online: array of recently closed positions reconciled online

Open position object:
- ticket: number (MT5 position ticket)
- symbol: string (e.g., "LITECOIN")
- type: number (0 = BUY, 1 = SELL)
- volume: number (lots or units; EA-config dependent)
- openPrice: number (entry price)
- price: number (current price)
- sl: number (stop loss)
- tp: number (take profit)
- magic: number (magic number)
- comment: string

Closed trade object (closed_offline/closed_online):
- deal: number (deal/ticket id)
- symbol: string
- type: number (0 = BUY, 1 = SELL)
- volume: number
- openPrice: number (may be 0.0 when not provided)
- closePrice: number
- profit: number
- swap: number
- commission: number
- closeTime: number (epoch seconds)

Notes:
- The server prints a human-readable summary, but the full payloads are appended to `received_log.jsonl` as JSONL for downstream parsing/audit.
- EA internals track an `openTime` per position, but current payload does not include it. If needed later, add it via `Json.mqh` (field openTime: epoch seconds).
- MQL5 enums observed:
  - POSITION_TYPE_BUY=0, POSITION_TYPE_SELL=1 (maps to `type` in open[])
  - DEAL_ENTRY_OUT used for closed trades in `OnTradeTransaction` (online closes)
  - `closeTime` values are epoch seconds (datetime casted to int).

Server endpoints used by the EA:
- POST `/` with the JSON payload above (Content-Type: application/json)
- GET `/health` for connectivity checks
- GET `/message` to fetch a simple `{ "message": "..." }`

When it sends:
- OnInit: initial SendArrays()
- OnTimer: periodic SendArrays(), prints, and FetchAndPrintMessage()

## TopStepX (Return_Open_Trades.py)

`TopStepX_Files/Return_Open_Trades.py` POSTs to `https://api.topstepx.com/api/Position/searchOpen` with body:
- accountId: number

Sample response captured during run:
```
Status: 200
Open Trades Response: {
  'positions': [
    {
      'id': 360018684,
      'accountId': 11357588,
      'contractId': 'CON.F.US.GCE.Z25',
      'creationTimestamp': '2025-09-10T01:49:30.104906+00:00',
      'type': 1,
      'size': 2,
      'averagePrice': 3668.0
    }
  ],
  'success': True,
  'errorCode': 0,
  'errorMessage': None
}
```

Position object (in `positions` array):
- id: number (position id)
- accountId: number
- contractId: string (instrument identifier, e.g., futures contract)
- creationTimestamp: ISO8601 timestamp (UTC)
- type: number (position direction; in orders API, side uses 0 = Buy, 1 = Sell; positions `type` likely follows same convention)
- size: number (contracts)
- averagePrice: number (position average price)

Envelope fields:
- success: boolean
- errorCode: number
- errorMessage: string | null

Related endpoints used in this repo:
- Account/search (POST): payload { onlyActiveAccounts: bool }; response { accounts: [{ id, name, balance, ... }], success, errorCode, errorMessage }
- Contract/available (POST): payload { accountId, live: bool }; response { contracts: [{ id, name, description, ... }], ... }
- Order/place (POST): see “Order placement payloads” below
- Order/searchOpen (POST): payload { accountId }; response { orders: [...] }
- Order/modify (POST): payload { orderId, accountId, contractId, type, side, size, stopPrice? limitPrice? }
- Position/closeContract (POST): payload { accountId, contractId }
- Position/partialCloseContract (POST): payload { accountId, contractId, size }

Order placement payloads (observed):
- Market entry:
  { accountId, contractId, type: 2, side: 0|1, size }
- Limit order (e.g., TP):
  { accountId, contractId, type: 1, side: 0|1, size, limitPrice }
- Stop order (e.g., SL):
  { accountId, contractId, type: 4, side: 0|1, size, stopPrice }
- Optional brackets (as used in `Open_Trade.py` when placing a market order):
  { accountId, contractId, type: 2, side: 0|1, size,
    bracket1: { action: "Buy"|"Sell", orderType: "Limit"|"Stop", price?: number, stopPrice?: number },
    bracket2: { action: "Buy"|"Sell", orderType: "Limit"|"Stop", price?: number, stopPrice?: number }
  }
  Note: The repository also demonstrates placing TP/SL as separate orders (preferred if bracket fields are not available in all environments).

## Cross-mapping (at-a-glance)

- Direction: MQL5 `type` (0 BUY, 1 SELL) ↔ TopStepX position `type` (likely 0 Buy, 1 Sell)
- Quantity: MQL5 `volume` ↔ TopStepX `size`
- Price: MQL5 `openPrice` (entry) ↔ TopStepX `averagePrice`
- Instrument: MQL5 `symbol` (e.g., "LITECOIN") ↔ TopStepX `contractId` (e.g., "CON.F.US.GCE.Z25"). A symbol-to-contract mapping step is needed when reconciling across platforms.
- Time: MQL5 closed trades use `closeTime` (epoch seconds); TopStepX uses `creationTimestamp` (ISO8601). Convert as needed.

## How to regenerate

- MQL5 format:
  1) Start the server
     - PowerShell: `python Server.py --host 0.0.0.0 --port 5000`
  2) Allow WebRequest in MetaTrader 5 for `http://<host>:<port>` and trigger EA updates
  3) Inspect `received_log.jsonl` or server stdout

- TopStepX format:
  - PowerShell: `python TopStepX_Files/Return_Open_Trades.py`

## Notes
- If TopStepX token expires, run `TopStepX_Files/Connector.py` to obtain a fresh access token and update `TopStepX_Files/Globals.py`.
- Avoid committing tokens or secrets.

## Unified format (canonical) ✅

Goal: one canonical shape that contains everything needed to represent an open position or a closed trade from either source (MQL5 EA or TopStepX), plus a small wrapper for batches.

### Canonical wrapper

Use this envelope when exchanging batches between components.

```
{
  "version": "1.0",
  "source": "MQL5|TopStepX|Bridge",
  "timestamp": "2025-09-09T02:11:00Z",
  "openPositions": [ CanonicalOpenPosition, ... ],
  "closedTrades": [ CanonicalClosedTrade, ... ]
}
```

### CanonicalOpenPosition

```
{
  "positionId": "string",          // MQL5: ticket (stringified); TopStepX: id (stringified)
  "accountId": "string|null",      // TopStepX: accountId; MQL5: null unless provided
  "instrument": {
    "symbol": "string|null",       // MQL5: symbol
    "contractId": "string|null"    // TopStepX: contractId
  },
  "side": "BUY|SELL",              // Direction normalized to strings
  "quantity": 0.0,                  // MQL5: volume; TopStepX: size
  "prices": {
    "openPrice": 0.0|null,          // MQL5: openPrice
    "averagePrice": 0.0|null,       // TopStepX: averagePrice
    "currentPrice": 0.0|null        // MQL5: price (if provided)
  },
  "risk": {
    "stopLoss": 0.0|null,           // MQL5: sl (if set)
    "takeProfit": 0.0|null          // MQL5: tp (if set)
  },
  "times": {
    "openedAt": "ISO8601|null",    // TopStepX: creationTimestamp; MQL5: null if not present
    "updatedAt": "ISO8601|null"
  },
  "metadata": {
    "magic": 0|null,                // MQL5 only
    "comment": "string|null"
  },
  "raw": { /* optional original payload */ }
}
```

### CanonicalClosedTrade

```
{
  "dealId": "string",              // MQL5: deal (stringified)
  "accountId": "string|null",
  "instrument": {
    "symbol": "string|null",
    "contractId": "string|null"
  },
  "side": "BUY|SELL",
  "quantity": 0.0,
  "prices": {
    "openPrice": 0.0|null,
    "closePrice": 0.0|null
  },
  "pnl": {
    "profit": 0.0|null,
    "swap": 0.0|null,
    "commission": 0.0|null
  },
  "times": {
    "openedAt": "ISO8601|null",
    "closedAt": "ISO8601|null"
  },
  "metadata": { "comment": "string|null" },
  "raw": { }
}
```

### Example: unified open positions payload

```
{
  "version": "1.0",
  "source": "Bridge",
  "timestamp": "2025-09-09T02:12:00Z",
  "openPositions": [
    {
      "positionId": "278293151",
      "accountId": null,
      "instrument": { "symbol": "LITECOIN", "contractId": null },
      "side": "BUY",
      "quantity": 0.10,
      "prices": { "openPrice": 112.24, "averagePrice": null, "currentPrice": 112.51 },
      "risk": { "stopLoss": 0.0, "takeProfit": 0.0 },
      "times": { "openedAt": null, "updatedAt": null },
      "metadata": { "magic": 0, "comment": "" }
    },
    {
      "positionId": "360018684",
      "accountId": "11357588",
      "instrument": { "symbol": null, "contractId": "CON.F.US.GCE.Z25" },
      "side": "SELL",                     // TopStepX type: 1 ⇒ SELL
      "quantity": 2,
      "prices": { "openPrice": null, "averagePrice": 3668.0, "currentPrice": null },
      "risk": { "stopLoss": null, "takeProfit": null },
      "times": { "openedAt": "2025-09-10T01:49:30.104906+00:00", "updatedAt": null },
      "metadata": { "magic": null, "comment": null }
    }
  ],
  "closedTrades": []
}
```

## Programmable mapping (adapters) 🧩

Adapter contracts to convert between native formats and the canonical format. Use these names in your integration layer.

### Inputs → Canonical

- from_mql5_payload(payload: dict) -> CanonicalEnvelope
  - Maps:
    - open[] → openPositions[] (ticket→positionId; symbol→instrument.symbol; type 0/1→BUY/SELL; volume→quantity; openPrice/price/sl/tp; magic/comment)
    - closed_offline[] + closed_online[] → closedTrades[] (deal→dealId; closeTime epoch→ISO8601)

- from_topstepx_positions(resp: dict) -> CanonicalEnvelope
  - Maps:
    - positions[] → openPositions[] (id→positionId; accountId; contractId→instrument.contractId; type 0/1→BUY/SELL; size→quantity; averagePrice)

### Canonical → Outputs

- to_mql5_open_position(pos: CanonicalOpenPosition) -> dict
  - Returns MQL5-like dict: { ticket, symbol, type(0/1), volume, openPrice, price, sl, tp, magic, comment }
  - Conversions: side BUY/SELL → 0/1; prefer prices.openPrice for openPrice; prices.currentPrice for price.

- to_topstepx_order(pos: CanonicalOpenPosition, extras: { accountId: string, orderType?: number }) -> dict
  - Returns one of the following payloads for Order/place, based on desired intent:
    - Market: { accountId, contractId, type: 2, side: 0|1, size }
    - Limit (TP): { accountId, contractId, type: 1, side: 0|1, size, limitPrice }
    - Stop (SL): { accountId, contractId, type: 4, side: 0|1, size, stopPrice }
    - Market with brackets (optional, as per `Open_Trade.py`):
      { accountId, contractId, type: 2, side: 0|1, size,
        bracket1: { action: "Buy"|"Sell", orderType: "Limit"|"Stop", price?: number, stopPrice?: number },
        bracket2: { action: "Buy"|"Sell", orderType: "Limit"|"Stop", price?: number, stopPrice?: number }
      }
  - Notes: Require contractId; if only symbol is known, look up contract via Contract/available. For TP/SL, you can either use separate orders or the bracket fields (if supported).

## Field-by-field mapping cheatsheet

- ID
  - Canonical.positionId ↔ MQL5.ticket (string) ↔ TopStepX.id (string)
- Account
  - Canonical.accountId ↔ TopStepX.accountId
- Instrument
  - Canonical.instrument.symbol ↔ MQL5.symbol
  - Canonical.instrument.contractId ↔ TopStepX.contractId
- Side
  - Canonical.side(BUY/SELL) ↔ MQL5.type(0/1) ↔ TopStepX.type(0/1)
- Quantity
  - Canonical.quantity ↔ MQL5.volume ↔ TopStepX.size
- Prices
  - Canonical.prices.openPrice ↔ MQL5.openPrice
  - Canonical.prices.currentPrice ↔ MQL5.price
  - Canonical.prices.averagePrice ↔ TopStepX.averagePrice
- Risk
  - Canonical.risk.stopLoss/takeProfit ↔ MQL5.sl/tp
- Times
  - Canonical.times.openedAt ↔ TopStepX.creationTimestamp (ISO8601)
  - MQL5 closeTime (epoch) → Canonical.closedTrades[].times.closedAt (ISO8601)
- Metadata
  - Canonical.metadata.magic/comment ↔ MQL5.magic/comment

## Validation hints

- Enforce side ∈ {BUY, SELL}.
- quantity > 0; for TopStepX, size must be integer contracts.
- contractId required to place TopStepX orders; symbol required to echo back to EA.
- When both openPrice and averagePrice are present, keep both; choose one per target when converting.
 - TopStepX order types observed: 1=Limit, 2=Market, 4=Stop. Side: 0=Buy, 1=Sell.

## Minimal type stubs (Python, optional)

These are illustrative only; implement where convenient.

```python
from dataclasses import dataclass
from typing import Optional, Dict, List

Side = str  # "BUY" | "SELL"

@dataclass
class Instrument:
    symbol: Optional[str]
    contractId: Optional[str]

@dataclass
class Prices:
    openPrice: Optional[float]
    averagePrice: Optional[float]
    currentPrice: Optional[float]

@dataclass
class Risk:
    stopLoss: Optional[float]
    takeProfit: Optional[float]

@dataclass
class Times:
    openedAt: Optional[str]
    updatedAt: Optional[str]

@dataclass
class CanonicalOpenPosition:
    positionId: str
    accountId: Optional[str]
    instrument: Instrument
    side: Side
    quantity: float
    prices: Prices
    risk: Risk
    times: Times
    metadata: Dict[str, object]
    raw: Dict[str, object]

@dataclass
class CanonicalClosedTrade:
    dealId: str
    accountId: Optional[str]
    instrument: Instrument
    side: Side
    quantity: float
    prices: Dict[str, Optional[float]]
    pnl: Dict[str, Optional[float]]
    times: Dict[str, Optional[str]]
    metadata: Dict[str, object]
    raw: Dict[str, object]
```

---

With this canonical shape and adapters, you can read inputs from either side and emit correctly shaped outputs without losing information.

## Operational logging (preferred format)

The Python server emits a concise per-client status line on each command poll. This is the preferred print statement and should remain stable:

```
[YYYY-MM-DDThh:mm:ss+00:00] ID=<id> Open=<count> LastAction=<state> Replies=<n>
```

- Example:
  - `[2025-09-10T03:57:03+00:00] ID=1 Open=1 LastAction=0 Replies=43`
- Fields:
  - ID: EA client identifier
  - Open: number of currently open positions tracked for that client
  - LastAction: state returned in the last /command response (0 no-op, 1 BUY, 2 SELL, 3 CLOSE)
  - Replies: number of polls served for that client

When an order command is delivered or acknowledged, the server may emit supplemental lines:

```
[ts] ORDER -> BUY|SELL <symbol> vol=<lots> TP=<tp|tpPips> SL=<sl|slPips>
[ts] ACK id=<id> cmd=<uuid> success=<bool> Paid=<price|retcode> OrderType=<BUY|SELL> Symbol=<symbol> Volume=<lots> TP=<tp> SL=<sl>
```

These are secondary; the per-client status line above is the canonical operational heartbeat.
