"""Document type enumeration and metadata for procurement documents."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Set


class DocumentType(str, Enum):
    """
    Document types commonly found in French public procurement.

    Each type represents a specific document with its own purpose
    and structure in the tender process.
    """

    # Core tender documents
    RC = "rc"           # Règlement de Consultation
    CCAP = "ccap"       # Cahier des Clauses Administratives Particulières
    CCTP = "cctp"       # Cahier des Clauses Techniques Particulières
    CCAG = "ccag"       # Cahier des Clauses Administratives Générales

    # Pricing documents
    BPU = "bpu"         # Bordereau des Prix Unitaires
    DPGF = "dpgf"       # Décomposition du Prix Global et Forfaitaire
    DQE = "dqe"         # Détail Quantitatif Estimatif

    # Administrative documents
    AE = "ae"           # Acte d'Engagement
    DC1 = "dc1"         # Déclaration du Candidat (lettre de candidature)
    DC2 = "dc2"         # Déclaration du Candidat (déclaration sur l'honneur)
    ATTRI = "attri"     # Critères d'attribution

    # Technical documents
    PLANNING = "planning"       # Planning prévisionnel
    MEMOIRE = "memoire"         # Mémoire technique
    ANNEXE = "annexe"           # Annexes techniques

    # Other
    OTHER = "other"             # Autres documents


@dataclass
class DocumentTypeInfo:
    """Metadata and configuration for each document type."""

    document_type: DocumentType
    french_name: str
    description: str
    is_mandatory: bool
    expected_formats: Set[str]
    typical_sections: Optional[list[str]] = None
    keywords: Optional[list[str]] = None


# Document type metadata registry
DOCUMENT_TYPE_INFO = {
    DocumentType.RC: DocumentTypeInfo(
        document_type=DocumentType.RC,
        french_name="Règlement de Consultation",
        description="Définit les règles de la consultation et les modalités de sélection",
        is_mandatory=True,
        expected_formats={".pdf"},
        typical_sections=["Objet de la consultation", "Conditions de participation",
                         "Critères de sélection", "Modalités de remise"],
        keywords=["règlement", "consultation", "modalités", "critères"]
    ),

    DocumentType.CCAP: DocumentTypeInfo(
        document_type=DocumentType.CCAP,
        french_name="Cahier des Clauses Administratives Particulières",
        description="Définit les conditions administratives d'exécution du marché",
        is_mandatory=True,
        expected_formats={".pdf"},
        typical_sections=["Prix et règlement", "Délais", "Pénalités", "Résiliation"],
        keywords=["clauses administratives", "CCAP", "pénalités", "délais"]
    ),

    DocumentType.CCTP: DocumentTypeInfo(
        document_type=DocumentType.CCTP,
        french_name="Cahier des Clauses Techniques Particulières",
        description="Spécifie les exigences techniques et fonctionnelles",
        is_mandatory=True,
        expected_formats={".pdf"},
        typical_sections=["Spécifications techniques", "Exigences fonctionnelles",
                         "Contraintes", "Livrables"],
        keywords=["clauses techniques", "CCTP", "spécifications", "exigences"]
    ),

    DocumentType.BPU: DocumentTypeInfo(
        document_type=DocumentType.BPU,
        french_name="Bordereau des Prix Unitaires",
        description="Liste les prix unitaires pour chaque prestation",
        is_mandatory=False,
        expected_formats={".xlsx", ".xls", ".pdf"},
        keywords=["bordereau", "prix unitaires", "BPU", "tarifs"]
    ),

    DocumentType.DPGF: DocumentTypeInfo(
        document_type=DocumentType.DPGF,
        french_name="Décomposition du Prix Global et Forfaitaire",
        description="Détaille la décomposition du prix global",
        is_mandatory=False,
        expected_formats={".xlsx", ".xls", ".pdf"},
        keywords=["décomposition", "prix global", "DPGF", "forfaitaire"]
    ),

    DocumentType.DQE: DocumentTypeInfo(
        document_type=DocumentType.DQE,
        french_name="Détail Quantitatif Estimatif",
        description="Estime les quantités pour chaque prestation",
        is_mandatory=False,
        expected_formats={".xlsx", ".xls", ".pdf"},
        keywords=["détail quantitatif", "DQE", "estimatif", "quantités"]
    ),

    DocumentType.AE: DocumentTypeInfo(
        document_type=DocumentType.AE,
        french_name="Acte d'Engagement",
        description="Document contractuel signé par le candidat",
        is_mandatory=True,
        expected_formats={".pdf", ".docx", ".doc"},
        keywords=["acte engagement", "AE", "contractuel", "engagement"]
    ),

    DocumentType.PLANNING: DocumentTypeInfo(
        document_type=DocumentType.PLANNING,
        french_name="Planning Prévisionnel",
        description="Calendrier prévisionnel d'exécution",
        is_mandatory=False,
        expected_formats={".pdf", ".pptx", ".xlsx", ".mpp"},
        keywords=["planning", "calendrier", "délais", "phases"]
    ),

    DocumentType.OTHER: DocumentTypeInfo(
        document_type=DocumentType.OTHER,
        french_name="Autre Document",
        description="Document non classifié",
        is_mandatory=False,
        expected_formats={".pdf", ".docx", ".xlsx", ".pptx"},
        keywords=[]
    ),
}


# Set of mandatory document types
MANDATORY_DOCUMENT_TYPES: Set[DocumentType] = {
    doc_type
    for doc_type, info in DOCUMENT_TYPE_INFO.items()
    if info.is_mandatory
}


def get_document_type_info(doc_type: DocumentType) -> DocumentTypeInfo:
    """Get metadata for a document type."""
    return DOCUMENT_TYPE_INFO.get(doc_type, DOCUMENT_TYPE_INFO[DocumentType.OTHER])


def detect_document_type_from_filename(filename: str) -> DocumentType:
    """
    Attempt to detect document type from filename.

    Args:
        filename: Name of the file

    Returns:
        Detected DocumentType or OTHER if not recognized
    """
    filename_lower = filename.lower()

    # Direct matching patterns
    patterns = {
        DocumentType.RC: ["reglement", "consultation", "rc."],
        DocumentType.CCAP: ["ccap", "clauses_administratives", "clauses administratives"],
        DocumentType.CCTP: ["cctp", "clauses_techniques", "clauses techniques"],
        DocumentType.BPU: ["bpu", "bordereau_prix", "bordereau prix", "prix_unitaires"],
        DocumentType.DPGF: ["dpgf", "decomposition_prix", "prix_global"],
        DocumentType.DQE: ["dqe", "detail_quantitatif", "quantitatif_estimatif"],
        DocumentType.AE: ["acte_engagement", "acte engagement", "ae."],
        DocumentType.PLANNING: ["planning", "calendrier", "plan_"],
    }

    for doc_type, keywords in patterns.items():
        if any(keyword in filename_lower for keyword in keywords):
            return doc_type

    return DocumentType.OTHER


def detect_document_type_from_content(content: str, filename: str = "") -> DocumentType:
    """
    Detect document type from content analysis.

    Args:
        content: Text content of the document (first 5000 chars recommended)
        filename: Optional filename for additional hints

    Returns:
        Detected DocumentType
    """
    # First try filename detection
    if filename:
        file_type = detect_document_type_from_filename(filename)
        if file_type != DocumentType.OTHER:
            return file_type

    content_lower = content[:5000].lower() if len(content) > 5000 else content.lower()

    # Score each document type based on keyword matches
    scores = {}

    for doc_type, info in DOCUMENT_TYPE_INFO.items():
        if doc_type == DocumentType.OTHER or not info.keywords:
            continue

        score = 0
        for keyword in info.keywords:
            if keyword.lower() in content_lower:
                score += 1

        # Bonus for french name in content
        if info.french_name.lower() in content_lower:
            score += 3

        scores[doc_type] = score

    # Return the type with highest score, or OTHER if no matches
    if scores:
        best_match = max(scores.items(), key=lambda x: x[1])
        if best_match[1] > 0:  # At least one keyword match
            return best_match[0]

    return DocumentType.OTHER