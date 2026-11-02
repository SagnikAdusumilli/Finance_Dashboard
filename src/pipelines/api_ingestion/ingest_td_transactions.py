import keyring
import json
import duckdb

from plaid.api import plaid_api
from plaid.api_client import ApiClient
from plaid.configuration import Configuration
from plaid import Environment
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from plaid.model.transactions_sync_request_options import TransactionsSyncRequestOptions
from plaid.model.item_get_request import ItemGetRequest
from datetime import date, datetime, timezone 
from pathlib import Path
import pandas as pd

INITIAL_DATE = date(2026, 3, 2)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = PROJECT_ROOT / "data" / "finance.db"

# get the creds from keychain 
def initialize_client():
    client_id = keyring.get_password("finance_dashboard_plaid_client_id", "td_plaid")
    access_token = keyring.get_password("finance_dashboard_plaid_td_token", "td_plaid")
    secret = keyring.get_password("finance_dashboard_plaid_secret", "td_plaid")

    # validate creds
    if not all([client_id, access_token, secret]):
        raise ValueError("Missing Plaid credentials in keychain")


    # API config
    conf = Configuration(
        host=Environment.Production,
        api_key={"clientId": client_id, "secret": secret}
    )

    return plaid_api.PlaidApi(ApiClient(conf))

def get_item_id(client, access_token):
    request = ItemGetRequest(access_token=access_token)
    response = client.item_get(request).to_dict()

    return response["item"]["item_id"]

def get_saved_cursor(environment, item_id, db_path):
    conn = duckdb.connect(str(db_path), read_only=True)

    try:
        result = conn.execute("""
            SELECT cursor
            FROM plaid_sync_state
            WHERE environment = ? 
            AND item_id = ? 
            ORDER BY last_successful_sync DESC
        """, [environment, item_id]).fetchone()

        return result[0] if result else None 
    finally: 
        conn.close()


def fetch_transactions(client, access_token, cursor=None):
    added = []
    modified = []
    removed = []
    pages_fetched = 0

    current_cursor = cursor

    while True:
        request_params = {
            "access_token": access_token, 
            "count": 500,  
            "options": TransactionsSyncRequestOptions(
        include_original_description=True)
        }

        if current_cursor is not None:
            request_params["cursor"] = current_cursor

        request = TransactionsSyncRequest(**request_params)
        response = client.transactions_sync(request).to_dict()

        added.extend(response["added"])
        modified.extend(response["modified"])
        removed.extend(response["removed"])

        pages_fetched +=1 
        current_cursor = response["next_cursor"]

        if not response["has_more"]:
            break

    return {
        "added": added,
        "modified": modified,
        "removed": removed,
        "cursor": current_cursor,
        "pages_fetched": pages_fetched
    }

def transform_transactions(transactions, environment, item_id):
    """
    item_id refers to plaid connection, each institution can have a seperate item id
    """

    rows = []

    for t in transactions:
        # skip any transactions that less inital date
        if t["date"] < INITIAL_DATE:
            continue 

        pfc = t.get("personal_finance_category") or {}

        rows.append({
            "environment": environment,
            "item_id": item_id,
            "transaction_id": t["transaction_id"],
            "account_id": t["account_id"],
            "date": t["date"],
            "amount": t["amount"],
            "iso_currency_code": t.get("iso_currency_code"),
            "description": t.get("original_description"),
            "merchant_name": t.get("merchant_name"),
            "pending": t["pending"],
            "pending_transaction_id": t.get("pending_transaction_id"),
            "plaid_category_primary": pfc.get("primary"),
            "plaid_category_detailed": pfc.get("detailed"),
            "plaid_category_confidence": pfc.get("confidence_level"),
            "raw_json": json.dumps(t, default=str)
        })
    return pd.DataFrame(rows)

