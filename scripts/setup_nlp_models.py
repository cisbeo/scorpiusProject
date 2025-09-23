#!/usr/bin/env python3
"""
Setup script to download and cache NLP models for Scorpius Project.
Run this after installing requirements-ml.txt
"""

import os
import sys
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_models_directory():
    """Create local models directory for caching."""
    models_dir = Path("models")
    models_dir.mkdir(exist_ok=True)

    subdirs = ["transformers", "spacy", "sentence-transformers"]
    for subdir in subdirs:
        (models_dir / subdir).mkdir(exist_ok=True)

    logger.info(f"✅ Models directory created at: {models_dir.absolute()}")
    return models_dir

def download_transformers_models():
    """Download and cache Transformers models."""
    logger.info("📥 Downloading Transformers models...")

    try:
        from transformers import AutoTokenizer, AutoModel, AutoModelForSequenceClassification

        models = [
            "camembert-base",  # Base French model
            # "maveriq/legal-camembert",  # Legal French model (if available)
        ]

        for model_name in models:
            try:
                logger.info(f"  Downloading {model_name}...")
                tokenizer = AutoTokenizer.from_pretrained(model_name)
                model = AutoModel.from_pretrained(model_name)

                # Cache locally
                local_path = Path(f"models/transformers/{model_name.replace('/', '-')}")
                tokenizer.save_pretrained(local_path)
                model.save_pretrained(local_path)

                logger.info(f"  ✅ {model_name} downloaded and cached")
            except Exception as e:
                logger.warning(f"  ⚠️ Could not download {model_name}: {e}")

    except ImportError:
        logger.error("❌ Transformers not installed. Run: pip install transformers")
        return False

    return True

def download_sentence_transformers():
    """Download and cache Sentence Transformers models."""
    logger.info("📥 Downloading Sentence Transformers models...")

    try:
        from sentence_transformers import SentenceTransformer

        models = [
            "dangvantuan/sentence-camembert-base",  # French sentence embeddings
            # "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",  # Multilingual fallback
        ]

        for model_name in models:
            try:
                logger.info(f"  Downloading {model_name}...")
                model = SentenceTransformer(model_name)

                # Cache locally
                local_path = Path(f"models/sentence-transformers/{model_name.replace('/', '-')}")
                model.save(str(local_path))

                logger.info(f"  ✅ {model_name} downloaded and cached")
            except Exception as e:
                logger.warning(f"  ⚠️ Could not download {model_name}: {e}")

    except ImportError:
        logger.error("❌ Sentence-transformers not installed. Run: pip install sentence-transformers")
        return False

    return True

def setup_spacy():
    """Download spaCy French language model."""
    logger.info("📥 Setting up spaCy French model...")

    try:
        import spacy
        import subprocess

        # Download French model
        models = ["fr_core_news_sm", "fr_core_news_lg"]

        for model in models:
            try:
                # Try to load to check if already installed
                spacy.load(model)
                logger.info(f"  ✅ {model} already installed")
            except:
                # Download if not installed
                logger.info(f"  Downloading {model}...")
                result = subprocess.run(
                    [sys.executable, "-m", "spacy", "download", model],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    logger.info(f"  ✅ {model} downloaded successfully")
                else:
                    logger.warning(f"  ⚠️ Could not download {model}: {result.stderr}")

    except ImportError:
        logger.error("❌ spaCy not installed. Run: pip install spacy")
        return False

    return True

def verify_installation():
    """Verify all models are properly installed."""
    logger.info("\n🔍 Verifying installation...")

    checks = []

    # Check Transformers
    try:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained("camembert-base")
        logger.info("  ✅ Transformers: CamemBERT ready")
        checks.append(True)
    except:
        logger.error("  ❌ Transformers: CamemBERT not available")
        checks.append(False)

    # Check Sentence Transformers
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("dangvantuan/sentence-camembert-base")
        logger.info("  ✅ Sentence-Transformers: French embeddings ready")
        checks.append(True)
    except:
        logger.error("  ❌ Sentence-Transformers: French embeddings not available")
        checks.append(False)

    # Check spaCy
    try:
        import spacy
        nlp = spacy.load("fr_core_news_sm")
        logger.info("  ✅ spaCy: French model ready")
        checks.append(True)
    except:
        logger.error("  ❌ spaCy: French model not available")
        checks.append(False)

    return all(checks)

def main():
    """Main setup function."""
    logger.info("🚀 Starting NLP models setup for Scorpius Project\n")

    # Create directories
    setup_models_directory()

    # Download models
    success = True
    success &= download_transformers_models()
    success &= download_sentence_transformers()
    success &= setup_spacy()

    # Verify
    if verify_installation():
        logger.info("\n✅ All NLP models successfully installed and ready!")
        logger.info("📌 Models cached in ./models/ directory")
        return 0
    else:
        logger.error("\n⚠️ Some models failed to install. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())