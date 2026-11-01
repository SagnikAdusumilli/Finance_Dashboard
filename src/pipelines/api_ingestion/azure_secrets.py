from azure.identity import AzureCliCredential
from azure.keyvault.secrets import SecretClient

vault_url = "https://kv-finance-dashboard.vault.azure.net/"

credential = AzureCliCredential()

client = SecretClient(
    vault_url=vault_url,
    credential=credential
)

client_id = client.get_secret("plaid-td-clientid").value

print("Client ID retrieved:", bool(client_id))
