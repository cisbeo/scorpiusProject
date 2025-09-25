"""French Named Entity Recognition and extraction service."""

import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class FrenchNERExtractor:
    """
    Service for extracting French-specific entities from procurement documents.
    
    Extracts:
    - SIRET numbers (14 digits)
    - French dates (various formats)
    - Monetary amounts (EUR)
    - Market reference numbers
    - Company names
    - Addresses
    - Deadlines
    - Contact information
    """
    
    def __init__(self):
        """Initialize the NER extractor."""
        self.spacy_available = self._check_spacy()
        self.nlp = None
        
        if self.spacy_available:
            self._initialize_spacy()
        
        # Initialize regex patterns for French entities
        self._compile_patterns()
        
    def _check_spacy(self) -> bool:
        """Check if spaCy and French model are available."""
        try:
            import spacy
            # Try to load French model
            try:
                nlp = spacy.load("fr_core_news_sm")
                return True
            except:
                logger.warning("French spaCy model not installed. Install with: python -m spacy download fr_core_news_sm")
                return False
        except ImportError:
            logger.warning("spaCy not installed. Install with: pip install spacy")
            return False
    
    def _initialize_spacy(self):
        """Initialize spaCy with French model and custom components."""
        import spacy
        from spacy.language import Language
        
        # Load French model
        self.nlp = spacy.load("fr_core_news_sm")
        
        # Add custom component for French entities
        @Language.component("french_entities")
        def extract_french_entities(doc):
            """Custom spaCy component for French entity extraction."""
            entities = []
            text = doc.text
            
            # Extract using compiled patterns
            for entity_type, pattern in self.patterns.items():
                for match in pattern.finditer(text):
                    entities.append({
                        "type": entity_type,
                        "text": match.group(),
                        "start": match.start(),
                        "end": match.end(),
                        "value": self._normalize_entity(entity_type, match)
                    })
            
            # Store in doc extension
            doc._.french_entities = entities
            return doc
        
        # Register extension
        from spacy.tokens import Doc
        if not Doc.has_extension("french_entities"):
            Doc.set_extension("french_entities", default=[])
        
        # Add component to pipeline
        if "french_entities" not in self.nlp.pipe_names:
            self.nlp.add_pipe("french_entities", after="ner")
    
    def _compile_patterns(self):
        """Compile regex patterns for French entity extraction."""
        self.patterns = {
            "SIRET": re.compile(r'\b\d{14}\b'),
            
            "SIREN": re.compile(r'\b\d{9}\b'),
            
            "DATE_FR": re.compile(
                r'\b(\d{1,2})\s*[/\-\.]\s*(\d{1,2})\s*[/\-\.]\s*(\d{2,4})\b|'
                r'\b(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+(\d{4})\b',
                re.IGNORECASE
            ),
            
            "MONTANT_EUR": re.compile(
                r'(\d{1,3}(?:\s?\d{3})*(?:[,.]\d{2})?)\s*(?:€|EUR|euros?)\b',
                re.IGNORECASE
            ),
            
            "MONTANT_HT": re.compile(
                r'(\d{1,3}(?:\s?\d{3})*(?:[,.]\d{2})?)\s*(?:€|EUR|euros?)\s*(?:HT|H\.T\.|hors taxes)',
                re.IGNORECASE
            ),
            
            "MONTANT_TTC": re.compile(
                r'(\d{1,3}(?:\s?\d{3})*(?:[,.]\d{2})?)\s*(?:€|EUR|euros?)\s*(?:TTC|T\.T\.C\.|toutes taxes comprises)',
                re.IGNORECASE
            ),
            
            "NUMERO_MARCHE": re.compile(
                r'(?:n°|N°|numéro|NUMERO|num\.|NUM\.)\s*(?:de marché\s*:?\s*)?([A-Z0-9\-\/]+)\b',
                re.IGNORECASE
            ),
            
            "CODE_CPV": re.compile(r'\b(\d{8})(?:-\d)?\b'),  # CPV codes format
            
            "CODE_POSTAL": re.compile(r'\b(\d{5})\b'),
            
            "TELEPHONE": re.compile(
                r'(?:(?:\+|00)33\s*[\s.-]?|0)[1-9](?:[\s.-]?\d{2}){4}\b'
            ),
            
            "EMAIL": re.compile(
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            ),
            
            "DEADLINE": re.compile(
                r'(?:date limite|délai|avant le|au plus tard le|jusqu\'au)\s*:?\s*'
                r'(\d{1,2}[\s\/\-\.]\d{1,2}[\s\/\-\.]\d{2,4}|'
                r'\d{1,2}\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4})',
                re.IGNORECASE
            ),
            
            "POURCENTAGE": re.compile(r'\b(\d{1,3}(?:[,.]\d{1,2})?)\s*%'),
            
            "DUREE": re.compile(
                r'(\d+)\s*(?:jours?|semaines?|mois|années?|ans?)\b',
                re.IGNORECASE
            )
        }
        
        # Month mapping for date normalization
        self.months_fr = {
            'janvier': '01', 'février': '02', 'mars': '03',
            'avril': '04', 'mai': '05', 'juin': '06',
            'juillet': '07', 'août': '08', 'septembre': '09',
            'octobre': '10', 'novembre': '11', 'décembre': '12'
        }
    
    def extract_entities(self, text: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract all entities from French text.
        
        Args:
            text: Input text to analyze
            
        Returns:
            Dictionary of entities grouped by type
        """
        entities = {
            "siret": [],
            "siren": [],
            "dates": [],
            "montants": [],
            "marches": [],
            "contacts": [],
            "deadlines": [],
            "durations": [],
            "percentages": [],
            "organizations": [],
            "locations": []
        }
        
        # Extract using regex patterns
        for entity_type, pattern in self.patterns.items():
            for match in pattern.finditer(text):
                entity_data = self._create_entity_data(entity_type, match, text)
                
                # Categorize entity
                if entity_type == "SIRET":
                    entities["siret"].append(entity_data)
                elif entity_type == "SIREN":
                    entities["siren"].append(entity_data)
                elif entity_type in ["DATE_FR", "DEADLINE"]:
                    entities["dates"].append(entity_data)
                    if entity_type == "DEADLINE":
                        entities["deadlines"].append(entity_data)
                elif entity_type in ["MONTANT_EUR", "MONTANT_HT", "MONTANT_TTC"]:
                    entities["montants"].append(entity_data)
                elif entity_type == "NUMERO_MARCHE":
                    entities["marches"].append(entity_data)
                elif entity_type in ["TELEPHONE", "EMAIL"]:
                    entities["contacts"].append(entity_data)
                elif entity_type == "DUREE":
                    entities["durations"].append(entity_data)
                elif entity_type == "POURCENTAGE":
                    entities["percentages"].append(entity_data)
        
        # Use spaCy if available for organizations and locations
        if self.spacy_available and self.nlp:
            doc = self.nlp(text)
            
            # Extract spaCy entities
            for ent in doc.ents:
                if ent.label_ in ["ORG", "COMPANY"]:
                    entities["organizations"].append({
                        "text": ent.text,
                        "type": "ORGANIZATION",
                        "start": ent.start_char,
                        "end": ent.end_char,
                        "label": ent.label_
                    })
                elif ent.label_ in ["LOC", "GPE"]:
                    entities["locations"].append({
                        "text": ent.text,
                        "type": "LOCATION",
                        "start": ent.start_char,
                        "end": ent.end_char,
                        "label": ent.label_
                    })
            
            # Get custom French entities
            if hasattr(doc, "_") and hasattr(doc._, "french_entities"):
                for entity in doc._.french_entities:
                    # Add to appropriate category if not already there
                    pass  # Already handled by regex
        
        # Remove duplicates
        for key in entities:
            entities[key] = self._remove_duplicate_entities(entities[key])
        
        return entities
    
    def _create_entity_data(
        self,
        entity_type: str,
        match: re.Match,
        text: str
    ) -> Dict[str, Any]:
        """
        Create entity data dictionary from regex match.
        
        Args:
            entity_type: Type of entity
            match: Regex match object
            text: Original text
            
        Returns:
            Entity data dictionary
        """
        entity = {
            "type": entity_type,
            "text": match.group(),
            "start": match.start(),
            "end": match.end(),
            "context": self._get_context(text, match.start(), match.end())
        }
        
        # Normalize and add value
        normalized = self._normalize_entity(entity_type, match)
        if normalized:
            entity["value"] = normalized
        
        return entity
    
    def _normalize_entity(self, entity_type: str, match: re.Match) -> Any:
        """
        Normalize entity value based on type.
        
        Args:
            entity_type: Type of entity
            match: Regex match object
            
        Returns:
            Normalized value
        """
        try:
            if entity_type in ["SIRET", "SIREN"]:
                # Remove spaces and validate
                value = re.sub(r'\s+', '', match.group())
                if entity_type == "SIRET" and len(value) == 14:
                    return value
                elif entity_type == "SIREN" and len(value) == 9:
                    return value
            
            elif entity_type == "DATE_FR" or entity_type == "DEADLINE":
                return self._normalize_french_date(match.group())
            
            elif entity_type in ["MONTANT_EUR", "MONTANT_HT", "MONTANT_TTC"]:
                # Extract amount and convert to float
                amount_str = match.group(1) if match.groups() else match.group()
                amount_str = amount_str.replace(' ', '').replace(',', '.')
                return {
                    "amount": float(amount_str),
                    "currency": "EUR",
                    "tax_status": "HT" if "HT" in entity_type else "TTC" if "TTC" in entity_type else "UNKNOWN"
                }
            
            elif entity_type == "NUMERO_MARCHE":
                # Extract market number
                if match.groups():
                    return match.group(1).strip()
                return match.group().strip()
            
            elif entity_type == "POURCENTAGE":
                # Convert percentage to float
                pct_str = match.group(1) if match.groups() else match.group()
                pct_str = pct_str.replace(',', '.')
                return float(pct_str)
            
            elif entity_type == "DUREE":
                # Extract duration value and unit
                if match.groups():
                    return {
                        "value": int(match.group(1)),
                        "unit": self._normalize_duration_unit(match.group())
                    }
            
            elif entity_type == "TELEPHONE":
                # Normalize phone number
                phone = re.sub(r'[^0-9+]', '', match.group())
                return phone
            
            elif entity_type == "EMAIL":
                return match.group().lower()
            
        except Exception as e:
            logger.warning(f"Error normalizing {entity_type}: {e}")
        
        return match.group()
    
    def _normalize_french_date(self, date_str: str) -> Optional[str]:
        """
        Normalize French date to ISO format.
        
        Args:
            date_str: Date string in French format
            
        Returns:
            ISO date string (YYYY-MM-DD) or None
        """
        try:
            # Try numeric format (DD/MM/YYYY or similar)
            numeric_match = re.match(
                r'(\d{1,2})[\s\/\-\.](\d{1,2})[\s\/\-\.](\d{2,4})',
                date_str
            )
            if numeric_match:
                day, month, year = numeric_match.groups()
                if len(year) == 2:
                    year = "20" + year if int(year) < 50 else "19" + year
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            
            # Try text format (DD month YYYY)
            text_match = re.match(
                r'(\d{1,2})\s+(\w+)\s+(\d{4})',
                date_str,
                re.IGNORECASE
            )
            if text_match:
                day, month_name, year = text_match.groups()
                month = self.months_fr.get(month_name.lower())
                if month:
                    return f"{year}-{month}-{day.zfill(2)}"
            
        except Exception as e:
            logger.warning(f"Error normalizing date {date_str}: {e}")
        
        return None
    
    def _normalize_duration_unit(self, duration_str: str) -> str:
        """
        Normalize duration unit to standard form.
        
        Args:
            duration_str: Duration string
            
        Returns:
            Standard unit (days, weeks, months, years)
        """
        duration_lower = duration_str.lower()
        
        if "jour" in duration_lower:
            return "days"
        elif "semaine" in duration_lower:
            return "weeks"
        elif "mois" in duration_lower:
            return "months"
        elif "an" in duration_lower or "année" in duration_lower:
            return "years"
        
        return "unknown"
    
    def _get_context(self, text: str, start: int, end: int, window: int = 50) -> str:
        """
        Get context around an entity.
        
        Args:
            text: Full text
            start: Entity start position
            end: Entity end position
            window: Context window size
            
        Returns:
            Context string
        """
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        
        context = text[context_start:context_end]
        
        # Add ellipsis if truncated
        if context_start > 0:
            context = "..." + context
        if context_end < len(text):
            context = context + "..."
        
        return context
    
    def _remove_duplicate_entities(self, entities: List[Dict]) -> List[Dict]:
        """
        Remove duplicate entities based on text and position.
        
        Args:
            entities: List of entity dictionaries
            
        Returns:
            Deduplicated list
        """
        seen = set()
        unique = []
        
        for entity in entities:
            # Create unique key
            key = (entity.get("text"), entity.get("start"), entity.get("end"))
            if key not in seen:
                seen.add(key)
                unique.append(entity)
        
        return unique
    
    def extract_procurement_specific(
        self,
        text: str
    ) -> Dict[str, Any]:
        """
        Extract procurement-specific information.
        
        Args:
            text: Document text
            
        Returns:
            Procurement-specific entities
        """
        procurement = {
            "buyer": None,
            "market_reference": None,
            "cpv_codes": [],
            "submission_deadline": None,
            "estimated_value": None,
            "duration": None,
            "lots": [],
            "criteria": [],
            "contact": {}
        }
        
        # Extract all entities
        entities = self.extract_entities(text)
        
        # Market reference
        if entities["marches"]:
            procurement["market_reference"] = entities["marches"][0].get("value")
        
        # Deadlines
        if entities["deadlines"]:
            procurement["submission_deadline"] = entities["deadlines"][0].get("value")
        
        # Amounts
        if entities["montants"]:
            # Look for estimated value keywords
            for montant in entities["montants"]:
                context = montant.get("context", "").lower()
                if any(keyword in context for keyword in ["estimé", "prévisionnel", "maximum"]):
                    procurement["estimated_value"] = montant.get("value")
                    break
            
            # If no estimated value found, use first amount
            if not procurement["estimated_value"] and entities["montants"]:
                procurement["estimated_value"] = entities["montants"][0].get("value")
        
        # Duration
        if entities["durations"]:
            procurement["duration"] = entities["durations"][0].get("value")
        
        # Contact information
        for contact in entities["contacts"]:
            if contact["type"] == "EMAIL":
                procurement["contact"]["email"] = contact.get("value")
            elif contact["type"] == "TELEPHONE":
                procurement["contact"]["phone"] = contact.get("value")
        
        # Organizations (first one is likely the buyer)
        if entities["organizations"]:
            procurement["buyer"] = entities["organizations"][0].get("text")
        
        # Extract lots if mentioned
        lot_pattern = re.compile(
            r'(?:lot|LOT)\s*(?:n°|N°|numéro)?\s*(\d+)\s*:?\s*([^\n]+)',
            re.IGNORECASE
        )
        for match in lot_pattern.finditer(text):
            procurement["lots"].append({
                "number": match.group(1),
                "title": match.group(2).strip()
            })
        
        # Extract evaluation criteria with percentages
        criteria_pattern = re.compile(
            r'([^:]+)\s*:\s*(\d{1,3}\s*%)',
            re.IGNORECASE
        )
        for match in criteria_pattern.finditer(text):
            criterion = match.group(1).strip()
            # Filter out noise
            if len(criterion) < 100 and len(criterion) > 5:
                procurement["criteria"].append({
                    "name": criterion,
                    "weight": match.group(2)
                })
        
        return procurement
