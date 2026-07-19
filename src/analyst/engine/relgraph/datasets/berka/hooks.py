"""Berka dataset hooks: decode the PKDD'99 encodings and derive counterparties.

- Dates are YYMMDD integers in the 1900s (e.g. 930107 -> 1993-01-07).
- client.birth_number encodes birth date and gender: for women, 50 is added
  to the month (e.g. 706213 -> 1970-12-13, female).
- card.issued is "YYMMDD 00:00:00".
- district.asc has anonymous A1..A16 headers; '?' marks missing values.
- Transfer transactions (trans.bank/account) and standing orders
  (order.bank_to/account_to) name the other side of the payment. The derived
  counterparty table gives each distinct (bank, account) pair a node, so
  accounts paying the same counterparty become connected through it — the
  entity-to-entity structure the paper's contagion argument needs. Hooks run
  in schema.yaml table order (trans and order before counterparty).
"""

from __future__ import annotations

import pandas as pd

_state: dict = {}

DISTRICT_RENAMES = {
    "A1": "district_id",
    "A2": "district_name",
    "A3": "region",
    "A4": "inhabitants",
    "A11": "avg_salary",
    "A12": "unemployment_rate_95",
    "A13": "unemployment_rate_96",
    "A14": "entrepreneurs_per_1000",
    "A15": "crimes_95",
    "A16": "crimes_96",
}


def _yymmdd_to_date(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip().str.zfill(6)
    return pd.to_datetime("19" + s, format="%Y%m%d").dt.date


def _counterparty_id(bank: pd.Series, account: pd.Series) -> pd.Series:
    """Stable id for the (bank, account) pair. Missing where neither is set,
    and for the bank's internal sentinel (no bank, account "0") used on fee
    and SIPO bookings — that is not a real counterparty."""
    bank = bank.fillna("").astype(str).str.strip()
    account = (
        account.fillna("").astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    )
    real = (bank != "") | (~account.isin(["", "0"]))
    return (bank + "|" + account).where(real)


def transform(table_name: str, df: pd.DataFrame) -> pd.DataFrame:
    if table_name == "counterparty":
        seen = pd.concat(
            [
                _state.get("trans_cp", pd.DataFrame()),
                _state.get("order_cp", pd.DataFrame()),
            ],
            ignore_index=True,
        )
        out = (
            seen.dropna(subset=["counterparty_id"])
            .drop_duplicates("counterparty_id")
            .reset_index(drop=True)
        )
        return out[["counterparty_id", "counterparty_bank"]]

    if table_name == "district":
        df = df.rename(columns=DISTRICT_RENAMES)
        for col in DISTRICT_RENAMES.values():
            if col in ("district_name", "region"):
                continue
            df[col] = pd.to_numeric(df[col].replace("?", None), errors="coerce")
        return df

    if table_name == "client":
        raw = df["birth_number"].astype(str).str.strip().str.zfill(6)
        month = raw.str[2:4].astype(int)
        female = month > 50
        real_month = month.where(~female, month - 50).astype(int)
        df["gender"] = female.map({True: "female", False: "male"})
        df["birth_date"] = pd.to_datetime(
            "19" + raw.str[:2] + real_month.astype(str).str.zfill(2) + raw.str[4:6],
            format="%Y%m%d",
        ).dt.date
        return df

    if table_name == "account":
        df["open_date"] = _yymmdd_to_date(df["date"])
        return df

    if table_name == "card":
        df["issued"] = _yymmdd_to_date(df["issued"].astype(str).str[:6])
        return df

    if table_name == "loan":
        df["grant_date"] = _yymmdd_to_date(df["date"])
        return df

    if table_name == "order":
        df["counterparty_id"] = _counterparty_id(df["bank_to"], df["account_to"])
        _state["order_cp"] = pd.DataFrame(
            {
                "counterparty_id": df["counterparty_id"],
                "counterparty_bank": df["bank_to"].fillna("").astype(str).str.strip(),
            }
        )
        return df

    if table_name == "trans":
        df["trans_date"] = _yymmdd_to_date(df["date"])
        df["counterparty_id"] = _counterparty_id(df["bank"], df["account"])
        _state["trans_cp"] = (
            pd.DataFrame(
                {
                    "counterparty_id": df["counterparty_id"],
                    "counterparty_bank": df["bank"].fillna("").astype(str).str.strip(),
                }
            )
            .dropna(subset=["counterparty_id"])
            .drop_duplicates("counterparty_id")
        )
        return df

    return df
