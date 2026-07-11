from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session


BANK_TABLE = "bank_transaction_import"


@dataclass(slots=True)
class BankTransaction:
    bank_code: str
    bank_name: str
    account_number: str
    transaction_id: str
    transaction_date: str
    deposit_amount: str
    withdrawal_amount: str
    amount: str
    direction: str
    counterparty: str
    description: str
    balance: str
    source_file: str
    import_batch_id: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _decode_csv(content: bytes) -> str:
    for encoding in ("cp932", "utf-8-sig", "utf-8"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Unsupported CSV encoding")


def _clean(value: Any) -> str:
    return str(value or "").replace("\u3000", " ").strip()


def _amount(value: Any) -> str:
    raw = _clean(value).replace(",", "").replace("円", "")
    if not raw:
        return ""
    try:
        number = Decimal(raw)
    except InvalidOperation:
        return ""
    if number == number.to_integral():
        return format(number.quantize(Decimal("1")), "f")
    return format(number.normalize(), "f")


def _date(value: str) -> str:
    raw = _clean(value)
    for fmt in ("%Y/%m/%d", "%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return raw


def detect_bank_csv(content: bytes) -> str:
    text_value = _decode_csv(content)
    if "お支払い金額" in text_value and "お預かり金額" in text_value:
        return "SUGAMO_SHINKIN"
    if "入出金明細ＩＤ" in text_value and "受入金額（円）" in text_value:
        return "JAPAN_POST_BANK"
    raise ValueError("Unsupported bank CSV format")


def _fingerprint(*values: str) -> str:
    raw = "|".join(values).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def parse_sugamo_shinkin_csv(
    content: bytes,
    *,
    source_file: str,
    import_batch_id: str,
) -> list[BankTransaction]:
    rows = list(csv.reader(io.StringIO(_decode_csv(content))))
    if len(rows) < 6:
        raise ValueError("Sugamo CSV is too short")

    account_number = ""
    branch = ""
    if rows and rows[0][:4] == ["契約店舗コード", "店舗名", "科目", "口座番号"][:4]:
        if len(rows) > 1:
            branch = _clean(rows[1][1] if len(rows[1]) > 1 else "")
            account_number = _clean(rows[1][3] if len(rows[1]) > 3 else "")

    header_index = next(
        (i for i, row in enumerate(rows) if row[:5] == ["日付", "摘要", "お支払い金額", "お預かり金額", "残高"]),
        -1,
    )
    if header_index < 0:
        raise ValueError("Sugamo detail header not found")

    result: list[BankTransaction] = []
    for row in rows[header_index + 1:]:
        if len(row) < 5 or not _clean(row[0]):
            continue

        payment_cell = _clean(row[2])
        deposit_cell = _clean(row[3])
        payment_amount = _amount(payment_cell)
        deposit_amount = _amount(deposit_cell)

        # Sugamo rows use the non-amount cell for counterparty/detail.
        if deposit_amount and not payment_amount:
            direction = "CREDIT"
            amount = deposit_amount
            withdrawal = ""
            counterparty = payment_cell
        elif payment_amount and not deposit_amount:
            direction = "DEBIT"
            amount = payment_amount
            withdrawal = payment_amount
            deposit_amount = ""
            counterparty = deposit_cell
        elif not payment_amount and not deposit_amount:
            continue
        else:
            raise ValueError(f"Sugamo row has both deposit and withdrawal amounts: {row}")

        tx_date = _date(row[0])
        description = _clean(row[1])
        balance = _amount(row[4])
        tx_id = _fingerprint(
            "SUGAMO_SHINKIN", account_number, tx_date, direction,
            amount, counterparty, description, balance,
        )
        result.append(BankTransaction(
            bank_code="SUGAMO_SHINKIN",
            bank_name="巣鴨信用金庫",
            account_number=account_number,
            transaction_id=tx_id,
            transaction_date=tx_date,
            deposit_amount=deposit_amount,
            withdrawal_amount=withdrawal,
            amount=amount,
            direction=direction,
            counterparty=counterparty,
            description=f"{branch} {description}".strip(),
            balance=balance,
            source_file=source_file,
            import_batch_id=import_batch_id,
        ))
    return result


def parse_japan_post_bank_csv(
    content: bytes,
    *,
    source_file: str,
    import_batch_id: str,
) -> list[BankTransaction]:
    rows = list(csv.reader(io.StringIO(_decode_csv(content))))
    account_number = ""
    for row in rows:
        if row and _clean(row[0]).startswith("お客さま口座番号："):
            account_number = _clean(row[0]).split("：", 1)[1]
            break

    header_index = next(
        (i for i, row in enumerate(rows) if row and _clean(row[0]) == "取引日" and "入出金明細ＩＤ" in row),
        -1,
    )
    if header_index < 0:
        raise ValueError("Japan Post detail header not found")

    result: list[BankTransaction] = []
    for row in rows[header_index + 1:]:
        if len(row) < 7 or not _clean(row[0]):
            continue
        deposit = _amount(row[2])
        withdrawal = _amount(row[3])
        if deposit and not withdrawal:
            direction, amount = "CREDIT", deposit
        elif withdrawal and not deposit:
            direction, amount = "DEBIT", withdrawal
        elif not deposit and not withdrawal:
            continue
        else:
            raise ValueError(f"Japan Post row has both deposit and withdrawal amounts: {row}")

        detail1 = _clean(row[4])
        detail2 = _clean(row[5])
        result.append(BankTransaction(
            bank_code="JAPAN_POST_BANK",
            bank_name="ゆうちょう銀行",
            account_number=account_number,
            transaction_id=_clean(row[1]),
            transaction_date=_date(row[0]),
            deposit_amount=deposit,
            withdrawal_amount=withdrawal,
            amount=amount,
            direction=direction,
            counterparty=detail2,
            description=detail1,
            balance=_amount(row[6]),
            source_file=source_file,
            import_batch_id=import_batch_id,
        ))
    return result


def parse_bank_csv(content: bytes, *, source_file: str, import_batch_id: str | None = None):
    batch = import_batch_id or uuid4().hex
    bank = detect_bank_csv(content)
    if bank == "SUGAMO_SHINKIN":
        return parse_sugamo_shinkin_csv(content, source_file=source_file, import_batch_id=batch)
    return parse_japan_post_bank_csv(content, source_file=source_file, import_batch_id=batch)


def ensure_bank_transaction_table(db: Session) -> None:
    db.execute(text(f"""CREATE TABLE IF NOT EXISTS {BANK_TABLE}(
      id VARCHAR(64) PRIMARY KEY,
      bank_code VARCHAR(64) NOT NULL,
      bank_name VARCHAR(255) NOT NULL,
      account_number VARCHAR(255) NOT NULL DEFAULT '',
      transaction_id VARCHAR(255) NOT NULL,
      transaction_date VARCHAR(32) NOT NULL,
      deposit_amount VARCHAR(64) NOT NULL DEFAULT '',
      withdrawal_amount VARCHAR(64) NOT NULL DEFAULT '',
      amount VARCHAR(64) NOT NULL,
      direction VARCHAR(16) NOT NULL,
      counterparty VARCHAR(500) NOT NULL DEFAULT '',
      description VARCHAR(1000) NOT NULL DEFAULT '',
      balance VARCHAR(64) NOT NULL DEFAULT '',
      source_file VARCHAR(1000) NOT NULL,
      import_batch_id VARCHAR(64) NOT NULL,
      imported_at VARCHAR(64) NOT NULL,
      UNIQUE(bank_code,account_number,transaction_id)
    )"""))
    db.commit()


def import_bank_transactions(db: Session, transactions: list[BankTransaction]) -> dict[str, Any]:
    ensure_bank_transaction_table(db)
    created = 0
    existing = 0
    now = datetime.utcnow().isoformat() + "Z"
    for tx in transactions:
        found = db.execute(text(
            f"SELECT id FROM {BANK_TABLE} WHERE bank_code=:bank AND account_number=:account AND transaction_id=:txid"
        ), {"bank":tx.bank_code,"account":tx.account_number,"txid":tx.transaction_id}).first()
        if found:
            existing += 1
            continue
        p = tx.as_dict()
        p.update({"id":uuid4().hex,"imported_at":now})
        db.execute(text(f"""INSERT INTO {BANK_TABLE}(
          id,bank_code,bank_name,account_number,transaction_id,transaction_date,
          deposit_amount,withdrawal_amount,amount,direction,counterparty,description,
          balance,source_file,import_batch_id,imported_at
        ) VALUES(
          :id,:bank_code,:bank_name,:account_number,:transaction_id,:transaction_date,
          :deposit_amount,:withdrawal_amount,:amount,:direction,:counterparty,:description,
          :balance,:source_file,:import_batch_id,:imported_at
        )"""), p)
        created += 1
    db.commit()
    return {"created":created,"existing":existing,"total":len(transactions)}
