"""Schémas Pydantic pour l'extraction de requirements avec IA."""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from enum import Enum


class RequirementImportance(str, Enum):
    """Niveaux d'importance des requirements."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RequirementCategory(str, Enum):
    """Catégories de requirements dans les marchés publics."""
    TECHNICAL = "technical"
    ADMINISTRATIVE = "administrative"
    FINANCIAL = "financial"
    LEGAL = "legal"
    FUNCTIONAL = "functional"
    PERFORMANCE = "performance"


class ExtractedRequirement(BaseModel):
    """Schéma pour un requirement extrait par l'IA."""

    category: RequirementCategory = Field(
        ...,
        description="Catégorie du requirement"
    )
    description: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Description claire et concise de l'exigence"
    )
    importance: RequirementImportance = Field(
        ...,
        description="Niveau d'importance de l'exigence"
    )
    is_mandatory: bool = Field(
        ...,
        description="True si obligatoire, False si optionnel"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Score de confiance de l'extraction (0-1)"
    )
    source_text: str = Field(
        ...,
        max_length=1000,
        description="Extrait exact du texte source"
    )
    keywords: List[str] = Field(
        default_factory=list,
        description="Mots-clés pertinents extraits"
    )

    @field_validator('description')
    @classmethod
    def validate_description(cls, v: str) -> str:
        """Nettoie et valide la description."""
        v = v.strip()
        if len(v.split()) < 3:
            raise ValueError("Description trop courte (minimum 3 mots)")
        return v

    @field_validator('keywords')
    @classmethod
    def validate_keywords(cls, v: List[str]) -> List[str]:
        """Nettoie les mots-clés."""
        return [k.strip().lower() for k in v if k.strip()]

    class Config:
        schema_extra = {
            "example": {
                "category": "technical",
                "description": "Application web responsive compatible tous navigateurs",
                "importance": "high",
                "is_mandatory": True,
                "confidence": 0.92,
                "source_text": "L'application devra être développée en mode responsive...",
                "keywords": ["responsive", "web", "navigateurs"]
            }
        }


class RequirementExtractionResponse(BaseModel):
    """Réponse structurée de l'extraction de requirements."""

    requirements: List[ExtractedRequirement] = Field(
        ...,
        description="Liste des requirements extraits"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Métadonnées additionnelles de l'extraction"
    )
    extraction_method: str = Field(
        default="mistral-ai",
        description="Méthode d'extraction utilisée"
    )
    confidence_avg: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Score de confiance moyen de tous les requirements"
    )
    document_type: str = Field(
        ...,
        description="Type de document analysé (CCTP, CCAP, RC, etc.)"
    )
    processing_time_ms: int = Field(
        default=0,
        description="Temps de traitement en millisecondes"
    )

    @field_validator('confidence_avg')
    @classmethod
    def calculate_avg_confidence(cls, v: float, info) -> float:
        """Recalcule la confiance moyenne si nécessaire."""
        if info.data.get('requirements'):
            requirements = info.data['requirements']
            calculated_avg = sum(r.confidence for r in requirements) / len(requirements)
            if abs(v - calculated_avg) > 0.01:  # Tolérance de 0.01
                return calculated_avg
        return v

    class Config:
        schema_extra = {
            "example": {
                "requirements": [
                    {
                        "category": "technical",
                        "description": "Développement d'application web responsive",
                        "importance": "high",
                        "is_mandatory": True,
                        "confidence": 0.92,
                        "source_text": "L'application devra être développée...",
                        "keywords": ["responsive", "web"]
                    }
                ],
                "metadata": {
                    "pages_analyzed": 10,
                    "language": "fr"
                },
                "extraction_method": "mistral-ai",
                "confidence_avg": 0.92,
                "document_type": "CCTP",
                "processing_time_ms": 3500
            }
        }


class RequirementExtractionRequest(BaseModel):
    """Requête pour l'extraction de requirements."""

    document_id: str = Field(
        ...,
        description="ID du document à analyser"
    )
    document_type: Optional[str] = Field(
        None,
        description="Type de document (CCTP, CCAP, RC, BPU)"
    )
    force_reprocess: bool = Field(
        default=False,
        description="Forcer le retraitement même si déjà en cache"
    )
    use_cache: bool = Field(
        default=True,
        description="Utiliser le cache si disponible"
    )
    max_requirements: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Nombre maximum de requirements à extraire"
    )
    min_confidence: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Score de confiance minimum pour inclure un requirement"
    )