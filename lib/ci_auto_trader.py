import os
from typing import Optional, Literal, Dict, Any, Tuple
from binance_common.configuration import ConfigurationRestAPI
from binance_common.constants import DERIVATIVES_TRADING_USDS_FUTURES_REST_API_PROD_URL
from binance_sdk_derivatives_trading_usds_futures.derivatives_trading_usds_futures import DerivativesTradingUsdsFutures
from binance_sdk_derivatives_trading_usds_futures.rest_api.models import ExchangeInformationResponse
from typing import Optional, Literal
import time
import re
from decimal import Decimal, ROUND_HALF_UP, ROUND_FLOOR, ROUND_CEILING

PositionMode = Literal["ONE_WAY", "HEDGE"]

class CIAutoTrader:


    def __init__(self, data):
        self.action_data = data
        configuration = ConfigurationRestAPI(api_key=os.getenv("BINANCE_API_KEY", None), api_secret=os.getenv("BINANCE_API_SECRET", None),
                                         base_path=DERIVATIVES_TRADING_USDS_FUTURES_REST_API_PROD_URL)
        self.client = DerivativesTradingUsdsFutures(config_rest_api=configuration)

    def execute_action(self):
        print(f"[CRYPTO-INSIGHT] Received command: {self.action_data['action']}")
        if self.action_data["action"] == "OPEN_POSITION":
            self.set_isolated_margin(self.action_data['symbol'])
            print(f"[CRYPTO-INSIGHT] Isolated margin set for: {self.action_data['symbol']}")
            self.set_leverage(self.action_data['symbol'], self.action_data['position']['leverage'])
            print(f"[CRYPTO-INSIGHT] Leverage f{self.action_data['position']['leverage']} set for: {self.action_data['symbol']}")
            position_mode = self.get_position_mode()
            if self.has_open_position(self.action_data['symbol'], self.action_data['direction']):
                print(
                    f"[CRYPTO-INSIGHT] Position for {self.action_data['symbol']} {self.action_data['direction']} already exists, skip opening"
                )
                return None
            opened_position = self.open_position(self.action_data['symbol'], position_mode, self.action_data['position']['position'], self.action_data['direction'])
            print(f"[CRYPTO-INSIGHT] Opened position {self.action_data['position']['position']}: {self.action_data['symbol']}")
            self.set_stop_loss_price(self.action_data['symbol'], self.action_data['position']['sl'], self.action_data['direction'], position_mode)
            print(
                f"[CRYPTO-INSIGHT] Stop loss set at price {self.action_data['position']['sl']} for {self.action_data['symbol']}")
            print(f"[CRYPTO-INSIGHT] Position opened: {opened_position}")
            return opened_position
        elif self.action_data["action"] == "PLACE_TP":
            position_mode = self.get_position_mode()
            self.place_take_profits(self.action_data['symbol'], self.action_data['position']['take_profits'],
                                    self.action_data['direction'], position_mode,
                                    self.action_data['position']['quantity'])
        elif self.action_data["action"] == "DO_TAKE_PROFIT":
            self.do_take_profit(self.action_data['symbol'], self.action_data['quantity'], self.action_data['direction'])
            print(f"[CRYPTO-INSIGHT] Take profit executed: {self.action_data['symbol']}")
        elif self.action_data["action"] == "MOVE_TRAILING_STOP":
            self.move_trailing_stop(self.action_data['symbol'], self.action_data['direction'], self.action_data['new_price'])
            print(f"[CRYPTO-INSIGHT] Trailing stop moved: {self.action_data['symbol']}")
        elif self.action_data["action"] == "SET_BREAK_EVEN":
            self.set_break_even(self.action_data['symbol'], self.action_data['direction'], self.action_data['precision'])
            print(f"[CRYPTO-INSIGHT] Break even set: {self.action_data['symbol']}")
        elif self.action_data["action"] == "FIRE_EARLY_EXIT":
            self.fire_early_exit(self.action_data['symbol'], self.action_data['direction'])
            print(f"[CRYPTO-INSIGHT] Early exit fired: {self.action_data['symbol']}")
        return  None

    def has_open_position(
            self,
            symbol: str,
            direction: Optional[str] = None,  # "LONG"/"SHORT" или None = любая
    ) -> bool:
        rows = self._safe_call(
            self.client.rest_api.position_information_v3,
            symbol=symbol.upper(),
        ) or []

        if not rows:
            return False

        direction = direction.upper()
        position_mode = self.get_position_mode()
        if position_mode == "HEDGE":
            for r in rows:
                if (
                        str(r.position_side).upper() == direction
                        and float(r.position_amt) != 0
                ):
                    return True
            return False
        pos_amt = float(rows[0].position_amt)

        if direction == "LONG":
            return pos_amt > 0
        else:
            return pos_amt < 0

    def round_to_step(self, value, step):
        dval = Decimal(str(value))
        dstep = Decimal(str(step))
        q = dval / dstep
        n = q.to_integral_value(rounding=ROUND_CEILING)
        res = (n * dstep).quantize(dstep)
        return float(res)

    def set_break_even(self, symbol, direction, precision):
        close_qty, position_side, side, be  = self.get_position_size_and_sides(symbol, direction)
        self.move_trailing_stop(symbol, direction,self.round_to_step(be, precision))

    def fire_early_exit(self, symbol, direction):
       close_qty, position_side, side, be  = self.get_position_size_and_sides(symbol, direction)
       if close_qty > 0:
           tp_params: Dict[str, Any] = {
               "symbol": symbol.upper(),
               "side": side,
               "position_side": position_side,
               "quantity": float(close_qty),
               "type": "MARKET",
           }
           position_mode = self.get_position_mode()
           if position_mode == "ONE_WAY":
               tp_params["reduce_only"] = True

           self._safe_call(self.client.rest_api.new_order, **tp_params)

    def move_trailing_stop(self, symbol, direction, price):
        direction = direction.upper()
        position_mode = self.get_position_mode() or "ONE_WAY"  # фолбэк, чтобы не “угадывать”
        position_side = direction if position_mode == "HEDGE" else "BOTH"

        sl_side = "SELL" if direction == "LONG" else "BUY"

        open_algo_orders = self._safe_call(
            self.client.rest_api.current_all_algo_open_orders,
            algo_type="CONDITIONAL",
            symbol=symbol.upper(),
        ) or []

        if not isinstance(open_algo_orders, list):
            open_algo_orders = [open_algo_orders]

        to_cancel = [
            o for o in open_algo_orders
            if str(getattr(o, "side", "")).upper() == sl_side
               and str(getattr(o, "position_side", "")).upper() == position_side
               and str(getattr(o, "order_type", "")).upper() in ("STOP_MARKET", "STOP")
        ]

        for o in to_cancel:
            algo_id = getattr(o, "algo_id", None)
            if algo_id is not None:
                self._safe_call(self.client.rest_api.cancel_algo_order, algoid=int(algo_id))

        params = {
            "algo_type": "CONDITIONAL",
            "symbol": symbol.upper(),
            "side": sl_side,
            "type": "STOP_MARKET",
            "trigger_price": float(price),
            "close_position": "true",
            "position_side": position_side,
            "working_type": "MARK_PRICE",
            "price_protect": "TRUE",
        }
        data = self._safe_call(self.client.rest_api.new_algo_order, **params)

        if not data:
            return None
        if hasattr(data, "algo_id") and data.algo_id is not None:
            return int(data.algo_id)
        if isinstance(data, dict) and "algoId" in data:
            return int(data["algoId"])
        return None

    def get_position_size_and_sides(self, symbol: str, direction: str):
        direction = direction.upper()
        rows = self._safe_call(self.client.rest_api.position_information_v3, symbol=symbol.upper()) or []
        position_mode = self.get_position_mode() or "ONE_WAY"

        if position_mode == "HEDGE":
            row = next((r for r in rows if str(getattr(r, "position_side", "")).upper() == direction), None)
            amt = abs(float(getattr(row, "position_amt", 0.0))) if row else 0.0
            be = float(getattr(row, "break_even_price", 0.0)) if row else 0.0
            position_side = direction
        else:
            row = rows[0] if rows else None
            signed = float(getattr(row, "position_amt", 0.0)) if row else 0.0
            be = float(getattr(row, "break_even_price", 0.0)) if row else 0.0

            if (direction == "LONG" and signed > 0) or (direction == "SHORT" and signed < 0):
                amt = abs(signed)
            else:
                amt = 0.0
            position_side = "BOTH"

        side = "SELL" if direction == "LONG" else "BUY"
        return amt, position_side, side, be

    def do_take_profit(self, symbol, quantity, direction):
        amt, position_side, side, be = self.get_position_size_and_sides(symbol, direction)
        close_qty = min(quantity, amt)
        tp_params: Dict[str, Any] = {
            "symbol": symbol.upper(),
            "side": side,
            "position_side": position_side,
            "quantity": float(close_qty),
            "type": "MARKET",
            "reduce_only": True,
        }
        self._safe_call(self.client.rest_api.new_order, **tp_params)

    def set_stop_loss_price(
            self,
            symbol: str,
            stop_loss_price: float,
            side: Literal["LONG", "SHORT"],
            position_mode: Literal["ONE_WAY", "HEDGE"],
            *,
            working_type: Literal["MARK_PRICE", "CONTRACT_PRICE"] = "MARK_PRICE",
            price_protect: bool = True,
    ) -> Optional[int]:
        order_side = "SELL" if side == "LONG" else "BUY"
        position_side = "BOTH" if position_mode == "ONE_WAY" else side

        params = {
            "algo_type": "CONDITIONAL",
            "symbol": symbol.upper(),
            "side": order_side,
            "type": "STOP_MARKET",
            "trigger_price": float(stop_loss_price),
            "close_position": "true",
            "position_side": position_side,
            "working_type": working_type,
            "price_protect": "TRUE" if price_protect else "FALSE",
        }
        data = self._safe_call(self.client.rest_api.new_algo_order, **params)
        return data

    def place_take_profits(self, symbol, take_profits, side, position_mode, full_position_quantity):
        order_side = "SELL" if side == "LONG" else "BUY"
        position_side = "BOTH" if position_mode == "ONE_WAY" else side

        for take_profit in take_profits:
            params = {
                "algo_type": "CONDITIONAL",
                "symbol": symbol.upper(),
                "side": order_side,
                "type": "TAKE_PROFIT_MARKET",
                "trigger_price": float(take_profit["price"]),
                "position_side": position_side,
                "working_type": "MARK_PRICE",
                "price_protect": "TRUE",
            }

            full_position_quantity = full_position_quantity - take_profit["quantity"]
            if full_position_quantity <= 0:
                # Close-All TP
                params["close_position"] = "true"
            else:
                params["quantity"] = float(take_profit["quantity"])
                # В Algo API reduceOnly нельзя отправлять в Hedge Mode
                if position_mode == "ONE_WAY":
                    params["reduce_only"] = "true"

            self._safe_call(self.client.rest_api.new_algo_order, **params)
            print(f"[CRYPTO-INSIGHT] Take profit at {take_profit['price']} set for {symbol}")


    from typing import Optional, Dict, Any

    def open_position(
            self,
            symbol: str,
            position_mode: str,
            quantity: float,
            side: str,
    ) -> Optional[int]:
        binance_side = "BUY" if side == "LONG" else "SELL"
        hedge_pos_side = "LONG" if side == "LONG" else "SHORT"

        is_hedge = str(position_mode).upper() == "HEDGE"



        base_params: Dict[str, Any] = {
            "symbol": symbol.upper(),
            "side": binance_side,
            "quantity": float(quantity),

        }


        if is_hedge:
            base_params["position_side"] = hedge_pos_side
        else:
            base_params["position_side"] = "BOTH"




        market_params = dict(base_params)
        market_params.update(
            {
                "type": "MARKET",
                "quantity": quantity,
                "new_order_resp_type": "RESULT",
            }
        )
        mkt = self._safe_call(self.client.rest_api.new_order, **market_params)
        return int(mkt.order_id)

    def set_isolated_margin(self, symbol: str) -> bool:
        data = self._safe_call(
            self.client.rest_api.change_margin_type,
            symbol=symbol.upper(),
            margin_type="ISOLATED",
        )
        return bool(data)

    def set_leverage(self, symbol: str, leverage: int) -> bool:
        data = self._safe_call(
            self.client.rest_api.change_initial_leverage,
            symbol=symbol.upper(),
            leverage=leverage,
        )
        return bool(data)

    def _safe_call(self, fn, **params):
        for attempt in range(3):
            try:
                resp = fn(**params)
                return resp.data() if hasattr(resp, "data") else resp
            except Exception as e:
                code, text = self._extract_binance_err(e)
                if code == -4046:
                    return None
                print("Binance API error in %s(%s): %s", fn.__name__, params, e)
                if attempt < 2:
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                return None


    def get_position_mode(self) -> Optional[PositionMode]:
        data = self._safe_call(self.client.rest_api.get_current_position_mode)
        if not data:
            return None
        val = data.dual_side_position
        is_hedge = bool(val) if isinstance(val, bool) else str(val).lower() == "true"
        return "HEDGE" if is_hedge else "ONE_WAY"

    def _extract_binance_err(self, e: Exception) -> Tuple[Optional[int], str]:
        s = str(e)
        m = re.search(r'{"code":\s*(-?\d+)\s*,\s*"msg"\s*:\s*"([^"]+)"', s)
        if m:
            return int(m.group(1)), m.group(2)
        if "No need to change margin type" in s:
            return -4046, "No need to change margin type."
        return None, s