# 🏗️ Architecture API Scorpius - Priorisation MoSCoW

## 📌 Vue d'Ensemble

Architecture RESTful + WebSocket organisée en microservices avec priorisation MoSCoW (Must-Have, Should-Have, Could-Have, Nice-to-Have).

## 🔴 MUST-HAVE - Core Fonctionnel MVP

### 1. Authentication & Authorization
```
POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
POST   /api/v1/auth/logout
GET    /api/v1/auth/me
```

### 2. Document Management
```
POST   /api/v1/documents/upload
GET    /api/v1/documents/{document_id}
GET    /api/v1/documents/{document_id}/status
DELETE /api/v1/documents/{document_id}
GET    /api/v1/documents/list
```

### 3. Tender Analysis Core
```
POST   /api/v1/tenders/create
GET    /api/v1/tenders/{tender_id}
POST   /api/v1/tenders/{tender_id}/documents
POST   /api/v1/tenders/{tender_id}/analyze
GET    /api/v1/tenders/{tender_id}/analysis
```

### 4. Requirements Extraction
```
GET    /api/v1/tenders/{tender_id}/requirements
GET    /api/v1/tenders/{tender_id}/requirements/{requirement_id}
POST   /api/v1/tenders/{tender_id}/requirements/extract
```

### 5. RAG Core (Search & Query)
```
POST   /api/v1/rag/query
POST   /api/v1/rag/search
GET    /api/v1/rag/documents/{document_id}/chunks
```

### 6. Basic Reporting
```
GET    /api/v1/tenders/{tender_id}/report
GET    /api/v1/tenders/{tender_id}/go-no-go
GET    /api/v1/tenders/{tender_id}/conformity-score
```

## 🟡 SHOULD-HAVE - Valeur Ajoutée Importante

### 1. Advanced Document Processing
```
POST   /api/v1/documents/batch-upload
POST   /api/v1/documents/process-multi-format
GET    /api/v1/documents/{document_id}/extracted-content
POST   /api/v1/documents/{document_id}/reprocess
```

### 2. Requirements Intelligence
```
POST   /api/v1/requirements/classify
POST   /api/v1/requirements/map-responses
POST   /api/v1/requirements/validate-responses
GET    /api/v1/requirements/suggestions
POST   /api/v1/requirements/cross-reference
```

### 3. Excel Template Management
```
POST   /api/v1/templates/detect-type
POST   /api/v1/templates/{template_id}/extract-structure
POST   /api/v1/templates/{template_id}/auto-fill
POST   /api/v1/templates/{template_id}/validate
GET    /api/v1/templates/{template_id}/preview
```

### 4. Response Generation
```
POST   /api/v1/responses/generate
POST   /api/v1/responses/{response_id}/improve
POST   /api/v1/responses/batch-generate
GET    /api/v1/responses/{response_id}/validation
```

### 5. Company Profile Management
```
POST   /api/v1/company/profile
GET    /api/v1/company/profile
PUT    /api/v1/company/profile
POST   /api/v1/company/capabilities
POST   /api/v1/company/certifications
POST   /api/v1/company/references
```

### 6. Workflow Progress (WebSocket)
```
WS     /ws/workflow/{tender_id}
POST   /api/v1/workflow/{tender_id}/start
GET    /api/v1/workflow/{tender_id}/status
POST   /api/v1/workflow/{tender_id}/pause
POST   /api/v1/workflow/{tender_id}/resume
```

## 🟢 COULD-HAVE - Optimisations & Confort

### 1. Workflow Orchestration
```
POST   /api/v1/workflow/create
GET    /api/v1/workflow/{workflow_id}/steps
POST   /api/v1/workflow/{workflow_id}/execute-step
POST   /api/v1/workflow/{workflow_id}/skip-step
GET    /api/v1/workflow/{workflow_id}/history
POST   /api/v1/workflow/{workflow_id}/rollback
```

### 2. Manual Review System
```
GET    /api/v1/reviews/pending
POST   /api/v1/reviews/{review_id}/submit
POST   /api/v1/reviews/{review_id}/approve
POST   /api/v1/reviews/{review_id}/reject
POST   /api/v1/reviews/{review_id}/request-changes
```

### 3. Submission Package Generation
```
POST   /api/v1/submission/generate/{tender_id}
GET    /api/v1/submission/preview/{tender_id}
POST   /api/v1/submission/validate/{tender_id}
GET    /api/v1/submission/checklist/{tender_id}
GET    /api/v1/submission/download/{submission_id}
```

### 4. Analytics & Insights
```
GET    /api/v1/analytics/tender-stats
GET    /api/v1/analytics/success-rate
GET    /api/v1/analytics/requirements-coverage
GET    /api/v1/analytics/processing-time
GET    /api/v1/analytics/user-activity
```

### 5. Template Library
```
GET    /api/v1/library/templates
POST   /api/v1/library/templates/save
GET    /api/v1/library/responses
POST   /api/v1/library/responses/save
GET    /api/v1/library/search
```

### 6. Collaboration Features
```
POST   /api/v1/tenders/{tender_id}/share
POST   /api/v1/tenders/{tender_id}/comments
GET    /api/v1/tenders/{tender_id}/comments
POST   /api/v1/tenders/{tender_id}/assign
GET    /api/v1/tenders/{tender_id}/activity-log
```

## 🔵 NICE-TO-HAVE - Features Avancées

### 1. AI Training & Feedback
```
POST   /api/v1/ai/feedback
POST   /api/v1/ai/train-custom-model
GET    /api/v1/ai/model-performance
POST   /api/v1/ai/fine-tune
```

