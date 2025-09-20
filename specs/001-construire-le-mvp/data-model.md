# Data Model Design

## Core Entities

### User
**Purpose**: Authentication and authorization for bid managers and admins
**Fields**:
- id: UUID (primary key)
- email: String (unique, not null)
- password_hash: String (not null)
- full_name: String (not null)
- role: Enum (bid_manager, admin)
- is_active: Boolean (default true)
- tenant_id: UUID (nullable, prepared for multi-tenancy)
- created_at: Timestamp
- updated_at: Timestamp
- deleted_at: Timestamp (nullable, soft delete)

**Relationships**:
- One-to-Many: ProcurementDocuments (uploaded_by)
- One-to-Many: BidResponses (created_by)
- One-to-Many: AuditLogs (user_id)

### ProcurementDocument
**Purpose**: Store uploaded procurement PDF documents with extracted metadata
**Fields**:
- id: UUID (primary key)
- original_filename: String (not null)
- file_path: String (not null, encrypted)
- file_size: Integer (bytes)
- file_hash: String (SHA-256)
- mime_type: String
- status: Enum (uploaded, processing, processed, failed)
- uploaded_by: UUID (foreign key to User)
- processing_started_at: Timestamp (nullable)
- processing_completed_at: Timestamp (nullable)
- processing_duration_ms: Integer (nullable)
- error_message: Text (nullable)
- tenant_id: UUID (nullable)
- version: Integer (default 1)
- created_at: Timestamp
- updated_at: Timestamp
- deleted_at: Timestamp (nullable)

**Relationships**:
- Many-to-One: User (uploaded_by)
- One-to-One: ExtractedRequirements
- One-to-Many: BidResponses
- One-to-Many: ProcessingEvents

### ExtractedRequirements
**Purpose**: Structured data extracted from procurement documents
**Fields**:
- id: UUID (primary key)
- document_id: UUID (foreign key to ProcurementDocument)
- title: String (not null)
- reference_number: String (nullable)
- buyer_organization: String (not null)
- submission_deadline: Timestamp (not null)
- budget_min: Decimal (nullable)
- budget_max: Decimal (nullable)
- requirements_json: JSONB (structured requirements)
- evaluation_criteria_json: JSONB
- mandatory_documents: JSONB (array of required docs)
- extracted_text: Text (full document text)
- extraction_confidence: Float (0-1)
- language: String (default 'fr')
- tenant_id: UUID (nullable)
- created_at: Timestamp
- updated_at: Timestamp

**JSON Structure Examples**:
```json
// requirements_json
{
  "technical": ["requirement1", "requirement2"],
  "functional": ["requirement3"],
  "administrative": ["requirement4"]
}

// evaluation_criteria_json
{
  "price": 40,
  "technical": 35,
  "experience": 25
}
```

**Relationships**:
- One-to-One: ProcurementDocument
- One-to-Many: CapabilityMatches

### CompanyProfile
**Purpose**: Static company information for capability matching
**Fields**:
- id: UUID (primary key)
- company_name: String (not null)
- siret: String (unique, not null)
- description: Text
- capabilities_json: JSONB (list of capabilities)
- certifications_json: JSONB
- references_json: JSONB
- team_size: Integer
- annual_revenue: Decimal
- founding_year: Integer
- contact_email: String
- contact_phone: String
- address: Text
- tenant_id: UUID (nullable)
- version: Integer (default 1)
- created_at: Timestamp
- updated_at: Timestamp

**JSON Structure Examples**:
```json
// capabilities_json
[
  {"name": "Web Development", "keywords": ["PHP", "JavaScript", "React"]},
  {"name": "Cloud Architecture", "keywords": ["AWS", "Azure", "DevOps"]}
]

// certifications_json
[
  {"name": "ISO 9001", "valid_until": "2025-12-31"},
  {"name": "Qualiopi", "valid_until": "2026-06-30"}
]
```

**Relationships**:
- One-to-Many: CapabilityMatches
- One-to-Many: BidResponses

### CapabilityMatch
**Purpose**: Analysis results matching requirements to company capabilities
**Fields**:
- id: UUID (primary key)
- extracted_requirements_id: UUID (foreign key)
- company_profile_id: UUID (foreign key)
- overall_score: Float (0-100)
- technical_score: Float (0-100)
- functional_score: Float (0-100)
- gaps_json: JSONB (identified gaps)
- strengths_json: JSONB (matching strengths)
- match_details_json: JSONB (detailed analysis)
- recommendation: Enum (go, no_go, review_needed)
- confidence_level: Float (0-1)
- tenant_id: UUID (nullable)
- created_at: Timestamp

