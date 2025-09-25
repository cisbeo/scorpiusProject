"""Requirements extraction engine for tender documents."""

import re
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
from datetime import datetime


class RequirementCategory(Enum):
    """Categories of requirements in tender documents."""
    TECHNICAL = "technique"
    ADMINISTRATIVE = "administratif"
    FUNCTIONAL = "fonctionnel"
    FINANCIAL = "financier"
    LEGAL = "juridique"
    QUALIFICATION = "qualification"
    PERFORMANCE = "performance"
    SECURITY = "sécurité"
    GENERAL = "général"


class RequirementPriority(Enum):
    """Priority levels for requirements."""
    MANDATORY = "obligatoire"
    DESIRABLE = "souhaitable"
    OPTIONAL = "optionnel"
    ELIMINATORY = "éliminatoire"


@dataclass
class ExtractedRequirement:
    """Requirement extracted from a document."""
    category: RequirementCategory
    description: str
    priority: RequirementPriority
    section_reference: str
    keywords: List[str]
    compliance_checkable: bool
    original_text: str
    confidence_score: float = 0.0
    position: int = 0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "category": self.category.value,
            "description": self.description,
            "priority": self.priority.value,
            "section_reference": self.section_reference,
            "keywords": self.keywords,
            "compliance_checkable": self.compliance_checkable,
            "original_text": self.original_text,
            "confidence_score": self.confidence_score,
            "position": self.position,
            "metadata": self.metadata
        }


