#!/usr/bin/env python3
"""
Specialized extractors for procurement document analysis.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


@dataclass
class Requirement:
    """Represents an extracted requirement."""
    id: str
    category: str  # technical, functional, administrative
    text: str
    priority: str  # mandatory, optional, nice-to-have
    metadata: Dict[str, Any] = None


@dataclass
class Budget:
    """Represents budget information."""
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    currency: str = "EUR"
    vat_included: Optional[bool] = None
    payment_terms: Optional[str] = None
    budget_type: Optional[str] = None  # fixed, estimated, maximum


@dataclass
class Deadline:
    """Represents a deadline or timeline."""
    date: Optional[datetime] = None
    description: str = ""
    type: str = ""  # submission, delivery, milestone
    is_strict: bool = True


@dataclass
class Entity:
    """Represents a named entity."""
    name: str
    type: str  # organization, person, location, product
    role: Optional[str] = None  # buyer, supplier, contact
    metadata: Dict[str, Any] = None


class BaseExtractor(ABC):
    """Base class for all extractors."""
    
    @abstractmethod
    def extract(self, text: str, context: Optional[Dict[str, Any]] = None) -> Any:
        """Extract information from text."""
        pass


class RequirementExtractor(BaseExtractor):
    """
    Extracts requirements from procurement documents.
    """
    
    def __init__(self):
        self.requirement_patterns = [
            # Technical requirements
            (r"exigence[s]? technique[s]?", "technical"),
            (r"spécification[s]? technique[s]?", "technical"),
            (r"caractéristique[s]? technique[s]?", "technical"),
            (r"norme[s]? technique[s]?", "technical"),
            
            # Functional requirements
            (r"exigence[s]? fonctionnelle[s]?", "functional"),
            (r"besoin[s]? fonctionnel[s]?", "functional"),
            (r"fonctionnalité[s]? requise[s]?", "functional"),
            (r"service[s]? demandé[s]?", "functional"),
            
            # Administrative requirements
            (r"condition[s]? administrative[s]?", "administrative"),
            (r"document[s]? à fournir", "administrative"),
            (r"pièce[s]? justificative[s]?", "administrative"),
            (r"certification[s]? requise[s]?", "administrative"),
        ]
        
        self.priority_indicators = {
            "mandatory": [
                r"obligatoire", r"impératif", r"exigé", r"requis",
                r"doit", r"doivent", r"devra", r"devront", r"nécessaire"
            ],
            "optional": [
                r"optionnel", r"facultatif", r"souhaitable",
                r"peut", r"peuvent", r"pourra", r"pourront"
            ],
            "nice-to-have": [
                r"apprécié", r"valorisé", r"bonus", r"atout"
            ]
        }
        
    def extract(self, text: str, context: Optional[Dict[str, Any]] = None) -> List[Requirement]:
        """
        Extract requirements from text.
        
        Args:
            text: Input text
            context: Optional context (e.g., section title)
            
        Returns:
            List of extracted requirements
        """
        requirements = []
        
        # Split into sentences for finer analysis
        sentences = self._split_sentences(text)
        
        for idx, sentence in enumerate(sentences):
            # Detect requirement category
            category = self._detect_category(sentence, context)
            
            # Check if sentence contains requirement indicators
            if self._is_requirement(sentence):
                priority = self._detect_priority(sentence)
                
                req = Requirement(
                    id=f"REQ-{idx:04d}",
                    category=category,
                    text=sentence.strip(),
                    priority=priority,
                    metadata={
                        'position': idx,
                        'context': context.get('section_title') if context else None
                    }
                )
                requirements.append(req)
        
        return requirements
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # French sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s for s in sentences if s.strip()]
    
    def _detect_category(self, sentence: str, context: Optional[Dict[str, Any]]) -> str:
        """Detect requirement category."""
        sentence_lower = sentence.lower()
        
        for pattern, category in self.requirement_patterns:
            if re.search(pattern, sentence_lower):
                return category
        
        # Use context if available
        if context and 'section_title' in context:
            section = context['section_title'].lower()
            if 'technique' in section:
                return 'technical'
            elif 'fonction' in section:
                return 'functional'
            elif 'administratif' in section:
                return 'administrative'
        
        # Default based on keywords
        if any(word in sentence_lower for word in ['serveur', 'logiciel', 'système', 'api']):
            return 'technical'
        elif any(word in sentence_lower for word in ['service', 'fonction', 'utilisateur']):
            return 'functional'
        else:
            return 'administrative'
    
    def _is_requirement(self, sentence: str) -> bool:
        """Check if sentence contains a requirement."""
        indicators = [
            r'\bdoit\b', r'\bdoivent\b', r'\bdevra\b',
            r'\bnécessaire\b', r'\brequis\b', r'\bexigé\b',
            r'\bfournir\b', r'\bcomprendre\b', r'\binclure\b',
            r'\bgarantir\b', r'\bassurer\b', r'\bpermettre\b'
        ]
        
        sentence_lower = sentence.lower()
        return any(re.search(pattern, sentence_lower) for pattern in indicators)
    
    def _detect_priority(self, sentence: str) -> str:
        """Detect requirement priority."""
        sentence_lower = sentence.lower()
        
        for priority, patterns in self.priority_indicators.items():
            if any(re.search(pattern, sentence_lower) for pattern in patterns):
                return priority
        
        # Default to mandatory if contains strong indicators
        if re.search(r'\bdoit\b|\bdevra\b|\bobligatoire\b', sentence_lower):
            return 'mandatory'
        
        return 'optional'


class BudgetExtractor(BaseExtractor):
    """
    Extracts budget and financial information.
    """
    
    def __init__(self):
        # Patterns for amounts
        self.amount_patterns = [
            r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)\s*(?:€|EUR|euros?)',
            r'(\d+(?:[.,]\d+)?)\s*(?:millions?|M€|MEUR)',
            r'(\d+(?:[.,]\d+)?)\s*(?:milliers?|K€|KEUR)',
        ]
        
        # Budget type indicators
        self.budget_types = {
            'fixed': [r'fixe', r'forfaitaire', r'déterminé'],
            'estimated': [r'estimé', r'prévisionnel', r'indicatif'],
            'maximum': [r'maximum', r'plafond', r'ne pas dépasser']
        }
        
    def extract(self, text: str, context: Optional[Dict[str, Any]] = None) -> Optional[Budget]:
        """
        Extract budget information from text.
        
        Args:
            text: Input text
            context: Optional context
            
        Returns:
            Budget object or None
        """
        budget = Budget()
        amounts_found = []
        
        # Extract amounts
        for pattern in self.amount_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                amount_str = match.group(1)
                amount = self._parse_amount(amount_str, pattern)
                if amount:
                    amounts_found.append(amount)
        
        # Determine min/max from context
        if amounts_found:
            text_lower = text.lower()
            
            # Look for range indicators
            if 'entre' in text_lower and len(amounts_found) >= 2:
                budget.min_amount = min(amounts_found)
                budget.max_amount = max(amounts_found)
            elif 'minimum' in text_lower or 'au moins' in text_lower:
                budget.min_amount = amounts_found[0]
            elif 'maximum' in text_lower or 'plafond' in text_lower:
                budget.max_amount = amounts_found[0]
            else:
                # Single amount - could be estimated
                budget.max_amount = amounts_found[0]
        
        # Extract VAT information
        if 'ht' in text.lower() or 'hors taxe' in text.lower():
            budget.vat_included = False
        elif 'ttc' in text.lower() or 'toutes taxes' in text.lower():
            budget.vat_included = True
        
        # Extract budget type
        for btype, patterns in self.budget_types.items():
            if any(re.search(pattern, text.lower()) for pattern in patterns):
                budget.budget_type = btype
                break
        
        # Extract payment terms
        payment_patterns = [
            r'paiement[s]? à (\d+) jours',
            r'(\d+)% à la commande',
            r'acompte de (\d+)%'
        ]
        
        for pattern in payment_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                budget.payment_terms = match.group(0)
                break
        
        return budget if (budget.min_amount or budget.max_amount) else None
    
    def _parse_amount(self, amount_str: str, pattern: str) -> Optional[float]:
        """Parse amount string to float."""
        try:
            # Replace French decimal separator
            amount_str = amount_str.replace(',', '.')
            amount_str = amount_str.replace(' ', '')
            
            amount = float(amount_str)
            
            # Apply multipliers
            if 'million' in pattern or 'M€' in pattern:
                amount *= 1_000_000
            elif 'millier' in pattern or 'K€' in pattern:
                amount *= 1_000
            
            return amount
        except ValueError:
            logger.warning(f"Could not parse amount: {amount_str}")
            return None


class DeadlineExtractor(BaseExtractor):
    """
    Extracts deadlines and timeline information.
    """
    
    def __init__(self):
        self.months = {
            'janvier': 1, 'février': 2, 'mars': 3, 'avril': 4,
            'mai': 5, 'juin': 6, 'juillet': 7, 'août': 8,
            'septembre': 9, 'octobre': 10, 'novembre': 11, 'décembre': 12
        }
        
        self.deadline_types = {
            'submission': ['dépôt', 'soumission', 'remise', 'candidature'],
            'delivery': ['livraison', 'exécution', 'réalisation'],
            'milestone': ['étape', 'jalon', 'phase', 'tranche']
        }
        
    def extract(self, text: str, context: Optional[Dict[str, Any]] = None) -> List[Deadline]:
        """
        Extract deadlines from text.
        
        Args:
            text: Input text
            context: Optional context
            
        Returns:
            List of deadlines
        """
        deadlines = []
        
        # Pattern for dates
        date_patterns = [
            # DD/MM/YYYY or DD-MM-YYYY
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
            # DD month YYYY
            r'(\d{1,2})\s+(' + '|'.join(self.months.keys()) + r')\s+(\d{4})',
            # avant le DD/MM/YYYY
            r'avant le\s+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
            # au plus tard le
            r'au plus tard le\s+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
        ]
        
        for pattern in date_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                date = self._parse_date(match)
                if date:
                    # Determine deadline type
                    deadline_type = self._detect_deadline_type(text, match.start())
                    
                    # Extract description
                    description = self._extract_context(text, match.start(), match.end())
                    
                    # Check if strict
                    is_strict = self._is_strict_deadline(text, match.start())
                    
                    deadline = Deadline(
                        date=date,
                        description=description,
                        type=deadline_type,
                        is_strict=is_strict
                    )
                    deadlines.append(deadline)
        
        # Also look for relative deadlines
        relative_patterns = [
            r'dans\s+(\d+)\s+(jours?|semaines?|mois)',
            r'sous\s+(\d+)\s+(jours?|semaines?|mois)',
            r'délai de\s+(\d+)\s+(jours?|semaines?|mois)'
        ]
        
        for pattern in relative_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                date = self._parse_relative_date(match)
                if date:
                    description = self._extract_context(text, match.start(), match.end())
                    deadline = Deadline(
                        date=date,
                        description=description,
                        type='delivery',
                        is_strict=True
                    )
                    deadlines.append(deadline)
        
        return deadlines
    
    def _parse_date(self, match: re.Match) -> Optional[datetime]:
        """Parse date from regex match."""
        try:
            if len(match.groups()) == 1:
                # Simple date format DD/MM/YYYY
                date_str = match.group(1)
                for fmt in ['%d/%m/%Y', '%d-%m-%Y']:
                    try:
                        return datetime.strptime(date_str, fmt)
                    except ValueError:
                        continue
            elif len(match.groups()) == 3:
                # French date format
                day = int(match.group(1))
                month = self.months.get(match.group(2).lower())
                year = int(match.group(3))
                if month:
                    return datetime(year, month, day)
        except (ValueError, AttributeError):
            logger.warning(f"Could not parse date from match: {match.group(0)}")
        
        return None
    
    def _parse_relative_date(self, match: re.Match) -> Optional[datetime]:
        """Parse relative date to absolute date."""
        try:
            quantity = int(match.group(1))
            unit = match.group(2).lower()
            
            base_date = datetime.now()
            
            if 'jour' in unit:
                return base_date + timedelta(days=quantity)
            elif 'semaine' in unit:
                return base_date + timedelta(weeks=quantity)
            elif 'mois' in unit:
                # Approximate month as 30 days
                return base_date + timedelta(days=quantity * 30)
        except (ValueError, AttributeError):
            logger.warning(f"Could not parse relative date: {match.group(0)}")
        
        return None
    
    def _detect_deadline_type(self, text: str, position: int) -> str:
        """Detect type of deadline based on context."""
        # Get surrounding text (100 chars before and after)
        start = max(0, position - 100)
        end = min(len(text), position + 100)
        context_text = text[start:end].lower()
        
        for dtype, keywords in self.deadline_types.items():
            if any(keyword in context_text for keyword in keywords):
                return dtype
        
        return 'submission'  # Default
    
    def _extract_context(self, text: str, start: int, end: int, window: int = 50) -> str:
        """Extract context around a match."""
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        
        context = text[context_start:context_end].strip()
        
        # Clean up
        context = re.sub(r'\s+', ' ', context)
        
        # Truncate at sentence boundaries if possible
        if len(context) > 100:
            # Try to find sentence end
            sentence_end = context.find('.', 80)
            if sentence_end != -1:
                context = context[:sentence_end + 1]
        
        return context
    
    def _is_strict_deadline(self, text: str, position: int) -> bool:
        """Check if deadline is strict or flexible."""
        # Get surrounding text
        start = max(0, position - 50)
        end = min(len(text), position + 50)
        context = text[start:end].lower()
        
        strict_indicators = [
            'impératif', 'strict', 'sans délai', 'au plus tard',
            'dernier délai', 'limite', 'obligatoire'
        ]
        
        flexible_indicators = [
            'indicatif', 'approximatif', 'environ', 'souhaité',
            'préférence', 'idéalement'
        ]
        
        if any(indicator in context for indicator in strict_indicators):
            return True
        elif any(indicator in context for indicator in flexible_indicators):
            return False
        
        return True  # Default to strict


class EntityExtractor(BaseExtractor):
    """
    Extracts named entities relevant to procurement.
    """
    
    def __init__(self, nlp_model=None):
        self.nlp = nlp_model
        
        # Role patterns
        self.role_patterns = {
            'buyer': ['acheteur', 'pouvoir adjudicateur', 'maître d\'ouvrage'],
            'contact': ['contact', 'responsable', 'référent'],
            'supplier': ['fournisseur', 'prestataire', 'titulaire']
        }
        
    def extract(self, text: str, context: Optional[Dict[str, Any]] = None) -> List[Entity]:
        """
        Extract named entities from text.
        
        Args:
            text: Input text
            context: Optional context
            
        Returns:
            List of entities
        """
        entities = []
        
        if self.nlp:
            # Use spaCy NER
            doc = self.nlp(text)
            for ent in doc.ents:
                if ent.label_ in ['ORG', 'PER', 'LOC']:
                    entity = Entity(
                        name=ent.text,
                        type=self._map_spacy_type(ent.label_),
                        role=self._detect_role(text, ent.start_char),
                        metadata={
                            'start': ent.start_char,
                            'end': ent.end_char,
                            'spacy_label': ent.label_
                        }
                    )
                    entities.append(entity)
        else:
            # Fallback to pattern matching
            entities.extend(self._extract_by_patterns(text))
        
        return entities
    
    def _map_spacy_type(self, spacy_label: str) -> str:
        """Map spaCy entity type to our types."""
        mapping = {
            'ORG': 'organization',
            'PER': 'person',
            'LOC': 'location',
            'MISC': 'product'
        }
        return mapping.get(spacy_label, 'other')
    
    def _detect_role(self, text: str, position: int) -> Optional[str]:
        """Detect entity role based on context."""
        # Get surrounding text
        start = max(0, position - 100)
        end = min(len(text), position + 100)
        context = text[start:end].lower()
        
        for role, keywords in self.role_patterns.items():
            if any(keyword in context for keyword in keywords):
                return role
        
        return None
    
    def _extract_by_patterns(self, text: str) -> List[Entity]:
        """Fallback entity extraction using patterns."""
        entities = []
        
        # Common organization patterns
        org_patterns = [
            r'(?:SAS|SARL|SA|SCI|EURL)\s+[A-Z][A-Za-zà-ÿ\s&-]+',
            r'[A-Z][A-Za-zà-ÿ]+\s+(?:SAS|SARL|SA|SCI|EURL)',
            r'Ministère\s+[A-Za-zà-ÿ\s]+',
            r'Direction\s+[A-Za-zà-ÿ\s]+',
        ]
        
        for pattern in org_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                entity = Entity(
                    name=match.group(0).strip(),
                    type='organization',
                    role=self._detect_role(text, match.start()),
                    metadata={'pattern': pattern}
                )
                entities.append(entity)
        
        return entities


class ComprehensiveExtractor:
    """
    Combines all extractors for comprehensive document analysis.
    """
    
    def __init__(self, nlp_model=None):
        self.requirement_extractor = RequirementExtractor()
        self.budget_extractor = BudgetExtractor()
        self.deadline_extractor = DeadlineExtractor()
        self.entity_extractor = EntityExtractor(nlp_model)
    
    def extract_all(self, text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Extract all information from text.
        
        Args:
            text: Input text
            context: Optional context
            
        Returns:
            Dictionary with all extracted information
        """
        return {
            'requirements': self.requirement_extractor.extract(text, context),
            'budget': self.budget_extractor.extract(text, context),
            'deadlines': self.deadline_extractor.extract(text, context),
            'entities': self.entity_extractor.extract(text, context)
        }
    
    def extract_from_chunks(self, chunks: List[Any]) -> Dict[str, Any]:
        """
        Extract information from multiple chunks.
        
        Args:
            chunks: List of text chunks
            
        Returns:
            Aggregated extraction results
        """
        all_requirements = []
        all_deadlines = []
        all_entities = []
        budgets = []
        
        for chunk in chunks:
            # Extract from each chunk
            text = chunk.content if hasattr(chunk, 'content') else str(chunk)
            context = {'section_title': chunk.section_title} if hasattr(chunk, 'section_title') else None
            
            results = self.extract_all(text, context)
            
            all_requirements.extend(results['requirements'])
            all_deadlines.extend(results['deadlines'])
            all_entities.extend(results['entities'])
            
            if results['budget']:
                budgets.append(results['budget'])
        
        # Aggregate budgets (take the most comprehensive one)
        final_budget = None
        if budgets:
            # Prefer budget with both min and max
            for budget in budgets:
                if budget.min_amount and budget.max_amount:
                    final_budget = budget
                    break
            
            if not final_budget:
                final_budget = budgets[0]
        
        # Deduplicate entities
        unique_entities = []
        seen = set()
        for entity in all_entities:
            if entity.name not in seen:
                unique_entities.append(entity)
                seen.add(entity.name)
        
        return {
            'requirements': all_requirements,
            'budget': final_budget,
            'deadlines': all_deadlines,
            'entities': unique_entities,
            'summary': {
                'total_requirements': len(all_requirements),
                'requirements_by_category': self._count_by_category(all_requirements),
                'requirements_by_priority': self._count_by_priority(all_requirements),
                'total_deadlines': len(all_deadlines),
                'total_entities': len(unique_entities),
                'has_budget': final_budget is not None
            }
        }
    
    def _count_by_category(self, requirements: List[Requirement]) -> Dict[str, int]:
        """Count requirements by category."""
        counts = {}
        for req in requirements:
            counts[req.category] = counts.get(req.category, 0) + 1
        return counts
    
    def _count_by_priority(self, requirements: List[Requirement]) -> Dict[str, int]:
        """Count requirements by priority."""
        counts = {}
        for req in requirements:
            counts[req.priority] = counts.get(req.priority, 0) + 1
        return counts