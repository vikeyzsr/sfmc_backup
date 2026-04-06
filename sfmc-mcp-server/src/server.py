import json
import os

from mcp.server.fastmcp import FastMCP

from .auth import SFMCAuth
from .client import SFMCClient
from .tools import data_extensions, journeys, email, subscribers, automations

mcp = FastMCP(
    "Salesforce Marketing Cloud Engagement",
    instructions="Read data from Salesforce Marketing Cloud Engagement: Data Extensions, Journeys, Emails, Contacts, and Automations.",
)

_auth: SFMCAuth | None = None
_client: SFMCClient | None = None


def _get_client() -> SFMCClient:
    global _auth, _client
    if _client is None:
        client_id = os.environ.get("SFMC_CLIENT_ID", "")
        client_secret = os.environ.get("SFMC_CLIENT_SECRET", "")
        subdomain = os.environ.get("SFMC_SUBDOMAIN", "")
        account_id = os.environ.get("SFMC_ACCOUNT_ID") or None

        if not client_id or not client_secret or not subdomain:
            raise RuntimeError(
                "Missing required environment variables: SFMC_CLIENT_ID, SFMC_CLIENT_SECRET, SFMC_SUBDOMAIN"
            )

        _auth = SFMCAuth(client_id, client_secret, subdomain, account_id)
        _client = SFMCClient(_auth)
    return _client


def _fmt(data: object) -> str:
    return json.dumps(data, indent=2, default=str)


# ---------------------------------------------------------------------------
# Data Extension tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def list_data_extensions() -> str:
    """List all data extensions in the Marketing Cloud account.

    Returns the name, customer key, and ID for each data extension.
    """
    client = _get_client()
    result = await data_extensions.list_data_extensions(client)
    return _fmt(result)


@mcp.tool()
async def describe_data_extension(customer_key: str) -> str:
    """Get the field schema (columns and types) of a data extension.

    Args:
        customer_key: The external/customer key of the data extension.
    """
    client = _get_client()
    result = await data_extensions.describe_data_extension(client, customer_key)
    return _fmt(result)


@mcp.tool()
async def query_data_extension_rows(
    customer_key: str,
    filter_expression: str = "",
    page: int = 1,
    page_size: int = 50,
) -> str:
    """Read rows from a data extension with optional filtering.

    Args:
        customer_key: The external/customer key of the data extension.
        filter_expression: OData-style filter, e.g. "EmailAddress eq 'test@example.com'". Leave empty for no filter.
        page: Page number (1-based).
        page_size: Number of rows per page (max 2500).
    """
    client = _get_client()
    result = await data_extensions.query_data_extension_rows(
        client,
        customer_key,
        filter_expression=filter_expression or None,
        page=page,
        page_size=min(page_size, 2500),
    )
    return _fmt(result)


# ---------------------------------------------------------------------------
# Journey tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def list_journeys(page: int = 1, page_size: int = 50, status: str = "") -> str:
    """List journeys (interactions) in Marketing Cloud.

    Args:
        page: Page number (1-based).
        page_size: Number of journeys per page.
        status: Optional status filter: Draft, Running, Stopped, etc.
    """
    client = _get_client()
    result = await journeys.list_journeys(client, page=page, page_size=page_size, status=status or None)
    return _fmt(result)


@mcp.tool()
async def get_journey(journey_id: str) -> str:
    """Get full details of a specific journey by its ID.

    Args:
        journey_id: The unique ID of the journey.
    """
    client = _get_client()
    result = await journeys.get_journey(client, journey_id)
    return _fmt(result)


# ---------------------------------------------------------------------------
# Email tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def list_email_definitions(page: int = 1, page_size: int = 50, status: str = "") -> str:
    """List triggered send (email) definitions.

    Args:
        page: Page number (1-based).
        page_size: Number of definitions per page.
        status: Optional status filter: Active, Inactive, Deleted, etc.
    """
    client = _get_client()
    result = await email.list_email_definitions(client, page=page, page_size=page_size, status=status or None)
    return _fmt(result)


@mcp.tool()
async def get_email_send_status(message_key: str) -> str:
    """Check the send status of a specific email message.

    Args:
        message_key: The unique message key returned when the email was triggered.
    """
    client = _get_client()
    result = await email.get_email_send_status(client, message_key)
    return _fmt(result)


@mcp.tool()
async def list_content_builder_emails(page: int = 1, page_size: int = 50) -> str:
    """List all email content from Content Builder / Email Studio.

    Returns name, subject line, preheader, HTML content, status, and category
    for every email asset (template-based, HTML, and text-only emails).

    Args:
        page: Page number (1-based).
        page_size: Number of emails per page (max 50).
    """
    client = _get_client()
    result = await email.list_content_builder_emails(client, page=page, page_size=min(page_size, 50))
    return _fmt(result)


# ---------------------------------------------------------------------------
# Subscriber / Contact tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def search_contacts(contact_key: str = "", email_address: str = "") -> str:
    """Search for contacts by contact key or email address.

    At least one of contact_key or email_address must be provided.

    Args:
        contact_key: The contact key to search for.
        email_address: The email address to search for.
    """
    client = _get_client()
    result = await subscribers.search_contacts(
        client,
        contact_key=contact_key or None,
        email=email_address or None,
    )
    return _fmt(result)


@mcp.tool()
async def get_contact(contact_id: str) -> str:
    """Get full details of a specific contact by ID.

    Args:
        contact_id: The unique contact ID.
    """
    client = _get_client()
    result = await subscribers.get_contact(client, contact_id)
    return _fmt(result)


# ---------------------------------------------------------------------------
# Automation tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def list_automations(page: int = 1, page_size: int = 50) -> str:
    """List all automations in the Marketing Cloud account.

    Args:
        page: Page number (1-based).
        page_size: Number of automations per page.
    """
    client = _get_client()
    result = await automations.list_automations(client, page=page, page_size=page_size)
    return _fmt(result)


@mcp.tool()
async def get_automation(automation_id: str) -> str:
    """Get full details of a specific automation by its ID.

    Args:
        automation_id: The unique ID of the automation.
    """
    client = _get_client()
    result = await automations.get_automation(client, automation_id)
    return _fmt(result)