### 2. Advanced Integrations
```
POST   /api/v1/integrations/crm/sync
POST   /api/v1/integrations/erp/sync
GET    /api/v1/integrations/marketplace/opportunities
POST   /api/v1/integrations/signature/send
```

### 3. Predictive Analytics
```
GET    /api/v1/predictions/win-probability
GET    /api/v1/predictions/optimal-price
GET    /api/v1/predictions/competitor-analysis
GET    /api/v1/predictions/tender-complexity
```

### 4. Notification System
```
POST   /api/v1/notifications/subscribe
GET    /api/v1/notifications/list
PUT    /api/v1/notifications/{notification_id}/read
POST   /api/v1/notifications/preferences
WS     /ws/notifications
```

### 5. Versioning & Audit
```
GET    /api/v1/audit/trail/{entity_id}
GET    /api/v1/versions/{entity_type}/{entity_id}
POST   /api/v1/versions/{entity_type}/{entity_id}/restore
GET    /api/v1/audit/compliance-report
```

### 6. Export & Import
```
POST   /api/v1/export/tender/{tender_id}
POST   /api/v1/export/bulk
POST   /api/v1/import/tender
POST   /api/v1/import/company-data
```

## 📊 Architecture Technique Détaillée

### Base URL Structure
```
https://api.scorpius.fr/v1/
```

### Authentication Headers
```http
Authorization: Bearer {jwt_token}
X-Tenant-ID: {tenant_id}  // Pour multi-tenancy future
X-Request-ID: {uuid}       // Traçabilité
```

### Response Format Standard
```json
{
  "success": boolean,
  "data": object | array,
  "meta": {
    "page": number,
    "per_page": number,
    "total": number,
    "request_id": string,
    "processing_time_ms": number
  },
  "errors": [
    {
      "code": string,
      "message": string,
      "field": string
    }
  ]
}
```

### WebSocket Events
```javascript
// Workflow Progress
{
  "event": "workflow.progress",
  "data": {
    "step": "analyze_requirements",
    "progress": 45,
    "status": "in_progress",
    "eta_seconds": 120
  }
}

// Manual Review Request
{
  "event": "review.requested",
  "data": {
    "review_id": "uuid",
    "type": "visual_planning",
    "priority": "high",
    "deadline": "2024-01-15T10:00:00Z"
  }
}

// Completion Notification
{
  "event": "workflow.completed",
  "data": {
    "tender_id": "uuid",
    "success": true,
    "next_steps": ["review", "submit"]
  }
}
```

### Rate Limiting
```
Must-Have:    100 req/min
Should-Have:  50 req/min
Could-Have:   30 req/min
Nice-to-Have: 10 req/min
```

### Error Codes
```
400: Bad Request
401: Unauthorized
403: Forbidden
404: Not Found
409: Conflict
422: Unprocessable Entity
429: Too Many Requests
500: Internal Server Error
503: Service Unavailable
```

## 🚀 Phases d'Implémentation

### Phase 1 - MVP (Semaines 1-3)
✅ Tous les endpoints **MUST-HAVE**
- Authentication complète
- Upload & analyse basique
- Extraction des exigences
- RAG queries simples
- Reporting basique

### Phase 2 - Valeur Ajoutée (Semaines 4-6)
✅ Endpoints **SHOULD-HAVE** prioritaires
- Multi-format processing
- Intelligence des exigences
- Auto-fill Excel
- Response generation
- WebSocket progress

### Phase 3 - Orchestration (Semaines 7-9)
✅ **SHOULD-HAVE** restants + **COULD-HAVE** essentiels
- Workflow complet
- Manual review system
- Submission generation
- Analytics basiques
- Collaboration simple

### Phase 4 - Excellence (Semaines 10+)
✅ **COULD-HAVE** restants + **NICE-TO-HAVE** sélectionnés
- AI feedback loop
- Integrations externes
- Predictive analytics
- Advanced notifications
- Audit complet

## 📈 Métriques de Succès

### Must-Have KPIs
- ✅ Temps de réponse API < 200ms
- ✅ Disponibilité > 99%
- ✅ Taux d'extraction exigences > 90%

### Should-Have KPIs
- ✅ Auto-fill accuracy > 85%
- ✅ Response generation relevance > 80%
- ✅ Workflow completion rate > 95%

### Nice-to-Have KPIs
- ✅ Prediction accuracy > 75%
- ✅ User engagement score > 8/10
- ✅ Integration reliability > 99.5%

## 🔒 Sécurité & Compliance

### Must-Have Security
- JWT avec rotation
- HTTPS obligatoire
- Rate limiting
- Input validation
- SQL injection protection

### Should-Have Security
- 2FA authentication
- IP whitelisting
- Audit logging
- Encryption at rest
- GDPR compliance

### Nice-to-Have Security
- Zero-trust architecture
- Blockchain audit trail
- Homomorphic encryption
- Quantum-resistant crypto
- SOC2 certification

## 💡 Notes d'Architecture

1. **Modularité**: Chaque groupe d'endpoints peut être déployé comme microservice indépendant
2. **Scalabilité**: Architecture horizontalement scalable avec load balancing
3. **Résilience**: Circuit breakers et retry policies sur tous les services externes
4. **Observabilité**: Logging structuré, traces distribuées, métriques Prometheus
5. **Évolutivité**: Versioning d'API pour permettre des évolutions sans breaking changes

Cette architecture permet de livrer rapidement de la valeur (Must-Have) tout en préparant l'évolution vers une plateforme complète et sophistiquée.