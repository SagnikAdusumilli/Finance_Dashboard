import keyring

from plaid.api import plaid_api
from plaid.api_client import ApiClient
from plaid.configuration import Configuration
from plaid import Environment
from plaid.model.transactions_sync_request import TransactionsSyncRequest

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


def fetch_transactions(client, access_token):
    request = TransactionsSyncRequest(access_token, count=100)
    return client.transactions_sync(request)

def main():
    client = initialize_client()
    access_token = keyring.get_password(
        "finance_dashboard_plaid_td_token", "td_plaid"
    )
    if not access_token:
        raise ValueError("Missing Plaid access token")

    response = fetch_transactions(client, access_token)

    print("Added transactions:", len(response.added))
    print("Has more:", response.has_more)


if __name__ == "__main__":
    main()