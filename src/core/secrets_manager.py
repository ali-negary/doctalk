from typing import Optional, Dict

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.core.exceptions import (
    ClientAuthenticationError,
    ResourceNotFoundError,
    HttpResponseError,
    ServiceRequestError,
)
import structlog

# Initialize global logger for the module
logger = structlog.get_logger(__name__)


class AzureSecretManager:  # Not Fully Tested
    """
    Encapsulates logic for fetching secrets from Azure Key Vault.
    Assumes 'azure-identity' and 'azure-keyvault-secrets' are installed.
    """

    def __init__(self, vault_url: str, app_env: str):
        self.vault_url = vault_url
        self.app_env = app_env.lower()
        self.client = None

        if self.vault_url:
            self._connect()

    def _connect(self):
        try:
            logger.info("keyvault_connecting", url=self.vault_url)

            # DefaultAzureCredential automatically handles:
            # 1. Environment Vars (AZURE_CLIENT_ID, etc.)
            # 2. Managed Identity (App Service / Container Apps)
            # 3. Azure CLI (local 'az login')
            credential = DefaultAzureCredential()
            self.client = SecretClient(vault_url=self.vault_url, credential=credential)

        except (ClientAuthenticationError, ServiceRequestError, HttpResponseError) as e:
            # ClientAuthenticationError: Credential issues (Mising env vars, bad secret)
            # ServiceRequestError: Network/DNS issues (Vault URL unreachable)
            # HttpResponseError: Base class for other API errors (403 Forbidden, etc)

            logger.critical("keyvault_connection_failed", error=str(e), exc_info=True)

            if self.app_env != "production":
                # In Dev/Test, we allow the app to start even if KV fails (fallback to .env)
                self.client = None
            else:
                # In Production, failing to connect to secrets is fatal
                raise e

    def get_secret(self, secret_name: str) -> Optional[str]:
        """Fetch a single secret by name."""
        if not self.client:
            logger.error("keyvault_client_not_initialized")
            return None

        try:
            # Key Vault secrets are versioned; get_secret retrieves the latest enabled version
            secret = self.client.get_secret(secret_name)
            if secret.value:
                return secret.value

        except ResourceNotFoundError:
            # Specific exception for when the secret name doesn't exist
            logger.warn("secret_not_found_in_kv", name=secret_name)

        except HttpResponseError as e:
            # Handles 403 Forbidden or 500 Server Errors from Azure
            logger.error("keyvault_fetch_error", name=secret_name, error=str(e))

        return None

    def load_secrets_into_settings(self, target_obj, mapping: Dict[str, str]):
        """
        Batch loads secrets and sets attributes on the target settings object.
        mapping format: {"KV_SECRET_NAME": "CONFIG_ATTRIBUTE_NAME"}
        """
        if not self.client:
            return

        count = 0
        for kv_name, attr_name in mapping.items():
            val = self.get_secret(kv_name)
            if val:
                setattr(target_obj, attr_name, val)
                count += 1

        if count > 0:
            logger.info("keyvault_secrets_loaded", count=count)