**Relationships**:
- Many-to-One: ExtractedRequirements
- Many-to-One: CompanyProfile
- One-to-One: BidResponse

### BidResponse
**Purpose**: Generated bid response documents
**Fields**:
- id: UUID (primary key)
- procurement_document_id: UUID (foreign key)
- company_profile_id: UUID (foreign key)
- capability_match_id: UUID (foreign key)
- title: String (not null)
- response_type: Enum (technical, commercial, complete)
- content_json: JSONB (structured response content)
- generated_file_path: String (nullable)
- status: Enum (draft, reviewing, final)
- compliance_score: Float (0-100)
- compliance_issues_json: JSONB
- created_by: UUID (foreign key to User)
- reviewed_by: UUID (nullable, foreign key to User)
- submitted_at: Timestamp (nullable)
- tenant_id: UUID (nullable)
- version: Integer (default 1)
- created_at: Timestamp
- updated_at: Timestamp

**JSON Structure Example**:
```json
// content_json
{
  "executive_summary": "...",
  "technical_response": {
    "section1": "...",
    "section2": "..."
  },
  "commercial_proposal": {
    "pricing": {},
    "payment_terms": "..."
  }
}
```

**Relationships**:
- Many-to-One: ProcurementDocument
- Many-to-One: CompanyProfile
- One-to-One: CapabilityMatch
- Many-to-One: User (created_by, reviewed_by)
- One-to-Many: ComplianceChecks

### ComplianceCheck
**Purpose**: Track compliance validation results
**Fields**:
- id: UUID (primary key)
- bid_response_id: UUID (foreign key)
- rule_category: String (not null)
- rule_name: String (not null)
- status: Enum (passed, failed, warning)
- message: Text
- severity: Enum (critical, major, minor)
- auto_fixable: Boolean (default false)
- tenant_id: UUID (nullable)
- created_at: Timestamp

**Relationships**:
- Many-to-One: BidResponse

### ProcessingEvent
**Purpose**: Audit trail for document processing pipeline
**Fields**:
- id: UUID (primary key)
- document_id: UUID (foreign key to ProcurementDocument)
- stage: Enum (upload, validation, extraction, analysis, generation)
- status: Enum (started, completed, failed)
- duration_ms: Integer (nullable)
- metadata_json: JSONB
- error_details: Text (nullable)
- tenant_id: UUID (nullable)
- created_at: Timestamp

**Relationships**:
- Many-to-One: ProcurementDocument

### AuditLog
**Purpose**: Security and activity audit trail
**Fields**:
- id: UUID (primary key)
- user_id: UUID (foreign key to User, nullable for system events)
- action: String (not null)
- resource_type: String (not null)
- resource_id: UUID (not null)
- ip_address: String (nullable)
- user_agent: Text (nullable)
- metadata_json: JSONB
- tenant_id: UUID (nullable)
- created_at: Timestamp

**Relationships**:
- Many-to-One: User (nullable)

## Database Indexes

### Performance Indexes
- users.email (unique)
- procurement_documents.status
- procurement_documents.uploaded_by
- extracted_requirements.submission_deadline
- extracted_requirements.document_id (unique)
- capability_matches.overall_score
- bid_responses.procurement_document_id
- processing_events.document_id, created_at (composite)
- audit_logs.user_id, created_at (composite)

### Future Indexes (Prepared)
- All tables: tenant_id (for multi-tenancy)
- extracted_requirements: Full-text search on extracted_text
- Vector indexes on embeddings (when added)

## Constraints

### Business Rules
1. File upload size: MAX 50MB
2. Submission deadline: Must be future date
3. Scores: Range 0-100
4. Confidence levels: Range 0-1
5. Budget max >= Budget min (when both present)
6. User email: Valid email format
7. SIRET: Valid French company number format

### Referential Integrity
- Cascade soft deletes through relationships
- Prevent deletion of documents with active bid responses
- Maintain audit logs even when referenced entities deleted

## Migration Notes

### MVP to Future Evolution
1. **tenant_id**: Currently nullable, will become required for multi-tenancy
2. **embeddings**: New table for vector storage, linked to documents
3. **templates**: New table for customizable response templates
4. **collaborations**: New table for team-based bid development
5. **ml_models**: New table for versioned NLP models
6. **notifications**: New table for deadline alerts and updates

### Versioning Strategy
- All content entities have version field
- Previous versions stored in archive tables (future)
- Audit trail captures all changes

## State Transitions

### ProcurementDocument Status Flow
```
uploaded → processing → processed
         ↘          ↗
           failed
```

### BidResponse Status Flow
```
draft → reviewing → final
```

### ProcessingEvent Status Flow
```
started → completed
       ↘
        failed
```