class RequirementsExtractor:
    """Intelligent requirements extraction from tender documents."""

    def __init__(self):
        """Initialize the requirements extractor with French patterns."""

        # Mandatory requirement patterns
        self.mandatory_patterns = [
            r"(?:doit|doivent|devra|devront)\s+(?:être|avoir|posséder|fournir|respecter|présenter)",
            r"(?:il est|il sera)\s+(?:obligatoire|impératif|nécessaire|requis|exigé)",
            r"(?:obligation|obligatoire(?:ment)?|impératif|exigence|requis|nécessaire)",
            r"(?:sous peine|à peine)\s+(?:de|d')",
            r"(?:minimum|au moins|au minimum)",
            r"(?:conformément|en conformité|selon)",
            r"(?:critère(?:s)?\s+(?:éliminatoire|obligatoire))",
        ]

        # Desirable requirement patterns
        self.desirable_patterns = [
            r"(?:souhaitable|souhaité|préférable|recommandé)",
            r"(?:serait|sera)\s+(?:apprécié|valorisé|un plus)",
            r"(?:de préférence|idéalement)",
            r"(?:pourra|pourront)\s+être",
        ]

        # Category identification keywords
        self.category_keywords = {
            RequirementCategory.TECHNICAL: [
                "technique", "technologie", "système", "informatique", "logiciel",
                "matériel", "infrastructure", "serveur", "réseau", "base de données",
                "API", "interface", "protocole", "format", "standard", "performance"
            ],
            RequirementCategory.ADMINISTRATIVE: [
                "administratif", "dossier", "document", "pièce", "justificatif",
                "attestation", "certificat", "déclaration", "formulaire", "inscription"
            ],
            RequirementCategory.FUNCTIONAL: [
                "fonctionnel", "fonction", "fonctionnalité", "module", "composant",
                "service", "processus", "workflow", "cas d'usage", "scénario"
            ],
            RequirementCategory.FINANCIAL: [
                "financier", "prix", "coût", "budget", "tarif", "facturation",
                "paiement", "garantie financière", "caution", "chiffre d'affaires"
            ],
            RequirementCategory.LEGAL: [
                "légal", "juridique", "loi", "règlement", "norme", "conformité",
                "RGPD", "licence", "propriété", "responsabilité", "contrat"
            ],
            RequirementCategory.QUALIFICATION: [
                "qualification", "certification", "agrément", "habilitation",
                "compétence", "expérience", "référence", "label", "diplôme"
            ],
            RequirementCategory.PERFORMANCE: [
                "performance", "délai", "temps de réponse", "disponibilité",
                "SLA", "engagement", "niveau de service", "indicateur", "KPI"
            ],
            RequirementCategory.SECURITY: [
                "sécurité", "sécurisé", "protection", "confidentialité",
                "authentification", "chiffrement", "sauvegarde", "ISO 27001", "SecNumCloud"
            ]
        }

        # Technical requirement specific patterns
        self.technical_patterns = {
            "infrastructure": [
                r"(?:serveur|cloud|hébergement|datacenter|virtualisation)",
                r"(?:CPU|RAM|stockage|bande passante|réseau)",
            ],
            "development": [
                r"(?:langage|framework|bibliothèque|API|REST|SOAP)",
                r"(?:version|compatible|intégration|interopérabilité)",
            ],
            "security": [
                r"(?:chiffrement|TLS|SSL|authentification|autorisation)",
                r"(?:HTTPS|VPN|firewall|WAF|antivirus)",
            ],
            "performance": [
                r"(?:latence|débit|concurrent|simultané|charge)",
                r"(?:temps de réponse|disponibilité|SLA|\d+\s*%)",
            ]
        }

        # Evaluation criteria patterns
        self.criteria_patterns = [
            r"critère(?:s)?\s+(?:d'|de)\s*(?:évaluation|sélection|attribution)",
            r"pondération|coefficient|note|notation|barème",
            r"(?:prix|valeur technique|délai|qualité)",
        ]

    async def extract_requirements(
        self,
        text: str,
        structured_content: Optional[Dict[str, Any]] = None
    ) -> List[ExtractedRequirement]:
        """
        Extract requirements from document text.

        Args:
            text: Raw text content
            structured_content: Optional structured content from Docling

        Returns:
            List of extracted requirements
        """
        requirements = []

        # Split into sections and sentences
        sections = self._split_into_sections(text)

        for section_ref, section_text in sections.items():
            sentences = self._split_into_sentences(section_text)

            for position, sentence in enumerate(sentences):
                if self._is_requirement(sentence):
                    requirement = self._parse_requirement(
                        sentence=sentence,
                        section_ref=section_ref,
                        position=position,
                        full_text=section_text
                    )
                    if requirement:
                        requirements.append(requirement)

        # Extract from structured content if available
        if structured_content:
            structured_reqs = self._extract_from_structured(structured_content)
            requirements.extend(structured_reqs)

        # Deduplicate and sort by priority
        requirements = self._deduplicate_requirements(requirements)
        requirements.sort(key=lambda r: (
            0 if r.priority == RequirementPriority.MANDATORY else 1,
            r.position
        ))

        return requirements

    def _split_into_sections(self, text: str) -> Dict[str, str]:
        """
        Split document text into sections.

        Args:
            text: Full document text

        Returns:
            Dictionary mapping section references to text
        """
        sections = {}

        # Pattern for section headers
        section_patterns = [
            r"(?:^|\n)(\d+(?:\.\d+)*)\s*[.\-]?\s*([A-Z][^.!?]*)",
            r"(?:^|\n)(Article\s+\d+)\s*[:\-]?\s*([^.!?]*)",
            r"(?:^|\n)(CHAPITRE\s+[IVX]+)\s*[:\-]?\s*([^.!?]*)",
            r"(?:^|\n)([A-Z][^.!?]{5,50})\s*:\s*\n",
        ]

        current_section = "0"
        current_text = []
        lines = text.split('\n')

        for line in lines:
            # Check if line is a section header
            is_header = False
            for pattern in section_patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    # Save previous section
                    if current_text:
                        sections[current_section] = '\n'.join(current_text)

                    # Start new section
                    current_section = match.group(1) if match.lastindex >= 1 else line[:50]
                    current_text = [line]
                    is_header = True
                    break

            if not is_header:
                current_text.append(line)

        # Save last section
        if current_text:
            sections[current_section] = '\n'.join(current_text)

        return sections if sections else {"document": text}

    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences.

        Args:
            text: Text to split

        Returns:
            List of sentences
        """
        # French sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)

        # Additional splitting on bullet points and newlines
        expanded = []
        for sentence in sentences:
            if '\n' in sentence:
                parts = sentence.split('\n')
                expanded.extend([p.strip() for p in parts if p.strip()])
            else:
                expanded.append(sentence.strip())

        return [s for s in expanded if len(s) > 10]

    def _is_requirement(self, sentence: str) -> bool:
        """
        Check if a sentence contains a requirement.

        Args:
            sentence: Sentence to check

        Returns:
            True if sentence contains requirement indicators
        """
        sentence_lower = sentence.lower()

        # Check mandatory patterns
        for pattern in self.mandatory_patterns:
            if re.search(pattern, sentence_lower):
                return True

        # Check desirable patterns
        for pattern in self.desirable_patterns:
            if re.search(pattern, sentence_lower):
                return True

        # Check for specific requirement keywords
        requirement_keywords = [
            "exigence", "requirement", "spécification",
            "condition", "critère", "contrainte"
        ]

        return any(keyword in sentence_lower for keyword in requirement_keywords)

    def _parse_requirement(
        self,
        sentence: str,
        section_ref: str,
        position: int,
        full_text: str
    ) -> Optional[ExtractedRequirement]:
        """
        Parse a sentence into a requirement.

        Args:
            sentence: Sentence containing requirement
            section_ref: Section reference
            position: Position in section
            full_text: Full section text for context

        Returns:
            ExtractedRequirement or None if parsing fails
        """
        # Determine priority
        priority = self._determine_priority(sentence)

        # Determine category
        category = self._determine_category(sentence, full_text)

        # Extract keywords
        keywords = self._extract_keywords(sentence)

        # Clean description
        description = self._clean_description(sentence)

        # Check if compliance is checkable
        compliance_checkable = self._is_compliance_checkable(sentence)

        # Calculate confidence score
        confidence_score = self._calculate_confidence(sentence, priority, category)

        return ExtractedRequirement(
            category=category,
            description=description,
            priority=priority,
            section_reference=section_ref,
            keywords=keywords,
            compliance_checkable=compliance_checkable,
            original_text=sentence,
            confidence_score=confidence_score,
            position=position
        )

    def _determine_priority(self, sentence: str) -> RequirementPriority:
        """
        Determine the priority of a requirement.

        Args:
            sentence: Requirement sentence

        Returns:
            RequirementPriority enum value
        """
        sentence_lower = sentence.lower()

        # Check for eliminatory criteria
        if "éliminatoire" in sentence_lower or "sous peine" in sentence_lower:
            return RequirementPriority.ELIMINATORY

        # Check for mandatory
        for pattern in self.mandatory_patterns:
            if re.search(pattern, sentence_lower):
                return RequirementPriority.MANDATORY

        # Check for desirable
        for pattern in self.desirable_patterns:
            if re.search(pattern, sentence_lower):
                return RequirementPriority.DESIRABLE

        # Check for optional
        if any(word in sentence_lower for word in ["optionnel", "facultatif", "peut", "pourra"]):
            return RequirementPriority.OPTIONAL

        # Default to mandatory if contains strong requirement words
        if any(word in sentence_lower for word in ["doit", "obligatoire", "requis"]):
            return RequirementPriority.MANDATORY

        return RequirementPriority.DESIRABLE

    def _determine_category(self, sentence: str, context: str) -> RequirementCategory:
        """
        Determine the category of a requirement.

        Args:
            sentence: Requirement sentence
            context: Surrounding text for context

        Returns:
            RequirementCategory enum value
        """
        combined_text = (sentence + " " + context[:500]).lower()

        # Count keyword matches for each category
        category_scores = {}

        for category, keywords in self.category_keywords.items():
            score = sum(1 for keyword in keywords if keyword in combined_text)
            if score > 0:
                category_scores[category] = score

        # Return category with highest score
        if category_scores:
            best_category = max(category_scores, key=category_scores.get)
            return best_category

        return RequirementCategory.GENERAL

    def _extract_keywords(self, sentence: str) -> List[str]:
        """
        Extract keywords from a requirement sentence.

        Args:
            sentence: Requirement sentence

        Returns:
            List of keywords
        """
        keywords = []

        # Technical terms pattern
        technical_terms = re.findall(
            r'\b(?:[A-Z]+(?:\s+[A-Z]+)*|[A-Z][a-z]+(?:[A-Z][a-z]+)+|\d+[\w\-]+)\b',
            sentence
        )
        keywords.extend(technical_terms)

        # Numbers and units
        numbers_units = re.findall(
            r'\b\d+\s*(?:Go|Mo|Ko|GB|MB|KB|ms|s|%|€|jours?|heures?|ans?)\b',
            sentence,
            re.IGNORECASE
        )
        keywords.extend(numbers_units)

        # Remove duplicates and clean
        keywords = list(set(k.strip() for k in keywords if len(k) > 2))

        return keywords[:10]  # Limit to 10 most relevant

    def _clean_description(self, sentence: str) -> str:
        """
        Clean and format requirement description.

        Args:
            sentence: Raw requirement text

        Returns:
            Cleaned description
        """
        # Remove excessive whitespace
        description = ' '.join(sentence.split())

        # Remove bullet points and numbering
        description = re.sub(r'^[\-•*\d]+[.\)]\s*', '', description)

        # Capitalize first letter
        if description and description[0].islower():
            description = description[0].upper() + description[1:]

        # Ensure ends with period
        if description and not description[-1] in '.!?':
            description += '.'

        return description

    def _is_compliance_checkable(self, sentence: str) -> bool:
        """
        Determine if requirement compliance can be checked automatically.

        Args:
            sentence: Requirement sentence

        Returns:
            True if compliance can be checked
        """
        checkable_patterns = [
            r'\b\d+\s*(?:Go|Mo|Ko|GB|MB|KB|ms|s|%)\b',  # Measurable values
            r'(?:certification|certificat|ISO|norme)',  # Certifications
            r'(?:version|compatible|format)',  # Technical specs
            r'(?:minimum|maximum|inférieur|supérieur)',  # Thresholds
        ]

        sentence_lower = sentence.lower()
        return any(re.search(pattern, sentence_lower) for pattern in checkable_patterns)

    def _calculate_confidence(
        self,
        sentence: str,
        priority: RequirementPriority,
        category: RequirementCategory
    ) -> float:
        """
        Calculate confidence score for requirement extraction.

        Args:
            sentence: Requirement sentence
            priority: Determined priority
            category: Determined category

        Returns:
            Confidence score between 0 and 1
        """
        score = 0.5  # Base score

        # Increase score for clear requirement patterns
        sentence_lower = sentence.lower()

        if any(re.search(p, sentence_lower) for p in self.mandatory_patterns):
            score += 0.2

        # Increase for specific categories
        if category != RequirementCategory.GENERAL:
            score += 0.1

        # Increase for eliminatory or mandatory priority
        if priority in [RequirementPriority.MANDATORY, RequirementPriority.ELIMINATORY]:
            score += 0.1

        # Increase for presence of specific keywords
        if any(word in sentence_lower for word in ["doit", "obligatoire", "exigé"]):
            score += 0.1

        return min(score, 1.0)

    def _extract_from_structured(
        self,
        structured_content: Dict[str, Any]
    ) -> List[ExtractedRequirement]:
        """
        Extract requirements from structured content.

        Args:
            structured_content: Structured content from Docling

        Returns:
            List of extracted requirements
        """
        requirements = []

        # Extract from tables
        for table in structured_content.get("tables", []):
            table_reqs = self._extract_from_table(table)
            requirements.extend(table_reqs)

        # Extract from lists
        for list_item in structured_content.get("lists", []):
            list_reqs = self._extract_from_list(list_item)
            requirements.extend(list_reqs)

        return requirements

    def _extract_from_table(self, table: Dict[str, Any]) -> List[ExtractedRequirement]:
        """
        Extract requirements from a table.

        Args:
            table: Table data

        Returns:
            List of requirements found in table
        """
        requirements = []

        headers = table.get("headers", [])
        rows = table.get("rows", [])

        # Look for requirement-like headers
        req_col = -1
        for i, header in enumerate(headers):
            if any(word in header.lower() for word in ["exigence", "requirement", "critère"]):
                req_col = i
                break

        if req_col >= 0:
            for row in rows:
                if req_col < len(row) and row[req_col]:
                    # Create requirement from table row
                    requirement = ExtractedRequirement(
                        category=RequirementCategory.GENERAL,
                        description=row[req_col],
                        priority=RequirementPriority.MANDATORY,
                        section_reference="table",
                        keywords=[],
                        compliance_checkable=False,
                        original_text=str(row),
                        confidence_score=0.7
                    )
                    requirements.append(requirement)

        return requirements

    def _extract_from_list(self, list_data: Dict[str, Any]) -> List[ExtractedRequirement]:
        """
        Extract requirements from a list.

        Args:
            list_data: List data

        Returns:
            List of requirements found in list
        """
        requirements = []

        for item in list_data.get("items", []):
            if self._is_requirement(item):
                requirement = self._parse_requirement(
                    sentence=item,
                    section_ref="list",
                    position=0,
                    full_text=""
                )
                if requirement:
                    requirements.append(requirement)

        return requirements

    def _deduplicate_requirements(
        self,
        requirements: List[ExtractedRequirement]
    ) -> List[ExtractedRequirement]:
        """
        Remove duplicate requirements.

        Args:
            requirements: List of requirements

        Returns:
            Deduplicated list
        """
        seen_descriptions = set()
        unique_requirements = []

        for req in requirements:
            # Normalize description for comparison
            normalized = req.description.lower().strip()

            if normalized not in seen_descriptions:
                seen_descriptions.add(normalized)
                unique_requirements.append(req)
            else:
                # If duplicate, keep the one with higher confidence
                for i, existing in enumerate(unique_requirements):
                    if existing.description.lower().strip() == normalized:
                        if req.confidence_score > existing.confidence_score:
                            unique_requirements[i] = req
                        break

        return unique_requirements

    async def extract_evaluation_criteria(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract evaluation criteria from document.

        Args:
            text: Document text

        Returns:
            List of evaluation criteria with weights
        """
        criteria = []

        # Look for criteria sections
        criteria_sections = re.findall(
            r'(?:critères?\s+d[\'e]\s*(?:évaluation|sélection|attribution).*?)(?=\n\n|\Z)',
            text,
            re.IGNORECASE | re.DOTALL
        )

        for section in criteria_sections:
            # Extract individual criteria
            lines = section.split('\n')
            for line in lines:
                # Look for criteria with percentages
                match = re.search(
                    r'([^:]+):\s*(\d+)\s*%',
                    line
                )
                if match:
                    criteria.append({
                        "name": match.group(1).strip(),
                        "weight": int(match.group(2)),
                        "type": "percentage"
                    })
                else:
                    # Look for criteria with coefficients
                    match = re.search(
                        r'([^:]+):\s*(?:coefficient|coef\.?)\s*(\d+(?:\.\d+)?)',
                        line,
                        re.IGNORECASE
                    )
                    if match:
                        criteria.append({
                            "name": match.group(1).strip(),
                            "weight": float(match.group(2)),
                            "type": "coefficient"
                        })

        return criteria