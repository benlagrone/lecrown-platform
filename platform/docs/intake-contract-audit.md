# Intake Contract Audit
## Source Files Analyzed
- `platform/backend/app/schemas/intake.py` (sha256: ae5d2300182666054cebd62ccd691dc6054c7309d1016270347a7dc162016b83)
- `platform/backend/app/routes/intake.py` (sha256: 0ebc6e3c2b9ba7a54bec889e5ac6953a7d3225011c7636b2b50980adef2a7737)
- `platform/backend/app/models/intake.py` (sha256: b1970c392987c260209aed989ae5fe00e5d81abccd30573614b70fc4ff6bb70f)
- `platform/docs/intake-architecture.md` (sha256: d82a4e2edb72f3374f528fbcf8e7b4400aca281cbabcdc9631687f9f3943d939)
- `platform/docs/espocrm-strategy.md` (sha256: b79362c38e6616cf8e4a9ad30835abc2a590c4c0f87d04586a1e309bc27b75d1)
- `platform/backend/app/services/intake_service.py` (sha256: 42c3e8cd6a2e60955aaf1b3435aec3fdf7eb0fe1b15a4defbcf72bd4a8e2ba4)
- `platform/backend/app/core/security.py` (sha256: 0b05b2b4cbb799278fdc6f356b2d006b87d0fd1fa487241288636dc018291488)
## Field Categories
### Source Site and Attribution
- `source_site`: Required string, minimum length 1 - identifies the originating site
- `source_type`: Optional string, default "website" - type of source (e.g., "wordpress", "custom")
- `form_provider`: Optional string - identifies form provider (e.g., "WPForms")
- `form_id`: Optional string - unique identifier for the form
- `form_name`: Optional string - name of the form
- `external_entry_id`: Optional string - external system identifier
- `page_url`: Optional string - URL where form was submitted
### Business Context and Tenant Boundary
- `business_context`: Optional string - identifies business unit or tenant context
- `product_context`: Optional string - identifies product type or service category
### Contact Data
- `lead`: Object containing contact information:
  - `firstName`: Optional string
  - `lastName`: Optional string
  - `emailAddress`: Optional string
  - `phoneNumber`: Optional string
  - `description`: Optional string
  - `source`: Optional string
  - `businessUnit`: Optional string
  - `productType`: Optional string
### Metadata and Arbitrary Context
- `metadata`: Dictionary of arbitrary key-value pairs for additional context
- `campaign`: Optional string - campaign identifier
## Endpoint and Submission Handling
### create_lead_submission Function
The intake endpoint handles lead submissions through the `create_lead_submission` function in the intake service, which:
- Validates incoming payloads against the IntakeLeadCreate schema
- Stores submissions in the database with proper normalization
- Routes submissions to downstream systems (currently EspoCRM)
- Maintains audit trails and delivery status tracking
## Persistence/Normalization/Attribution
### Database Persistence
The intake data is persisted in the `intake_lead_submissions` table with:
- Source site identification (`source_site`)
- Business context (`business_context`)
- Contact information fields (`contact_name`, `email`, `phone`)
- Status tracking (`status`, `delivery_target`, `delivery_status`)
- Raw and normalized payloads (`raw_payload`, `normalized_payload`)
- Timestamps for creation and updates
### Normalization
The system normalizes contact data by:
- Extracting and storing contact information in dedicated fields
- Mapping source site data to standardized fields
- Maintaining raw payload for audit purposes
### Attribution
The system supports attribution through:
- `source_site` field identifying the originating site
- `business_context` for tenant boundary separation
- `product_context` for product/service categorization
- `form_provider`, `form_id`, `form_name` for form tracking
## Authentication and Tenant Boundary Gaps
### Authentication
The intake endpoint requires an API key via the `x-intake-key` header:
```python
def require_intake_key(x_intake_key: Optional[str] = Header(default=None)) -> None:
    if not settings.intake_api_key:
        return
    if x_intake_key != settings.intake_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid intake key",
        )
```
### Tenant Boundary Issues
The current implementation has several gaps in tenant boundary enforcement:
1. **Client-controlled Context**: The `business_context` field is client-controlled and not validated against known business contexts, creating potential for data pollution.
2. **No Business Context Validation**: There's no validation that `business_context` values are legitimate or authorized for the submitting site.
3. **No Tenant Isolation Enforcement**: The system does not enforce tenant isolation - any client can submit data with any `business_context`.
4. **Missing Site-to-Business Mapping**: There's no mapping between `source_site` and allowed `business_context` values, allowing cross-tenant data contamination.
5. **No API Key Scoping**: The same API key is used for all sites, providing no mechanism to restrict which sites can submit to which business contexts.
## Safe Migration Path
### Immediate Steps (Current State)
1. Maintain current schema and endpoint
2. Continue using `x-intake-key` header authentication
3. Keep existing field structure for backward compatibility
## Notes
This audit was performed against revision `0f39b094f59281167dc00cbec805b7465a5a5627`.
Database persistence, HTTP routing, outbound CRM delivery and production delivery are not tested in this audit.
The existing optional intake key and client-controlled context must not be described as tenant isolation.