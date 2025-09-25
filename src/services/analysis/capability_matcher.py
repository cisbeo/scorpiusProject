"""Capability matching engine for requirements and company capabilities."""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
import numpy as np
from datetime import datetime


class GapType(Enum):
    """Types of gaps between requirements and capabilities."""
    CAPABILITY_MISSING = "capability_missing"
    PARTIAL_MATCH = "partial_match"
    EXPERIENCE_INSUFFICIENT = "experience_insufficient"
    CERTIFICATION_MISSING = "certification_missing"
    TECHNOLOGY_MISMATCH = "technology_mismatch"
    CAPACITY_INSUFFICIENT = "capacity_insufficient"


@dataclass
class GapAnalysis:
    """Analysis of gap between requirement and capability."""
    has_gap: bool
    gap_type: Optional[GapType]
    remediation_needed: bool
    estimated_effort: str  # "none", "low", "medium", "high", "critical"
    missing_elements: List[str]
    recommendations: List[str]
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "has_gap": self.has_gap,
            "gap_type": self.gap_type.value if self.gap_type else None,
            "remediation_needed": self.remediation_needed,
            "estimated_effort": self.estimated_effort,
            "missing_elements": self.missing_elements,
            "recommendations": self.recommendations,
            "confidence": self.confidence
        }


@dataclass
class MatchResult:
    """Result of matching a requirement to capabilities."""
    requirement: Any  # ExtractedRequirement
    matched_capability: Optional[Dict[str, Any]]
    confidence_score: float
    gap_analysis: GapAnalysis
    match_type: str  # "exact", "partial", "no_match"
    keywords_matched: List[str]
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "requirement": self.requirement.to_dict() if hasattr(self.requirement, 'to_dict') else str(self.requirement),
            "matched_capability": self.matched_capability,
            "confidence_score": self.confidence_score,
            "gap_analysis": self.gap_analysis.to_dict(),
            "match_type": self.match_type,
            "keywords_matched": self.keywords_matched,
            "metadata": self.metadata
        }


