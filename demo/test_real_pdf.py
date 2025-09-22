#!/usr/bin/env python3
"""Test Scorpius MVP avec le PDF test.pdf."""

import asyncio
import json
import os
from datetime import datetime
import httpx

# Configuration
API_BASE_URL = "http://localhost:8000/api/v1"
PDF_PATH = "/Users/cedric/Downloads/test.pdf"

# Credentials pour le test
TEST_USER = {
    "email": f"demo_{datetime.now().strftime('%Y%m%d_%H%M%S')}@test.fr",
    "password": "TestSecure2024!",
    "full_name": "Demo Test User"
}

# Profil entreprise de test
TEST_COMPANY = {
    "company_name": "Demo Solutions SAS",
    "siret": "98765432101234",
    "description": "Entreprise de développement logiciel spécialisée en solutions cloud",
    "capabilities": [
        {
            "domain": "Développement Full-Stack",
            "technologies": ["Python", "FastAPI", "React", "PostgreSQL", "Redis"],
            "experience_years": 7
        },
        {
            "domain": "Infrastructure Cloud",
            "technologies": ["Docker", "Kubernetes", "AWS", "Terraform"],
            "experience_years": 5
        },
        {
            "domain": "Sécurité",
            "technologies": ["OAuth2", "JWT", "SSL/TLS", "OWASP"],
            "experience_years": 4
        }
    ],
    "certifications": [
        {
            "name": "ISO 27001",
            "valid_until": "2026-12-31",
            "issuer": "Bureau Veritas"
        }
    ],
    "references": [
        {
            "client": "Ministère de l'Économie",
            "project": "Plateforme de gestion documentaire",
            "year": 2023,
            "amount": 450000
        }
    ],
    "team_size": 25,
    "annual_revenue": 3500000,
    "founding_year": 2015,
    "contact_email": "contact@demo-solutions.fr",
    "contact_phone": "+33 1 42 86 92 48",
    "address": "10 Rue de la Paix, 75002 Paris"
}


