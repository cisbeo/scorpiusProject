#!/usr/bin/env python3
"""
API FastAPI pour le POC Docling.
Expose les fonctionnalités d'extraction via REST API.
"""

import os
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
import logging

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from docling_processor import DoclingPDFProcessor, DoclingComparator, ExtractionResult

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialisation FastAPI
app = FastAPI(
    title="Docling POC API",
    description="API pour tester l'extraction de documents avec Docling",
    version="1.0.0"
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialisation des processeurs
processor = DoclingPDFProcessor()
comparator = DoclingComparator()


class HealthResponse(BaseModel):
    """Réponse health check."""
    status: str
    docling_available: bool
    version: str


class ExtractionRequest(BaseModel):
    """Requête d'extraction."""
    file_path: str
    use_ocr: bool = False
    compare_with_traditional: bool = False


class ExtractionResponse(BaseModel):
    """Réponse d'extraction."""
    success: bool
    filename: str
    method: str
    confidence: float
    text_preview: str
    requirements_count: int
    tables_count: int
    processing_time_ms: float
    problems_detected: bool
    comparison: Optional[Dict[str, Any]] = None


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Vérification de l'état du service."""
    return HealthResponse(
        status="healthy",
        docling_available=processor.docling_available,
        version="1.0.0"
    )


@app.post("/extract", response_model=ExtractionResponse)
async def extract_document(file: UploadFile = File(...), compare: bool = False):
    """
    Extrait le contenu d'un document PDF avec Docling.

    Args:
        file: Fichier PDF à traiter
        compare: Si True, compare avec extraction traditionnelle

    Returns:
        ExtractionResponse avec résultats
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Seuls les fichiers PDF sont supportés")

    try:
        # Sauvegarder temporairement le fichier
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = Path(tmp.name)

        # Extraction avec Docling
        if compare:
            # Comparaison complète
            comparison = comparator.compare_extraction(tmp_path)
            docling_data = comparison["docling"]

            # Récupérer le texte complet pour preview
            result = processor.process_pdf(tmp_path)
            text_preview = result.raw_text[:500] + "..." if len(result.raw_text) > 500 else result.raw_text

            response = ExtractionResponse(
                success=True,
                filename=file.filename,
                method=docling_data["method"],
                confidence=docling_data["confidence"],
                text_preview=text_preview,
                requirements_count=docling_data["requirements_count"],
                tables_count=docling_data["tables_count"],
                processing_time_ms=docling_data["processing_time_ms"],
                problems_detected=docling_data["has_problems"],
                comparison=comparison
            )
        else:
            # Extraction simple
            result = processor.process_pdf(tmp_path)

            text_preview = result.raw_text[:500] + "..." if len(result.raw_text) > 500 else result.raw_text

            response = ExtractionResponse(
                success=result.success,
                filename=file.filename,
                method=result.method,
                confidence=result.confidence,
                text_preview=text_preview,
                requirements_count=len(result.requirements),
                tables_count=len(result.tables),
                processing_time_ms=result.processing_time_ms,
                problems_detected="PR OGRAMME" in result.raw_text or "DI GITALE" in result.raw_text
            )

        # Nettoyer
        os.unlink(tmp_path)

        return response

    except Exception as e:
        logger.error(f"Erreur lors de l'extraction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/extract/full")
async def extract_document_full(file: UploadFile = File(...)):
    """
    Extraction complète avec tous les détails.

    Returns:
        ExtractionResult complet en JSON
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Seuls les fichiers PDF sont supportés")

    try:
        # Sauvegarder temporairement
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = Path(tmp.name)

        # Extraction complète
        result = processor.process_pdf(tmp_path)

        # Nettoyer
        os.unlink(tmp_path)

        # Convertir en dict pour JSON
        return JSONResponse(content={
            "success": result.success,
            "filename": result.filename,
            "method": result.method,
            "confidence": result.confidence,
            "raw_text": result.raw_text,
            "structured_data": result.structured_data,
            "tables": result.tables,
            "requirements": result.requirements,
            "metadata": result.metadata,
            "processing_time_ms": result.processing_time_ms,
            "errors": result.errors
        })

    except Exception as e:
        logger.error(f"Erreur lors de l'extraction complète: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/test/cctp")
async def test_cctp_extraction():
    """
    Test sur un fichier CCTP problématique connu.
    """
    test_file = Path("/app/data/examples/CCTP_HEC.pdf")

    if not test_file.exists():
        # Créer un fichier de test
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter

        test_file = Path("/app/temp/test_cctp.pdf")
        c = canvas.Canvas(str(test_file), pagesize=letter)

        # Simuler les problèmes Word 2013
        c.setFont("Helvetica-Bold", 14)
        c.drawString(100, 750, "ACCOMPAGNEMENT AU PR OGRAMME")
        c.drawString(100, 730, "DE TRANSFORMATION DI GITALE HEC PARIS")
        c.drawString(100, 700, "CAHIER DES CLAUSES TECHNIQUES")

        c.setFont("Helvetica", 12)
        c.drawString(100, 650, "1. Objet du marché")
        c.drawString(100, 620, "La partie A comprend les prestations suivantes :")
        c.drawString(120, 590, "- Program Management Office")
        c.drawString(120, 570, "- Organisation et an imation d'ateliers")
        c.drawString(120, 550, "- Conseil en architecture d'entreprise")

        c.showPage()
        c.save()

        logger.info(f"Fichier de test créé: {test_file}")

    # Comparer les extractions
    comparison = comparator.compare_extraction(test_file)

    return JSONResponse(content=comparison)


@app.get("/demo")
async def demo_interface():
    """
    Interface de démonstration HTML simple.
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Docling POC - Demo</title>
        <style>
            body { font-family: Arial; margin: 40px; background: #f5f5f5; }
            .container { max-width: 900px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }
            h1 { color: #333; border-bottom: 3px solid #007bff; padding-bottom: 10px; }
            .upload-box {
                border: 2px dashed #007bff;
                padding: 30px;
                text-align: center;
                margin: 20px 0;
                background: #f8f9fa;
                border-radius: 5px;
            }
            input[type="file"] { margin: 20px 0; }
            button {
                background: #007bff;
                color: white;
                padding: 12px 30px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;
            }
            button:hover { background: #0056b3; }
            .results {
                margin-top: 30px;
                padding: 20px;
                background: #f8f9fa;
                border-radius: 5px;
                white-space: pre-wrap;
                font-family: monospace;
                max-height: 600px;
                overflow-y: auto;
            }
            .success { color: green; font-weight: bold; }
            .error { color: red; font-weight: bold; }
            .warning { color: orange; font-weight: bold; }
            .info { color: #007bff; }
            .loader { display: none; text-align: center; margin: 20px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 Docling POC - Extraction PDF Intelligente</h1>

            <div class="upload-box">
                <h2>📄 Télécharger un PDF</h2>
                <input type="file" id="pdfFile" accept=".pdf" />
                <br>
                <label>
                    <input type="checkbox" id="compareMode">
                    Comparer avec extraction traditionnelle
                </label>
                <br><br>
                <button onclick="extractPDF()">🔍 Analyser le document</button>
            </div>

            <div class="loader" id="loader">
                ⏳ Traitement en cours...
            </div>

            <div id="results" class="results" style="display:none;"></div>

            <hr style="margin: 40px 0;">

            <div style="text-align: center;">
                <button onclick="testCCTP()" style="background: #28a745;">
                    🧪 Tester avec CCTP problématique
                </button>
            </div>
        </div>

        <script>
            async function extractPDF() {
                const fileInput = document.getElementById('pdfFile');
                const compareMode = document.getElementById('compareMode').checked;
                const resultsDiv = document.getElementById('results');
                const loader = document.getElementById('loader');

                if (!fileInput.files[0]) {
                    alert('Veuillez sélectionner un fichier PDF');
                    return;
                }

                const formData = new FormData();
                formData.append('file', fileInput.files[0]);

                loader.style.display = 'block';
                resultsDiv.style.display = 'none';

                try {
                    const response = await fetch(`/extract?compare=${compareMode}`, {
                        method: 'POST',
                        body: formData
                    });

                    const data = await response.json();
                    displayResults(data);
                } catch (error) {
                    resultsDiv.innerHTML = `<span class="error">Erreur: ${error}</span>`;
                    resultsDiv.style.display = 'block';
                }

                loader.style.display = 'none';
            }

            async function testCCTP() {
                const resultsDiv = document.getElementById('results');
                const loader = document.getElementById('loader');

                loader.style.display = 'block';
                resultsDiv.style.display = 'none';

                try {
                    const response = await fetch('/test/cctp');
                    const data = await response.json();
                    displayComparison(data);
                } catch (error) {
                    resultsDiv.innerHTML = `<span class="error">Erreur: ${error}</span>`;
                    resultsDiv.style.display = 'block';
                }

                loader.style.display = 'none';
            }

            function displayResults(data) {
                const resultsDiv = document.getElementById('results');

                let html = '<h2>📊 Résultats de l\\'extraction</h2>';

                html += `<span class="${data.success ? 'success' : 'error'}">`;
                html += data.success ? '✅ Extraction réussie' : '❌ Extraction échouée';
                html += '</span>\\n\\n';

                html += `<span class="info">📄 Fichier:</span> ${data.filename}\\n`;
                html += `<span class="info">🔧 Méthode:</span> ${data.method}\\n`;
                html += `<span class="info">📊 Confiance:</span> ${(data.confidence * 100).toFixed(1)}%\\n`;
                html += `<span class="info">📝 Requirements:</span> ${data.requirements_count}\\n`;
                html += `<span class="info">📋 Tableaux:</span> ${data.tables_count}\\n`;
                html += `<span class="info">⏱️ Temps:</span> ${data.processing_time_ms.toFixed(0)}ms\\n`;

                if (data.problems_detected) {
                    html += `\\n<span class="warning">⚠️ Problèmes détectés (PR OGRAMME, DI GITALE)</span>\\n`;
                } else {
                    html += `\\n<span class="success">✅ Aucun problème d'espacement détecté</span>\\n`;
                }

                html += '\\n<span class="info">📖 Aperçu du texte:</span>\\n';
                html += data.text_preview;

                if (data.comparison) {
                    html += '\\n\\n<h3>🔄 Comparaison avec extraction traditionnelle</h3>';
                    html += formatComparison(data.comparison);
                }

                resultsDiv.innerHTML = html;
                resultsDiv.style.display = 'block';
            }

            function displayComparison(data) {
                const resultsDiv = document.getElementById('results');

                let html = '<h2>🧪 Test CCTP Problématique</h2>';
                html += formatComparison(data);

                resultsDiv.innerHTML = html;
                resultsDiv.style.display = 'block';
            }

            function formatComparison(comp) {
                let html = '\\n<table style="width: 100%; border-collapse: collapse;">';
                html += '<tr style="background: #f0f0f0;">';
                html += '<th style="padding: 10px; border: 1px solid #ddd;">Critère</th>';
                html += '<th style="padding: 10px; border: 1px solid #ddd;">Docling</th>';
                html += '<th style="padding: 10px; border: 1px solid #ddd;">Traditionnel</th>';
                html += '</tr>';

                const metrics = [
                    ['Méthode', comp.docling.method, comp.traditional.method],
                    ['Confiance', `${(comp.docling.confidence * 100).toFixed(1)}%`, `${(comp.traditional.confidence * 100).toFixed(1)}%`],
                    ['Longueur texte', comp.docling.text_length, comp.traditional.text_length],
                    ['Requirements', comp.docling.requirements_count, comp.traditional.requirements_count],
                    ['Tableaux', comp.docling.tables_count, comp.traditional.tables_count],
                    ['Temps (ms)', comp.docling.processing_time_ms.toFixed(0), comp.traditional.processing_time_ms.toFixed(0)],
                    ['Problèmes', comp.docling.has_problems ? '❌ Oui' : '✅ Non', comp.traditional.has_problems ? '❌ Oui' : '✅ Non']
                ];

                for (const [label, docling, trad] of metrics) {
                    html += '<tr>';
                    html += `<td style="padding: 8px; border: 1px solid #ddd;">${label}</td>`;
                    html += `<td style="padding: 8px; border: 1px solid #ddd;">${docling}</td>`;
                    html += `<td style="padding: 8px; border: 1px solid #ddd;">${trad}</td>`;
                    html += '</tr>';
                }

                html += '</table>';

                if (comp.improvements && Object.keys(comp.improvements).length > 0) {
                    html += '\\n<h3>✨ Améliorations Docling</h3>';
                    for (const [key, value] of Object.entries(comp.improvements)) {
                        html += `<span class="success">✅ ${key}: ${value}</span>\\n`;
                    }
                }

                return html;
            }
        </script>
    </body>
    </html>
    """

    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html_content)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)