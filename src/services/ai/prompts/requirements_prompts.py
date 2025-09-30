"""Templates de prompts spécialisés pour l'extraction de requirements."""

from typing import Dict, Optional, Tuple, List
from src.models.document_type import DocumentType


class RequirementsPromptBuilder:
    """Constructeur de prompts pour l'extraction de requirements avec Mistral AI."""

    BASE_SYSTEM_PROMPT = """Tu es un expert en marchés publics français spécialisé dans l'analyse de documents d'appels d'offres.
Ta tâche est d'extraire TOUS les requirements (exigences) du document de manière structurée.

Pour chaque requirement identifié, tu dois fournir :
- category : technical, administrative, financial, legal, functional ou performance
- description : description claire et concise de l'exigence (10-500 caractères)
- importance : critical, high, medium ou low
- is_mandatory : true si obligatoire, false si optionnel
- confidence : score de confiance de 0.0 à 1.0
- source_text : extrait exact du texte source (max 1000 caractères)
- keywords : mots-clés pertinents

RÈGLES D'EXTRACTION :
1. Les mots "doit", "devra", "obligatoire", "impératif", "nécessaire", "exigé" indiquent une exigence obligatoire
2. Les mots "peut", "pourra", "souhaitable", "recommandé", "optionnel" indiquent une exigence optionnelle
3. Les mots "éliminatoire", "critère d'exclusion", "sous peine de rejet" indiquent une importance critical
4. Identifie les exigences explicites ET implicites
5. Sois exhaustif mais évite les doublons
6. Groupe les exigences similaires quand c'est pertinent
7. Retourne UNIQUEMENT du JSON valide, sans markdown ni commentaires

IMPORTANT : Focus sur les éléments actionnables et vérifiables. Ignore les descriptions générales qui ne sont pas des requirements."""

    DOCUMENT_SPECIFIC_PROMPTS = {
        DocumentType.CCTP: """
Focus PRIORITAIRE sur les aspects techniques :
- Spécifications techniques détaillées (technologies, frameworks, langages)
- Performances attendues (temps de réponse, charge, disponibilité)
- Normes et standards à respecter (ISO, RGPD, RGS, etc.)
- Livrables techniques et leur format
- Contraintes d'architecture et d'infrastructure
- Interfaces et intégrations avec systèmes existants
- Environnements (dev, test, prod)
- Sécurité et authentification
- Volumétrie et montée en charge
- Maintenance et évolutivité

Mots-clés à rechercher : "architecture", "performance", "interface", "API", "base de données",
"sécurité", "authentification", "infrastructure", "hébergement", "sauvegarde", "monitoring"
""",

        DocumentType.CCAP: """
Focus PRIORITAIRE sur les aspects administratifs et contractuels :
- Clauses de paiement et modalités
- Pénalités de retard et conditions d'application
- Garanties exigées (technique, financière)
- Responsabilités et obligations contractuelles
- Conditions de résiliation et litiges
- Propriété intellectuelle et droits d'usage
- Assurances requises
- Clauses de confidentialité
- Transfert de compétences
- Réversibilité

Mots-clés à rechercher : "pénalité", "garantie", "paiement", "facture", "délai", "résiliation",
"responsabilité", "assurance", "propriété", "confidentialité", "litige", "réversibilité"
""",

        DocumentType.RC: """
Focus PRIORITAIRE sur les critères de sélection et documents administratifs :
- Documents obligatoires à fournir (Kbis, attestations, certificats)
- Critères d'évaluation et leur pondération
- Références clients requises (nombre, secteur, montant)
- Qualifications professionnelles et certifications
- Capacités financières minimales (CA, ratios)
- Moyens humains et techniques
- Dates limites et modalités de soumission
- Format de réponse attendu
- Langue de la réponse
- Nombre d'exemplaires

Mots-clés à rechercher : "candidature", "dossier", "pièce", "justificatif", "attestation",
"référence", "chiffre d'affaires", "effectif", "qualification", "date limite", "cachet"
""",

        DocumentType.BPU: """
Focus PRIORITAIRE sur les aspects financiers et tarifaires :
- Structure de prix (forfait, régie, unité d'œuvre)
- Unités de facturation et leur définition
- Conditions de révision des prix
- Modalités de paiement et échéances
- Rabais, remises et ristournes
- Prix plafond ou budget maximum
- Décomposition du prix global
- Variantes autorisées
- Options et prestations supplémentaires
- Devise et TVA

Mots-clés à rechercher : "prix", "tarif", "coût", "forfait", "régie", "unité", "révision",
"rabais", "remise", "option", "variante", "budget", "plafond", "HT", "TTC"
"""
    }

    # Template pour documents non reconnus
    DEFAULT_PROMPT = """
Analyse générale du document :
- Identifie toutes les obligations et exigences
- Distingue les éléments obligatoires des optionnels
- Extrais les critères d'évaluation
- Repère les contraintes techniques et administratives
- Note les délais et dates importantes
"""

    @classmethod
    def build_extraction_prompt(
        cls,
        document_text: str,
        document_type: Optional[DocumentType] = None,
        max_text_length: int = 12000,
        focus_sections: Optional[List[str]] = None
    ) -> Tuple[str, str]:
        """
        Construit les prompts système et utilisateur pour l'extraction.

        Args:
            document_text: Texte du document à analyser
            document_type: Type de document (CCTP, CCAP, etc.)
            max_text_length: Longueur maximale du texte (pour éviter token overflow)
            focus_sections: Sections spécifiques sur lesquelles se concentrer

        Returns:
            Tuple (system_prompt, user_prompt)
        """
        # Tronquer le texte si trop long
        truncated = False
        if len(document_text) > max_text_length:
            document_text = document_text[:max_text_length]
            truncated = True

        # Construire le prompt système
        system_prompt = cls.BASE_SYSTEM_PROMPT

        if document_type and document_type in cls.DOCUMENT_SPECIFIC_PROMPTS:
            system_prompt += f"\n\nPour ce document de type {document_type.value.upper()} :"
            system_prompt += cls.DOCUMENT_SPECIFIC_PROMPTS[document_type]
        else:
            system_prompt += f"\n\nDocument de type non spécifié :"
            system_prompt += cls.DEFAULT_PROMPT

        # Ajouter les sections focus si spécifiées
        if focus_sections:
            system_prompt += f"\n\nConcentre-toi particulièrement sur les sections : {', '.join(focus_sections)}"

        # Construire le prompt utilisateur
        user_prompt = f"""Analyse le document suivant et extrais TOUS les requirements au format JSON.

DOCUMENT À ANALYSER :
=====================================
{document_text}
{"[... document tronqué pour l'analyse ...]" if truncated else ""}
=====================================

INSTRUCTIONS :
1. Extrais TOUS les requirements trouvés dans le document
2. Assure-toi de ne pas manquer d'exigences importantes
3. Pour chaque requirement, fournis toutes les informations demandées
4. Retourne UNIQUEMENT le JSON, sans texte avant ou après
5. Le JSON doit être valide et correctement formaté

FORMAT DE RÉPONSE ATTENDU :
{{
    "requirements": [
        {{
            "category": "technical|administrative|financial|legal|functional|performance",
            "description": "Description claire et concise de l'exigence",
            "importance": "critical|high|medium|low",
            "is_mandatory": true|false,
            "confidence": 0.0-1.0,
            "source_text": "Extrait exact du texte source",
            "keywords": ["mot1", "mot2", "mot3"]
        }}
    ],
    "metadata": {{
        "total_requirements_found": <nombre>,
        "sections_analyzed": ["section1", "section2"],
        "extraction_notes": "Notes éventuelles sur l'extraction"
    }},
    "confidence_avg": 0.0-1.0,
    "document_type": "{document_type.value if document_type else 'unknown'}"
}}"""

        return system_prompt, user_prompt

    @classmethod
    def build_validation_prompt(
        cls,
        requirement: Dict,
        document_context: str
    ) -> str:
        """
        Construit un prompt pour valider un requirement extrait.

        Args:
            requirement: Requirement à valider
            document_context: Contexte du document

        Returns:
            Prompt de validation
        """
        return f"""Valide le requirement suivant extrait d'un document de marché public :

REQUIREMENT :
{requirement}

CONTEXTE :
{document_context[:500]}

Questions de validation :
1. La catégorie est-elle correcte ?
2. La description est-elle claire et actionnable ?
3. Le niveau d'importance est-il approprié ?
4. L'extraction du texte source est-elle exacte ?
5. Y a-t-il des informations manquantes ou incorrectes ?

Retourne un score de validation de 0.0 à 1.0 et des suggestions d'amélioration au format JSON."""

    @classmethod
    def build_consolidation_prompt(
        cls,
        requirements: List[Dict],
        document_type: Optional[DocumentType] = None
    ) -> str:
        """
        Construit un prompt pour consolider et dédupliquer des requirements.

        Args:
            requirements: Liste de requirements à consolider
            document_type: Type de document

        Returns:
            Prompt de consolidation
        """
        return f"""Consolide et déduplique la liste de requirements suivante :

REQUIREMENTS :
{requirements[:20]}  # Limiter pour éviter token overflow

INSTRUCTIONS :
1. Identifie les doublons et fusionne-les
2. Groupe les requirements similaires
3. Vérifie la cohérence des catégories
4. Ajuste les niveaux d'importance si nécessaire
5. Améliore les descriptions pour plus de clarté

Retourne la liste consolidée au format JSON avec les mêmes champs que l'original."""