class CapabilityMatcher:
    """Engine for matching requirements to company capabilities."""

    def __init__(self):
        """Initialize the capability matcher."""
        self.vectorizer = None
        self.similarity_threshold = 0.3
        self.exact_match_threshold = 0.8
        self.partial_match_threshold = 0.5
        self._initialize_vectorizer()

    def _initialize_vectorizer(self):
        """Initialize TF-IDF vectorizer for text similarity."""
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            self.vectorizer = TfidfVectorizer(
                analyzer='word',
                ngram_range=(1, 3),
                max_features=1000,
                lowercase=True,
                strip_accents='unicode'
            )
            self.vectorizer_available = True
        except ImportError:
            self.vectorizer_available = False
            self.vectorizer = None

    async def match_requirements_to_capabilities(
        self,
        requirements: List[Any],  # List[ExtractedRequirement]
        company_profile: Dict[str, Any]
    ) -> List[MatchResult]:
        """
        Match requirements to company capabilities.

        Args:
            requirements: List of extracted requirements
            company_profile: Company profile with capabilities

        Returns:
            List of match results with gap analysis
        """
        matches = []
        capabilities = company_profile.get('capabilities', [])
        certifications = company_profile.get('certifications', [])
        references = company_profile.get('references', [])

        for req in requirements:
            # Find best matching capability
            best_match = await self._find_best_capability_match(
                req, capabilities, certifications
            )

            # Analyze gap
            gap_analysis = self._analyze_gap(
                req, best_match, capabilities, certifications, references
            )

            # Determine match type
            match_type = self._determine_match_type(best_match)

            # Create match result
            match_result = MatchResult(
                requirement=req,
                matched_capability=best_match[0] if best_match else None,
                confidence_score=best_match[1] if best_match else 0.0,
                gap_analysis=gap_analysis,
                match_type=match_type,
                keywords_matched=self._extract_matched_keywords(req, best_match[0]) if best_match else []
            )

            matches.append(match_result)

        return matches

    async def _find_best_capability_match(
        self,
        requirement: Any,
        capabilities: List[Dict[str, Any]],
        certifications: List[Dict[str, Any]]
    ) -> Optional[Tuple[Dict, float]]:
        """
        Find the best matching capability for a requirement.

        Args:
            requirement: Requirement to match
            capabilities: List of company capabilities
            certifications: List of company certifications

        Returns:
            Tuple of (best_capability, confidence_score) or None
        """
        if not capabilities:
            return None

        # Create requirement text for matching
        req_text = self._create_requirement_text(requirement)

        # Score each capability
        capability_scores = []

        for cap in capabilities:
            # Create capability text
            cap_text = self._create_capability_text(cap)

            # Calculate similarity score
            if self.vectorizer_available:
                similarity = self._calculate_similarity(req_text, cap_text)
            else:
                similarity = self._calculate_simple_similarity(req_text, cap_text)

            # Boost score for keyword matches
            keyword_boost = self._calculate_keyword_boost(requirement, cap)

            # Boost score for certification matches
            cert_boost = self._calculate_certification_boost(requirement, certifications)

            # Combined score
            total_score = (similarity * 0.6) + (keyword_boost * 0.3) + (cert_boost * 0.1)

            capability_scores.append((cap, total_score))

        # Sort by score and get best match
        capability_scores.sort(key=lambda x: x[1], reverse=True)

        if capability_scores and capability_scores[0][1] > self.similarity_threshold:
            return capability_scores[0]

        return None

    def _create_requirement_text(self, requirement: Any) -> str:
        """
        Create text representation of requirement for matching.

        Args:
            requirement: Requirement object

        Returns:
            Text representation
        """
        parts = []

        if hasattr(requirement, 'description'):
            parts.append(requirement.description)

        if hasattr(requirement, 'keywords'):
            parts.extend(requirement.keywords)

        if hasattr(requirement, 'category'):
            parts.append(str(requirement.category.value if hasattr(requirement.category, 'value') else requirement.category))

        return ' '.join(parts)

    def _create_capability_text(self, capability: Dict[str, Any]) -> str:
        """
        Create text representation of capability for matching.

        Args:
            capability: Capability dictionary

        Returns:
            Text representation
        """
        parts = []

        if 'domain' in capability:
            parts.append(capability['domain'])

        if 'technologies' in capability:
            parts.extend(capability['technologies'])

        if 'description' in capability:
            parts.append(capability['description'])

        return ' '.join(parts)

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate TF-IDF similarity between two texts.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score between 0 and 1
        """
        if not self.vectorizer_available or not text1 or not text2:
            return 0.0

        try:
            from sklearn.metrics.pairwise import cosine_similarity

            # Fit and transform texts
            tfidf_matrix = self.vectorizer.fit_transform([text1, text2])

            # Calculate cosine similarity
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]

            return float(similarity)

        except Exception:
            return self._calculate_simple_similarity(text1, text2)

    def _calculate_simple_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate simple word-based similarity.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score between 0 and 1
        """
        if not text1 or not text2:
            return 0.0

        # Tokenize and normalize
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        # Calculate Jaccard similarity
        intersection = words1.intersection(words2)
        union = words1.union(words2)

        if not union:
            return 0.0

        return len(intersection) / len(union)

    def _calculate_keyword_boost(self, requirement: Any, capability: Dict[str, Any]) -> float:
        """
        Calculate boost score based on keyword matches.

        Args:
            requirement: Requirement object
            capability: Capability dictionary

        Returns:
            Boost score between 0 and 1
        """
        score = 0.0

        if hasattr(requirement, 'keywords'):
            req_keywords = [k.lower() for k in requirement.keywords]
        else:
            return 0.0

        cap_technologies = [t.lower() for t in capability.get('technologies', [])]
        cap_domain = capability.get('domain', '').lower()

        # Check technology matches
        tech_matches = sum(1 for k in req_keywords if any(t in k or k in t for t in cap_technologies))

        # Check domain matches
        domain_matches = sum(1 for k in req_keywords if k in cap_domain or cap_domain in k)

        if req_keywords:
            score = (tech_matches + domain_matches) / (len(req_keywords) * 2)

        return min(score, 1.0)

    def _calculate_certification_boost(
        self,
        requirement: Any,
        certifications: List[Dict[str, Any]]
    ) -> float:
        """
        Calculate boost score based on certification matches.

        Args:
            requirement: Requirement object
            certifications: List of certifications

        Returns:
            Boost score between 0 and 1
        """
        if not certifications:
            return 0.0

        cert_names = [c.get('name', '').lower() for c in certifications]
        req_text = self._create_requirement_text(requirement).lower()

        # Check for certification mentions
        cert_keywords = ['iso', 'certification', 'certificat', 'norme', 'label', 'agrément']

        has_cert_requirement = any(keyword in req_text for keyword in cert_keywords)

        if not has_cert_requirement:
            return 0.0

        # Check specific certification matches
        matches = 0
        for cert_name in cert_names:
            if cert_name in req_text:
                matches += 1

        return min(matches * 0.5, 1.0)

    def _analyze_gap(
        self,
        requirement: Any,
        match: Optional[Tuple[Dict, float]],
        capabilities: List[Dict[str, Any]],
        certifications: List[Dict[str, Any]],
        references: List[Dict[str, Any]]
    ) -> GapAnalysis:
        """
        Analyze gap between requirement and capabilities.

        Args:
            requirement: Requirement object
            match: Best match found
            capabilities: All company capabilities
            certifications: Company certifications
            references: Company references

        Returns:
            Gap analysis result
        """
        # No match found - capability completely missing
        if not match or match[1] < self.similarity_threshold:
            return self._create_missing_capability_gap(requirement)

        confidence = match[1]
        capability = match[0]

        # Exact match - no gap
        if confidence >= self.exact_match_threshold:
            return GapAnalysis(
                has_gap=False,
                gap_type=None,
                remediation_needed=False,
                estimated_effort="none",
                missing_elements=[],
                recommendations=[],
                confidence=confidence
            )

        # Partial match - analyze specific gaps
        if confidence >= self.partial_match_threshold:
            return self._analyze_partial_match_gap(requirement, capability, confidence)

        # Weak match - significant gap
        return self._analyze_weak_match_gap(requirement, capability, confidence)

    def _create_missing_capability_gap(self, requirement: Any) -> GapAnalysis:
        """
        Create gap analysis for missing capability.

        Args:
            requirement: Requirement object

        Returns:
            Gap analysis for missing capability
        """
        missing_elements = []
        recommendations = []

        if hasattr(requirement, 'keywords'):
            missing_elements.extend(requirement.keywords[:5])

        if hasattr(requirement, 'category'):
            category = str(requirement.category.value if hasattr(requirement.category, 'value') else requirement.category)
            recommendations.append(f"Développer une capacité en {category}")

        if hasattr(requirement, 'priority'):
            priority = str(requirement.priority.value if hasattr(requirement.priority, 'value') else requirement.priority)
            if priority in ['obligatoire', 'éliminatoire']:
                recommendations.append("Considérer un partenariat ou sous-traitance")

        return GapAnalysis(
            has_gap=True,
            gap_type=GapType.CAPABILITY_MISSING,
            remediation_needed=True,
            estimated_effort="high",
            missing_elements=missing_elements,
            recommendations=recommendations,
            confidence=0.0
        )

    def _analyze_partial_match_gap(
        self,
        requirement: Any,
        capability: Dict[str, Any],
        confidence: float
    ) -> GapAnalysis:
        """
        Analyze gap for partial match.

        Args:
            requirement: Requirement object
            capability: Matched capability
            confidence: Match confidence

        Returns:
            Gap analysis for partial match
        """
        missing_elements = []
        recommendations = []

        # Check for missing technologies
        if hasattr(requirement, 'keywords'):
            req_keywords = [k.lower() for k in requirement.keywords]
            cap_technologies = [t.lower() for t in capability.get('technologies', [])]

            missing_tech = [k for k in req_keywords if not any(t in k or k in t for t in cap_technologies)]
            if missing_tech:
                missing_elements.extend(missing_tech[:3])
                recommendations.append(f"Ajouter les technologies: {', '.join(missing_tech[:3])}")

        # Check experience level
        if 'experience_years' in capability:
            exp_years = capability['experience_years']
            if exp_years < 3:
                recommendations.append("Renforcer l'expérience dans ce domaine")

        return GapAnalysis(
            has_gap=True,
            gap_type=GapType.PARTIAL_MATCH,
            remediation_needed=True,
            estimated_effort="medium",
            missing_elements=missing_elements,
            recommendations=recommendations,
            confidence=confidence
        )

    def _analyze_weak_match_gap(
        self,
        requirement: Any,
        capability: Dict[str, Any],
        confidence: float
    ) -> GapAnalysis:
        """
        Analyze gap for weak match.

        Args:
            requirement: Requirement object
            capability: Matched capability
            confidence: Match confidence

        Returns:
            Gap analysis for weak match
        """
        return GapAnalysis(
            has_gap=True,
            gap_type=GapType.TECHNOLOGY_MISMATCH,
            remediation_needed=True,
            estimated_effort="high",
            missing_elements=["Alignement technologique insuffisant"],
            recommendations=[
                "Évaluer la faisabilité d'adaptation",
                "Considérer une formation ou recrutement",
                "Explorer des partenariats stratégiques"
            ],
            confidence=confidence
        )

    def _determine_match_type(self, match: Optional[Tuple[Dict, float]]) -> str:
        """
        Determine the type of match.

        Args:
            match: Match result

        Returns:
            Match type string
        """
        if not match:
            return "no_match"

        confidence = match[1]

        if confidence >= self.exact_match_threshold:
            return "exact"
        elif confidence >= self.partial_match_threshold:
            return "partial"
        else:
            return "no_match"

    def _extract_matched_keywords(
        self,
        requirement: Any,
        capability: Optional[Dict[str, Any]]
    ) -> List[str]:
        """
        Extract keywords that matched between requirement and capability.

        Args:
            requirement: Requirement object
            capability: Capability dictionary

        Returns:
            List of matched keywords
        """
        if not capability:
            return []

        matched = []

        req_text = self._create_requirement_text(requirement).lower()
        cap_text = self._create_capability_text(capability).lower()

        # Find common words
        req_words = set(req_text.split())
        cap_words = set(cap_text.split())

        common_words = req_words.intersection(cap_words)

        # Filter out common French words
        stop_words = {'le', 'la', 'les', 'de', 'du', 'des', 'un', 'une', 'et', 'ou', 'dans', 'pour', 'avec'}
        matched = [w for w in common_words if w not in stop_words and len(w) > 2]

        return list(matched)[:10]

    async def calculate_overall_matching_score(
        self,
        match_results: List[MatchResult]
    ) -> Dict[str, Any]:
        """
        Calculate overall matching score for all requirements.

        Args:
            match_results: List of individual match results

        Returns:
            Dictionary with overall scores and statistics
        """
        if not match_results:
            return {
                "overall_score": 0.0,
                "capability_coverage": 0.0,
                "critical_gaps": 0,
                "recommendations": []
            }

        # Calculate statistics
        total_requirements = len(match_results)
        exact_matches = sum(1 for m in match_results if m.match_type == "exact")
        partial_matches = sum(1 for m in match_results if m.match_type == "partial")
        no_matches = sum(1 for m in match_results if m.match_type == "no_match")

        # Calculate weighted scores
        mandatory_requirements = [m for m in match_results if hasattr(m.requirement, 'priority') and
                                 str(m.requirement.priority.value if hasattr(m.requirement.priority, 'value') else m.requirement.priority) == 'obligatoire']

        mandatory_score = 0.0
        if mandatory_requirements:
            mandatory_score = sum(m.confidence_score for m in mandatory_requirements) / len(mandatory_requirements)

        # Overall score calculation
        overall_score = (exact_matches * 1.0 + partial_matches * 0.5) / total_requirements

        # Capability coverage
        capability_coverage = (exact_matches + partial_matches) / total_requirements

        # Critical gaps
        critical_gaps = sum(1 for m in match_results if m.gap_analysis.has_gap and
                          m.gap_analysis.estimated_effort in ["high", "critical"])

        # Aggregate recommendations
        all_recommendations = []
        for m in match_results:
            if m.gap_analysis.recommendations:
                all_recommendations.extend(m.gap_analysis.recommendations)

        # Deduplicate recommendations
        unique_recommendations = list(set(all_recommendations))[:5]

        return {
            "overall_score": round(overall_score, 2),
            "capability_coverage": round(capability_coverage, 2),
            "mandatory_compliance": round(mandatory_score, 2),
            "exact_matches": exact_matches,
            "partial_matches": partial_matches,
            "no_matches": no_matches,
            "critical_gaps": critical_gaps,
            "total_requirements": total_requirements,
            "recommendations": unique_recommendations
        }