def save_ingestion(
        db_path, 
        result, 
        added_df, 
        modified_df, 
        environment, 
        item_id, 
        run_mode="INITIAL"
):
    conn = duckdb.connect(str(db_path))

    try: 
        # combine added and modified transaction 
        df = pd.concat([added_df, modified_df], ignore_index=True)

        if not df.empty: 
            df = df.drop_duplicates(
                subset=["environment", "item_id", "transaction_id"],
                keep="last")

            conn.register("staged_transactions", df)
        conn.execute("BEGIN TRANSACTION")

        #1. Uspert transction 
        if not df.empty:
            conn.execute("""
                INSERT INTO plaid_transactions (
                    environment,
                    item_id,
                    transaction_id,
                    account_id,
                    date,
                    amount,
                    iso_currency_code,
                    description,
                    merchant_name,
                    pending,
                    pending_transaction_id,
                    plaid_category_primary,
                    plaid_category_detailed,
                    plaid_category_confidence,
                    raw_json
                )
                SELECT
                    environment,
                    item_id,
                    transaction_id,
                    account_id,
                    date,
                    amount,
                    iso_currency_code,
                    description,
                    merchant_name,
                    pending,
                    pending_transaction_id,
                    plaid_category_primary,
                    plaid_category_detailed,
                    plaid_category_confidence,
                    raw_json::JSON
                FROM staged_transactions
                WHERE TRUE
                ON CONFLICT (
                    environment, item_id, transaction_id
                )
                DO UPDATE SET
                    account_id = EXCLUDED.account_id,
                    date = EXCLUDED.date,
                    amount = EXCLUDED.amount,
                    iso_currency_code = EXCLUDED.iso_currency_code,
                    description = EXCLUDED.description,
                    merchant_name = EXCLUDED.merchant_name,
                    pending = EXCLUDED.pending,
                    pending_transaction_id =
                        EXCLUDED.pending_transaction_id,
                    plaid_category_primary =
                        EXCLUDED.plaid_category_primary,
                    plaid_category_detailed =
                        EXCLUDED.plaid_category_detailed,
                    plaid_category_confidence =
                        EXCLUDED.plaid_category_confidence,
                    raw_json = EXCLUDED.raw_json,
                    is_removed = FALSE,
                    updated_at = now()
            """)
        # 2. Soft-delete removed transactions
        for removed in result["removed"]:
            conn.execute("""
                UPDATE plaid_transactions
                SET
                    is_removed = TRUE,
                    updated_at = now()
                WHERE environment = ?
                AND item_id = ?
                AND transaction_id = ?
            """, [
                environment,
                item_id,
                removed["transaction_id"]
            ])
                # 3. Save new cursor
        conn.execute("""
            INSERT INTO plaid_sync_state (
                environment,
                item_id,
                cursor,
                last_successful_sync
            )
            VALUES (?, ?, ?, now())
            ON CONFLICT (environment, item_id)
            DO UPDATE SET
                cursor = EXCLUDED.cursor,
                last_successful_sync =
                    EXCLUDED.last_successful_sync
        """, [
            environment,
            item_id,
            result["cursor"]
        ])

        # 4. Log successful ingestion
        conn.execute("""
            INSERT INTO ingestion_run (
                pipeline_name,
                source_type,
                run_mode,
                started_at,
                completed_at,
                status,
                records_added,
                records_modified,
                records_removed,
                pages_fetched
            )
            VALUES (
                'td_plaid_transactions',
                'API',
                ?,
                ?,
                now(),
                'SUCCESS',
                ?, ?, ?, ?
            )
        """, [
            run_mode,
            datetime.now(timezone.utc),
            len(result["added"]),
            len(result["modified"]),
            len(result["removed"]),
            result["pages_fetched"]
            ])

        conn.execute("COMMIT")
        print("Ingestion committed successfully!")
    except Exception: 
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()

def main():
    environment = "production"

    # Step 1: Initialize Plaid client
    client = initialize_client()
    access_token = keyring.get_password("finance_dashboard_plaid_td_token", "td_plaid")
   

    # Step 2: Retrieve Item ID
    item_id = get_item_id(client, access_token)

    cursor = get_saved_cursor(environment, item_id, DB_PATH)

    # Step 3: Fetch transactions (initial load)
    result = fetch_transactions(
        client=client,
        access_token=access_token,
        cursor=cursor
    )

    print(f"Added: {len(result['added'])}")
    print(f"Modified: {len(result['modified'])}")
    print(f"Removed: {len(result['removed'])}")

    # Step 4: Transform transactions
    added_df = transform_transactions(
        result["added"], environment, item_id
    )

    modified_df = transform_transactions(
        result["modified"], environment, item_id
    )

    print(f"Added DataFrame: {added_df.shape}")
    print(f"Modified DataFrame: {modified_df.shape}")

    run_mode = "INITIAL" if cursor is None else "INCREMENTAL"

    run_mode = "INITIAL" if cursor is None else "INCREMENTAL"

    print(f"Run mode: {run_mode}")
    print(f"Cursor found: {cursor is not None}")

    # Step 5: Save transactions and cursor
    save_ingestion(
        db_path=DB_PATH,
        result=result,
        added_df=added_df,
        modified_df=modified_df,
        environment=environment,
        item_id=item_id,
        run_mode=run_mode
    )

    print(f"{run_mode} ingestion completed successfully!")

if __name__ == "__main__":
    main()