class TestRunner:
    def __init__(self):
        self.client = httpx.AsyncClient(base_url=API_BASE_URL, timeout=60.0)
        self.token = None
        self.user_id = None
        self.company_id = None
        self.document_id = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.client.aclose()

    def log(self, msg, level="INFO"):
        icons = {"SUCCESS": "✅", "ERROR": "❌", "INFO": "ℹ️", "WAIT": "⏳", "DATA": "📊"}
        print(f"{icons.get(level, '•')} {msg}")

    async def step_1_register(self):
        """Étape 1: Inscription utilisateur"""
        self.log("=== ÉTAPE 1: INSCRIPTION ===", "INFO")

        try:
            response = await self.client.post("/auth/register", json={
                **TEST_USER,
                "role": "bid_manager"
            })

            if response.status_code == 201:
                data = response.json()
                self.token = data["tokens"]["access_token"]
                self.user_id = data["user"]["id"]
                self.client.headers["Authorization"] = f"Bearer {self.token}"

                self.log(f"Utilisateur créé: {data['user']['email']}", "SUCCESS")
                self.log(f"User ID: {self.user_id}", "DATA")
                return True
            else:
                self.log(f"Erreur: {response.status_code} - {response.text}", "ERROR")
                return False

        except Exception as e:
            self.log(f"Exception: {e}", "ERROR")
            return False

    async def step_2_company(self):
        """Étape 2: Création profil entreprise"""
        self.log("\n=== ÉTAPE 2: PROFIL ENTREPRISE ===", "INFO")

        try:
            response = await self.client.post("/company-profile", json=TEST_COMPANY)

            if response.status_code == 201:
                data = response.json()
                self.company_id = data["id"]
                self.log(f"Profil créé: {data['company_name']}", "SUCCESS")
                self.log(f"Company ID: {self.company_id}", "DATA")
                self.log(f"Capacités: {len(TEST_COMPANY['capabilities'])} domaines", "DATA")
                return True
            else:
                # Peut-être que le profil existe déjà
                get_resp = await self.client.get("/company-profile")
                if get_resp.status_code == 200:
                    data = get_resp.json()
                    self.company_id = data["id"]
                    self.log("Profil existant récupéré", "SUCCESS")
                    return True
                else:
                    self.log(f"Erreur: {response.status_code} - {response.text}", "ERROR")
                    return False

        except Exception as e:
            self.log(f"Exception: {e}", "ERROR")
            return False

    async def step_3_upload(self):
        """Étape 3: Upload du PDF"""
        self.log("\n=== ÉTAPE 3: UPLOAD PDF ===", "INFO")

        if not os.path.exists(PDF_PATH):
            self.log(f"Fichier non trouvé: {PDF_PATH}", "ERROR")
            return False

        try:
            # Lire le PDF
            with open(PDF_PATH, "rb") as f:
                pdf_data = f.read()

            file_size_mb = len(pdf_data) / (1024 * 1024)
            self.log(f"Fichier: test.pdf ({file_size_mb:.2f} MB)", "DATA")

            # Upload
            files = {"file": ("test.pdf", pdf_data, "application/pdf")}

            self.log("Upload en cours...", "WAIT")
            response = await self.client.post("/documents", files=files)

            if response.status_code in [200, 201]:
                data = response.json()
                self.document_id = data["id"]

                self.log("Document uploadé avec succès!", "SUCCESS")
                self.log(f"Document ID: {self.document_id}", "DATA")
                self.log(f"Status: {data.get('status', 'N/A')}", "DATA")
                return True
            else:
                self.log(f"Erreur upload: {response.status_code}", "ERROR")
                self.log(f"Détails: {response.text[:200]}", "ERROR")
                return False

        except Exception as e:
            self.log(f"Exception: {e}", "ERROR")
            return False

    async def step_4_process(self):
        """Étape 4: Traitement du document"""
        self.log("\n=== ÉTAPE 4: TRAITEMENT ===", "INFO")

        if not self.document_id:
            self.log("Pas de document ID", "ERROR")
            return False

        try:
            # Lancer le traitement
            self.log("Démarrage du traitement...", "WAIT")
            process_resp = await self.client.post(f"/documents/{self.document_id}/process")

            if process_resp.status_code not in [200, 201, 202]:
                self.log(f"Impossible de démarrer le traitement: {process_resp.status_code}", "ERROR")

            # Vérifier le statut
            max_attempts = 15
            for i in range(max_attempts):
                await asyncio.sleep(2)

                response = await self.client.get(f"/documents/{self.document_id}")
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status", "unknown")

                    self.log(f"Tentative {i+1}/{max_attempts}: Status = {status}", "WAIT")

                    if status == "processed":
                        self.log("Document traité avec succès!", "SUCCESS")

                        # Afficher les métadonnées si disponibles
                        if "page_count" in data:
                            self.log(f"Pages: {data['page_count']}", "DATA")
                        if "file_size" in data:
                            self.log(f"Taille: {data['file_size']} bytes", "DATA")

                        return True
                    elif status == "failed":
                        self.log(f"Échec: {data.get('error', 'Unknown')}", "ERROR")
                        return False

            self.log("Timeout - traitement trop long", "ERROR")
            return False

        except Exception as e:
            self.log(f"Exception: {e}", "ERROR")
            return False

    async def step_5_requirements(self):
        """Étape 5: Extraction des exigences"""
        self.log("\n=== ÉTAPE 5: EXTRACTION EXIGENCES ===", "INFO")

        if not self.document_id:
            return False

        try:
            response = await self.client.get(f"/documents/{self.document_id}/requirements")

            if response.status_code == 200:
                data = response.json()

                self.log("Exigences extraites!", "SUCCESS")
                self.log(f"Total: {data.get('total_requirements', 0)} exigences", "DATA")

                # Afficher par catégorie
                if "requirements" in data:
                    reqs = data["requirements"]
                    if isinstance(reqs, dict):
                        for category, items in reqs.items():
                            if isinstance(items, list):
                                self.log(f"  • {category}: {len(items)} items", "DATA")

                # Afficher un échantillon
                print("\n📄 Échantillon du contenu extrait:")
                content_preview = json.dumps(data, indent=2, ensure_ascii=False)[:500]
                print(content_preview + "...\n")

                return True
            else:
                self.log(f"Erreur: {response.status_code}", "ERROR")
                return False

        except Exception as e:
            self.log(f"Exception: {e}", "ERROR")
            return False

    async def step_6_analysis(self):
        """Étape 6: Analyse de compatibilité"""
        self.log("\n=== ÉTAPE 6: ANALYSE COMPATIBILITÉ ===", "INFO")

        if not self.document_id or not self.company_id:
            self.log("IDs manquants", "ERROR")
            return False

        try:
            payload = {
                "document_id": self.document_id,
                "company_profile_id": self.company_id,
                "analysis_options": {
                    "min_score_threshold": 0.5,
                    "include_partial_matches": True
                }
            }

            self.log("Lancement de l'analyse...", "WAIT")
            response = await self.client.post("/analysis/match", json=payload)

            if response.status_code == 200:
                data = response.json()

                score = data.get("overall_match_score", 0)
                self.log(f"Score global: {score}%", "SUCCESS")
                self.log(f"Recommandation: {data.get('recommendation', 'N/A')}", "DATA")
                self.log(f"Confiance: {data.get('confidence_level', 0)*100:.0f}%", "DATA")

                print("\n📈 Analyse détaillée:")
                print(f"  • Techniques: {data.get('technical_matches', 0)}/{data.get('total_requirements', 0)}")
                print(f"  • Fonctionnelles: {data.get('functional_matches', 0)}")
                print(f"  • Administratives: {data.get('administrative_matches', 0)}")

                if "strengths" in data and data["strengths"]:
                    print("\n✅ Points forts:")
                    for s in data["strengths"][:3]:
                        print(f"  • {s}")

                if "missing_capabilities" in data and data["missing_capabilities"]:
                    print("\n⚠️ À améliorer:")
                    for m in data["missing_capabilities"][:3]:
                        print(f"  • {m}")

                return True
            else:
                self.log(f"Erreur analyse: {response.status_code}", "ERROR")
                return False

        except Exception as e:
            self.log(f"Exception: {e}", "ERROR")
            return False

    async def run(self):
        """Exécuter tous les tests"""
        print("\n" + "="*50)
        print("🚀 TEST SCORPIUS AVEC PDF RÉEL")
        print(f"📄 Fichier: {PDF_PATH}")
        print("="*50 + "\n")

        steps = [
            ("Inscription", self.step_1_register),
            ("Profil entreprise", self.step_2_company),
            ("Upload PDF", self.step_3_upload),
            ("Traitement", self.step_4_process),
            ("Extraction", self.step_5_requirements),
            ("Analyse", self.step_6_analysis)
        ]

        results = {}
        for name, func in steps:
            success = await func()
            results[name] = success

            if not success:
                self.log(f"\n⛔ Arrêt après échec: {name}", "ERROR")
                break

            await asyncio.sleep(1)

        # Résumé
        print("\n" + "="*50)
        print("📊 RÉSUMÉ")
        print("="*50)

        for name, success in results.items():
            status = "✅" if success else "❌"
            print(f"{status} {name}")

        passed = sum(1 for s in results.values() if s)
        total = len(results)

        print(f"\nScore: {passed}/{total}")

        if passed == total:
            print("\n🎉 TOUS LES TESTS RÉUSSIS!")
            print("Le système fonctionne correctement avec un vrai PDF.")
        else:
            print("\n⚠️ Des problèmes ont été détectés.")

        return passed == total


async def main():
    """Point d'entrée principal"""
    try:
        # Vérifier que Docker est lancé
        print("Vérification des services...")
        os.system("docker-compose ps | grep api")

        print("\nAttente de l'API (3 sec)...")
        await asyncio.sleep(3)

        async with TestRunner() as runner:
            await runner.run()

    except KeyboardInterrupt:
        print("\n\nTest interrompu.")
    except Exception as e:
        print(f"\nErreur: {e}")


if __name__ == "__main__":
    asyncio.run(main())