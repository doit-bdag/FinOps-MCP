"""Ingest FOCUS column definitions and FinOps terms into structured Firestore collections.

This script populates two Firestore collections:
  - finops_focus_columns: Structured FOCUS column records with column_id, display_name,
    category, description, data_type, required status.
  - finops_terms: FinOps terminology with canonical names and informal aliases.

Usage:
    python scripts/ingest_focus.py             # Ingest all
    python scripts/ingest_focus.py --refresh   # Delete + re-ingest
"""

from __future__ import annotations

import argparse
import logging
import sys

# Ensure the src/ package is importable when running as a script
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "src"))

from finops_mcp import config  # noqa: E402
from finops_mcp.vector_store import (  # noqa: E402
    delete_collection,
    upsert_structured_doc,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


# ── FOCUS Column Definitions (sourced from FOCUS 1.2 spec) ────────────────────
# Each column includes: column_id, display_name, category, description,
# data_type, required (bool).

FOCUS_COLUMNS: list[dict] = [
    # Billing
    {"column_id": "BilledCost", "display_name": "Billed Cost", "category": "Billing",
     "description": "A charge serving as the basis for invoicing, inclusive of all reduced rates and discounts while excluding the amortization of upfront charges (one-time or recurring).",
     "data_type": "Decimal", "required": True},
    {"column_id": "BillingAccountId", "display_name": "Billing Account ID", "category": "Billing",
     "description": "The identifier assigned to a billing account by the provider.",
     "data_type": "String", "required": True},
    {"column_id": "BillingAccountName", "display_name": "Billing Account Name", "category": "Billing",
     "description": "The display name assigned to a billing account.",
     "data_type": "String", "required": True},
    {"column_id": "BillingCurrency", "display_name": "Billing Currency", "category": "Billing",
     "description": "The currency that a charge was billed in.",
     "data_type": "String (ISO 4217)", "required": True},
    {"column_id": "InvoiceIssuerName", "display_name": "Invoice Issuer Name", "category": "Billing",
     "description": "The name of the entity responsible for invoicing for the resources and/or services consumed.",
     "data_type": "String", "required": True},
    {"column_id": "ProviderName", "display_name": "Provider Name", "category": "Billing",
     "description": "The name of the entity that made the resources and/or services available for purchase.",
     "data_type": "String", "required": True},
    {"column_id": "SubAccountId", "display_name": "Sub Account ID", "category": "Billing",
     "description": "An ID assigned to a grouping of resources and/or services, often used to manage access and/or cost.",
     "data_type": "String", "required": True},
    {"column_id": "SubAccountName", "display_name": "Sub Account Name", "category": "Billing",
     "description": "A name assigned to a grouping of resources and/or services, often used to manage access and/or cost.",
     "data_type": "String", "required": True},

    # Charge
    {"column_id": "ChargeCategory", "display_name": "Charge Category", "category": "Charge",
     "description": "Indicates whether the row represents an upfront or recurring fee, cost of usage that already occurred, an after-the-fact adjustment (e.g., credits), or taxes.",
     "data_type": "String", "required": True,
     "allowed_values": "Adjustment, Purchase, Tax, Usage"},
    {"column_id": "ChargeClass", "display_name": "Charge Class", "category": "Charge",
     "description": "Indicates whether the row represents a correction to a previously invoiced billing period.",
     "data_type": "String", "required": True,
     "allowed_values": "Correction (or null for regular charges)"},
    {"column_id": "ChargeDescription", "display_name": "Charge Description", "category": "Charge",
     "description": "A self-contained summary of the charge's purpose and price.",
     "data_type": "String", "required": True},
    {"column_id": "ChargeFrequency", "display_name": "Charge Frequency", "category": "Charge",
     "description": "Indicates how often a charge will occur.",
     "data_type": "String", "required": True,
     "allowed_values": "One-Time, Recurring, Usage-Based"},
    {"column_id": "ChargeSubcategory", "display_name": "Charge Subcategory", "category": "Charge",
     "description": "Indicates the kind of charge within the ChargeCategory.",
     "data_type": "String", "required": False},
    {"column_id": "ConsumedQuantity", "display_name": "Consumed Quantity", "category": "Charge",
     "description": "The volume of a given service or resource used or purchased based on the ConsumedUnit.",
     "data_type": "Decimal", "required": False},
    {"column_id": "ConsumedUnit", "display_name": "Consumed Unit", "category": "Charge",
     "description": "The unit of measure indicating how a provider measures usage or purchase of a given service or resource.",
     "data_type": "String", "required": False},
    {"column_id": "ContractedCost", "display_name": "Contracted Cost", "category": "Charge",
     "description": "The cost calculated by multiplying the ContractedUnitPrice by the corresponding PricingQuantity.",
     "data_type": "Decimal", "required": True},
    {"column_id": "ContractedUnitPrice", "display_name": "Contracted Unit Price", "category": "Charge",
     "description": "The agreed-upon unit price for a single PricingUnit of the associated service or resource, inclusive of negotiated discounts, if present.",
     "data_type": "Decimal", "required": True},
    {"column_id": "EffectiveCost", "display_name": "Effective Cost", "category": "Charge",
     "description": "The amortized cost of the charge after applying all reduced rates, discounts, and the applicable portion of relevant, prepaid purchases (one-time or recurring) that covered this charge.",
     "data_type": "Decimal", "required": True},
    {"column_id": "ListCost", "display_name": "List Cost", "category": "Charge",
     "description": "The cost calculated by multiplying the ListUnitPrice by the corresponding PricingQuantity.",
     "data_type": "Decimal", "required": True},
    {"column_id": "ListUnitPrice", "display_name": "List Unit Price", "category": "Charge",
     "description": "The suggested provider-published unit price for a single PricingUnit of the associated service or resource, exclusive of any discounts.",
     "data_type": "Decimal", "required": True},

    # Commitment Discount
    {"column_id": "CommitmentDiscountCategory", "display_name": "Commitment Discount Category", "category": "Commitment Discount",
     "description": "Indicates whether the commitment-based discount identified in the CommitmentDiscountId is based on usage quantity or cost (aka spend).",
     "data_type": "String", "required": False,
     "allowed_values": "Spend, Usage"},
    {"column_id": "CommitmentDiscountId", "display_name": "Commitment Discount ID", "category": "Commitment Discount",
     "description": "The identifier assigned to a commitment-based discount by the provider.",
     "data_type": "String", "required": False},
    {"column_id": "CommitmentDiscountName", "display_name": "Commitment Discount Name", "category": "Commitment Discount",
     "description": "The display name assigned to a commitment-based discount.",
     "data_type": "String", "required": False},
    {"column_id": "CommitmentDiscountQuantity", "display_name": "Commitment Discount Quantity", "category": "Commitment Discount",
     "description": "The amount of a commitment-based discount purchased or allocated for the charge's billing period.",
     "data_type": "Decimal", "required": False},
    {"column_id": "CommitmentDiscountStatus", "display_name": "Commitment Discount Status", "category": "Commitment Discount",
     "description": "Indicates whether the charge corresponds with the consumption of a commitment-based discount or the unused portion.",
     "data_type": "String", "required": False,
     "allowed_values": "Used, Unused"},
    {"column_id": "CommitmentDiscountType", "display_name": "Commitment Discount Type", "category": "Commitment Discount",
     "description": "A provider-assigned label assigned to commitment-based discounts.",
     "data_type": "String", "required": False},
    {"column_id": "CommitmentDiscountUnit", "display_name": "Commitment Discount Unit", "category": "Commitment Discount",
     "description": "The unit of measure used for the commitment-based discount's committed amount.",
     "data_type": "String", "required": False},

    # Location
    {"column_id": "AvailabilityZone", "display_name": "Availability Zone", "category": "Location",
     "description": "A provider-assigned identifier for a physically separated and isolated area within a Region that provides high availability and fault tolerance.",
     "data_type": "String", "required": False},
    {"column_id": "RegionId", "display_name": "Region ID", "category": "Location",
     "description": "A provider-assigned identifier for an isolated geographic area where a resource is provisioned in or a service is provided from.",
     "data_type": "String", "required": False},
    {"column_id": "RegionName", "display_name": "Region Name", "category": "Location",
     "description": "The name of an isolated geographic area where a resource is provisioned in or a service is provided from.",
     "data_type": "String", "required": False},

    # Pricing
    {"column_id": "PricingCategory", "display_name": "Pricing Category", "category": "Pricing",
     "description": "Describes the pricing model used for a charge at the time of use or purchase.",
     "data_type": "String", "required": True,
     "allowed_values": "On-Demand, Commitment-Based, Dynamic, Other"},
    {"column_id": "PricingCurrency", "display_name": "Pricing Currency", "category": "Pricing",
     "description": "The currency that a charge was priced in.",
     "data_type": "String (ISO 4217)", "required": False},
    {"column_id": "PricingQuantity", "display_name": "Pricing Quantity", "category": "Pricing",
     "description": "The volume of a given service or resource used or purchased based on the PricingUnit.",
     "data_type": "Decimal", "required": True},
    {"column_id": "PricingUnit", "display_name": "Pricing Unit", "category": "Pricing",
     "description": "A provider-specified measurement unit for determining unit prices, indicating how the provider rates measured usage and purchase quantities after applying pricing-specific rules.",
     "data_type": "String", "required": True},

    # Resource
    {"column_id": "ResourceId", "display_name": "Resource ID", "category": "Resource",
     "description": "The identifier assigned to a resource by the provider.",
     "data_type": "String", "required": True},
    {"column_id": "ResourceName", "display_name": "Resource Name", "category": "Resource",
     "description": "The display name assigned to a resource.",
     "data_type": "String", "required": True},
    {"column_id": "ResourceType", "display_name": "Resource Type", "category": "Resource",
     "description": "The kind of resource the charge applies to.",
     "data_type": "String", "required": False},
    {"column_id": "Tags", "display_name": "Tags", "category": "Resource",
     "description": "The set of tags assigned to a resource.",
     "data_type": "JSON Object", "required": False},

    # Service
    {"column_id": "ServiceCategory", "display_name": "Service Category", "category": "Service",
     "description": "The highest-level classification of a service based on the core function of the service.",
     "data_type": "String", "required": True,
     "allowed_values": "AI and Machine Learning, Analytics, Business Application, Compute, Databases, Developer Tools, Identity, Integration, IoT, Management and Governance, Media, Migration, Multicloud, Networking, Security, Storage, Web, Other"},
    {"column_id": "ServiceName", "display_name": "Service Name", "category": "Service",
     "description": "An offering that can be purchased from a provider (e.g., cloud virtual machine, SaaS database, professional services from a systems integrator).",
     "data_type": "String", "required": True},
    {"column_id": "ServiceSubcategory", "display_name": "Service Subcategory", "category": "Service",
     "description": "A secondary classification of the service based on the core function.",
     "data_type": "String", "required": False},

    # SKU
    {"column_id": "SkuId", "display_name": "SKU ID", "category": "SKU",
     "description": "A unique identifier that defines a provider-supported construct for organizing properties that are common across one or more SKU Prices.",
     "data_type": "String", "required": False},
    {"column_id": "SkuMeter", "display_name": "SKU Meter", "category": "SKU",
     "description": "A provider-assigned name that further classifies how a SKU ID is measured.",
     "data_type": "String", "required": False},
    {"column_id": "SkuPriceId", "display_name": "SKU Price ID", "category": "SKU",
     "description": "A unique identifier that defines the unit price used to calculate the charge.",
     "data_type": "String", "required": False},

    # Timeframe
    {"column_id": "BillingPeriodEnd", "display_name": "Billing Period End", "category": "Timeframe",
     "description": "The exclusive end date and time of a billing period.",
     "data_type": "DateTime (UTC)", "required": True},
    {"column_id": "BillingPeriodStart", "display_name": "Billing Period Start", "category": "Timeframe",
     "description": "The inclusive start date and time of a billing period.",
     "data_type": "DateTime (UTC)", "required": True},
    {"column_id": "ChargePeriodEnd", "display_name": "Charge Period End", "category": "Timeframe",
     "description": "The exclusive end date and time of a charge period.",
     "data_type": "DateTime (UTC)", "required": True},
    {"column_id": "ChargePeriodStart", "display_name": "Charge Period Start", "category": "Timeframe",
     "description": "The inclusive start date and time of a charge period.",
     "data_type": "DateTime (UTC)", "required": True},
]


# ── FinOps Terms (canonical name → informal aliases) ──────────────────────────

FINOPS_TERMS: list[dict] = [
    {"term": "BilledCost", "display_name": "Billed Cost",
     "definition": "A charge serving as the basis for invoicing, inclusive of all reduced rates and discounts while excluding the amortization of upfront charges.",
     "aliases": ["bill amount", "charge", "raw cost", "invoice cost", "billed amount"],
     "do_not_say": ["actual cost", "real cost"],
     "focus_columns": ["BilledCost"]},
    {"term": "EffectiveCost", "display_name": "Effective Cost",
     "definition": "The amortized cost of the charge after applying all reduced rates, discounts, and the applicable portion of relevant prepaid purchases that covered this charge.",
     "aliases": ["actual cost", "real cost", "net cost", "amortized cost", "true cost"],
     "do_not_say": ["raw cost", "list price"],
     "focus_columns": ["EffectiveCost"]},
    {"term": "ListCost", "display_name": "List Cost",
     "definition": "The cost calculated by multiplying the ListUnitPrice by the PricingQuantity, representing the undiscounted price.",
     "aliases": ["list price", "on-demand price", "retail price", "sticker price", "rack rate"],
     "do_not_say": ["actual cost", "billed cost"],
     "focus_columns": ["ListCost", "ListUnitPrice"]},
    {"term": "CommitmentDiscount", "display_name": "Commitment Discount",
     "definition": "A reduced rate commitment — such as a Reserved Instance, Savings Plan, or Committed Use Discount — that provides lower prices in exchange for a usage or spend commitment over a period of time.",
     "aliases": ["reservation", "RI", "savings plan", "CUD", "committed use discount", "reserved instance"],
     "do_not_say": ["savings", "discount"],
     "focus_columns": ["CommitmentDiscountId", "CommitmentDiscountName", "CommitmentDiscountCategory", "CommitmentDiscountStatus", "CommitmentDiscountType"]},
    {"term": "ChargeCategory", "display_name": "Charge Category",
     "definition": "Indicates whether the row represents an upfront or recurring fee, cost of usage that already occurred, an after-the-fact adjustment, or taxes.",
     "aliases": ["cost type", "charge type", "line item type", "record type"],
     "do_not_say": ["expense category"],
     "focus_columns": ["ChargeCategory"]},
    {"term": "Chargeback", "display_name": "Chargeback",
     "definition": "An allocation model where shared IT costs are directly charged back to the business units that consumed them.",
     "aliases": ["cost allocation", "internal billing", "internal charge"],
     "do_not_say": ["showback"],
     "focus_columns": []},
    {"term": "Showback", "display_name": "Showback",
     "definition": "An allocation model where shared IT costs are shown to business units for awareness, but not directly charged to their budget.",
     "aliases": ["cost visibility", "cost transparency", "cost reporting"],
     "do_not_say": ["chargeback"],
     "focus_columns": []},
    {"term": "UnitEconomics", "display_name": "Unit Economics",
     "definition": "The cost per unit of business value (e.g., cost per transaction, cost per customer, cost per API call). A key FinOps KPI for measuring cloud efficiency.",
     "aliases": ["cost per unit", "unit cost", "COGS per unit", "cost efficiency"],
     "do_not_say": [],
     "focus_columns": ["EffectiveCost"]},
    {"term": "FinOps", "display_name": "FinOps",
     "definition": "An operational framework and cultural practice that maximizes the business value of cloud, enables timely data-driven decision making, and creates financial accountability through collaboration between engineering, finance, and business teams.",
     "aliases": ["cloud financial management", "cloud cost management", "cloud economics"],
     "do_not_say": ["cloud accounting"],
     "focus_columns": []},
    {"term": "FOCUS", "display_name": "FOCUS",
     "definition": "FinOps Open Cost and Usage Specification — an open specification for generating consistent technology billing datasets to reduce complexity for FinOps Practitioners.",
     "aliases": ["FinOps Open Cost and Usage Specification", "FOCUS spec", "FOCUS standard"],
     "do_not_say": ["billing format", "cost format"],
     "focus_columns": []},
    {"term": "ServiceName", "display_name": "Service Name",
     "definition": "An offering that can be purchased from a provider. In FOCUS, ServiceName is the canonical column for identifying the cloud service.",
     "aliases": ["service", "product", "cloud service", "offering"],
     "do_not_say": ["tool", "app"],
     "focus_columns": ["ServiceName"]},
    {"term": "PricingCategory", "display_name": "Pricing Category",
     "definition": "Describes the pricing model used for a charge at the time of use or purchase.",
     "aliases": ["pricing model", "pricing type", "rate type", "price plan"],
     "do_not_say": ["cost model"],
     "focus_columns": ["PricingCategory"]},
]


def ingest_focus_columns(refresh: bool = False) -> int:
    """Upsert all FOCUS column definitions into Firestore."""
    collection_name = config.FIRESTORE_FOCUS_COLLECTION

    if refresh:
        logger.info("Refreshing: deleting all docs in '%s'...", collection_name)
        deleted = delete_collection(collection_name)
        logger.info("Deleted %d documents", deleted)

    count = 0
    for col in FOCUS_COLUMNS:
        doc = {
            "column_id": col["column_id"],
            "display_name": col["display_name"],
            "category": col["category"],
            "description": col["description"],
            "data_type": col["data_type"],
            "required": col["required"],
            "lowercase_column_id": col["column_id"].lower(),
            "lowercase_display_name": col["display_name"].lower(),
        }
        if "allowed_values" in col:
            doc["allowed_values"] = col["allowed_values"]

        upsert_structured_doc(doc, collection_name, col["column_id"])
        count += 1
        logger.debug("Upserted FOCUS column: %s", col["column_id"])

    logger.info("Upserted %d FOCUS columns into '%s'", count, collection_name)
    return count


def ingest_terms(refresh: bool = False) -> int:
    """Upsert all FinOps terms into Firestore."""
    collection_name = config.FIRESTORE_TERMS_COLLECTION

    if refresh:
        logger.info("Refreshing: deleting all docs in '%s'...", collection_name)
        deleted = delete_collection(collection_name)
        logger.info("Deleted %d documents", deleted)

    count = 0
    for term in FINOPS_TERMS:
        doc = {
            "term": term["term"],
            "display_name": term["display_name"],
            "definition": term["definition"],
            "aliases": term["aliases"],
            "do_not_say": term["do_not_say"],
            "focus_columns": term["focus_columns"],
            "lowercase_term": term["term"].lower(),
            "lowercase_display_name": term["display_name"].lower(),
        }

        upsert_structured_doc(doc, collection_name, term["term"])
        count += 1
        logger.debug("Upserted term: %s", term["term"])

    logger.info("Upserted %d FinOps terms into '%s'", count, collection_name)
    return count


def main():
    parser = argparse.ArgumentParser(
        description="Ingest FOCUS column definitions and FinOps terms into Firestore"
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Delete all existing documents and re-ingest from scratch",
    )
    args = parser.parse_args()

    cols = ingest_focus_columns(refresh=args.refresh)
    terms = ingest_terms(refresh=args.refresh)

    logger.info("Ingestion complete: %d columns, %d terms", cols, terms)


if __name__ == "__main__":
    main()
