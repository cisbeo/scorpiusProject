# Plan Détaillé : Migration vers Docling comme Processeur Principal

## 🎯 Objectif
Remplacer PyPDF2 par Docling comme processeur principal pour bénéficier de ses capacités avancées d'extraction structurelle, tout en gardant PyPDF2 comme fallback.

---

## Phase 1️⃣ : Préparation & Installation (Jour 1-2)

### 1.1 Installation Docling
```bash
# requirements.txt
docling>=2.0.0
docling-parse>=1.0.0
docling-ibm-models>=1.0.0  # Pour OCR si nécessaire
```

### 1.2 Configuration
```python
# src/core/config.py
class Settings(BaseSettings):
    # Document Processing
    default_processor: str = Field(default="docling", description="Default processor")
    enable_docling_ocr: bool = Field(default=False, description="Enable OCR in Docling")
    enable_docling_tables: bool = Field(default=True, description="Extract tables")
    enable_docling_layout: bool = Field(default=True, description="Detect layout")
    docling_timeout: int = Field(default=60, description="Docling timeout in seconds")
```

### 1.3 Créer ProcessorFactory améliorée
```python
# src/processors/factory.py
class ProcessorFactory:
    def get_processor(self, filename: str, mime_type: str) -> DocumentProcessor:
        if settings.default_processor == "docling":
            try:
                return DoclingProcessor()
            except ImportError:
                logger.warning("Docling not available, falling back to PyPDF2")
                return PDFProcessor()
        return PDFProcessor()
```

---

## Phase 2️⃣ : Amélioration DoclingProcessor (Jour 3-5)

### 2.1 Extraction Structurelle Avancée
```python
# src/processors/docling_processor.py

class EnhancedDoclingProcessor(DoclingProcessor):

    async def process_document(self, file_content: bytes, filename: str, ...) -> ProcessingResult:
        # Configuration spécifique pour documents français
        pipeline_options = PipelineOptions(
            do_table_structure=True,
            do_ocr=settings.enable_docling_ocr,
            do_layout_analysis=True,
            language_hint="fr",
            table_extraction_options={
                "method": "lattice",  # Pour tableaux avec bordures
                "flavor": "stream"     # Pour tableaux sans bordures
            }
        )

        result = await self._docling_extract(file_path, pipeline_options)

        # Enrichir avec structure hiérarchique
        structured_content = await self._build_document_tree(result)

        return ProcessingResult(
            raw_text=result.export_to_markdown(),
            structured_content=structured_content,
            document_tree=self._create_hierarchical_tree(result),  # NOUVEAU
            metadata={
                "extraction_method": "docling",
                "layout_detected": True,
                "tables_extracted": len(structured_content["tables"]),
                "sections_detected": len(structured_content["sections"])
            }
        )
```

### 2.2 Création Arbre Hiérarchique
```python
@dataclass
class DocumentNode:
    """Nœud de l'arbre documentaire."""
    id: str
    type: str  # chapitre, article, section, paragraphe, alinea
    level: int  # Profondeur dans l'arbre
    number: Optional[str]  # 1.2.3
    title: Optional[str]
    content: str
    parent: Optional['DocumentNode'] = None
    children: List['DocumentNode'] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    page_numbers: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type,
            "level": self.level,
            "number": self.number,
            "title": self.title,
            "content": self.content[:200] + "..." if len(self.content) > 200 else self.content,
            "children": [child.to_dict() for child in self.children],
            "metadata": self.metadata,
            "page_numbers": self.page_numbers
        }

async def _build_document_tree(self, docling_result) -> DocumentNode:
    """Construit l'arbre hiérarchique du document."""

    root = DocumentNode(
        id="root",
        type="document",
        level=0,
        content="",
        title=docling_result.metadata.title or "Document"
    )

    current_chapter = None
    current_article = None
    current_section = None

    for element in docling_result.body:
        if element.type == "heading":
            node = self._create_heading_node(element)

            if element.level == 1:  # Chapitre/Titre
                root.children.append(node)
                current_chapter = node
                current_article = None
                current_section = None

            elif element.level == 2:  # Article
                if current_chapter:
                    current_chapter.children.append(node)
                    node.parent = current_chapter
                else:
                    root.children.append(node)
                current_article = node
                current_section = None

            elif element.level == 3:  # Section/Clause
                if current_article:
                    current_article.children.append(node)
                    node.parent = current_article
                elif current_chapter:
                    current_chapter.children.append(node)
                    node.parent = current_chapter
                else:
                    root.children.append(node)
                current_section = node

        elif element.type == "paragraph":
            node = self._create_paragraph_node(element)

            # Attacher au niveau le plus bas disponible
            if current_section:
                current_section.children.append(node)
                node.parent = current_section
            elif current_article:
                current_article.children.append(node)
                node.parent = current_article
            elif current_chapter:
                current_chapter.children.append(node)
                node.parent = current_chapter
            else:
                root.children.append(node)

        elif element.type == "table":
            node = self._create_table_node(element)
            # Même logique d'attachement...

    return root
```

---

## Phase 3️⃣ : Intégration Pipeline (Jour 6-8)

### 3.1 Modifier DocumentPipelineService
```python
# src/services/document/pipeline_service.py

async def _process_document_content(self, document: ProcurementDocument, ...):
    # Toujours utiliser Docling en premier
    processor = DoclingProcessor()

    try:
        result = await processor.process_document(...)

        # Stocker l'arbre hiérarchique
        if result.document_tree:
            await self._store_document_tree(document.id, result.document_tree)

    except Exception as e:
        logger.warning(f"Docling failed: {e}, falling back to PyPDF2")
        processor = PDFProcessor()
        result = await processor.process_document(...)

    return result
```

### 3.2 Nouveau modèle pour l'arbre
```python
# src/models/document_structure.py

class DocumentStructure(BaseModel):
    """Stockage de la structure hiérarchique du document."""

    __tablename__ = "document_structures"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("procurement_documents.id"))

    # Structure complète en JSON
    tree_json: Mapped[dict] = mapped_column(JSON)

    # Métadonnées de structure
    total_nodes: Mapped[int]
    max_depth: Mapped[int]
    section_count: Mapped[int]

    # Index pour recherche rapide
    sections_index: Mapped[dict] = mapped_column(JSON)  # {"article_1": node_id, ...}
```

---

## Phase 4️⃣ : Chunking Intelligent avec Structure (Jour 9-10)

### 4.1 Chunking basé sur l'arbre Docling
```python
# src/services/ai/chunking_service.py

class DoclingAwareChunkingService(ChunkingService):

    async def _structural_chunking_with_tree(
        self,
        document_tree: DocumentNode,
        document_id: str
    ) -> List[DocumentChunk]:
        """Chunking intelligent basé sur l'arbre Docling."""

        chunks = []
        chunk_index = 0

        def process_node(node: DocumentNode, context_path: List[str]):
            nonlocal chunk_index

            # Construire le contexte hiérarchique
            context = " > ".join(context_path + [node.title or node.type])

            # Décider si le nœud devient un chunk
            if self._should_create_chunk(node):
                chunk_text = self._build_chunk_text(node, include_children=True)

                # Si trop gros, diviser
                if len(chunk_text) > self.max_chunk_size * 4:
                    sub_chunks = self._split_node_intelligently(node, context)
                    chunks.extend(sub_chunks)
                else:
                    chunk = DocumentChunk(
                        chunk_id=self._generate_chunk_id(document_id, chunk_index),
                        chunk_text=chunk_text,
                        chunk_index=chunk_index,
                        chunk_size=len(chunk_text),
                        metadata={
                            "node_id": node.id,
                            "node_type": node.type,
                            "node_level": node.level,
                            "context_path": context,
                            "page_numbers": node.page_numbers
                        },
                        section_type=node.type,
                        document_type=self._detect_document_type(chunk_text),
                        page_number=node.page_numbers[0] if node.page_numbers else None
                    )
                    chunks.append(chunk)
                    chunk_index += 1

            # Traiter les enfants
            for child in node.children:
                process_node(child, context_path + [node.title or node.type])

        # Démarrer depuis la racine
        process_node(document_tree, [])

        return chunks

    def _should_create_chunk(self, node: DocumentNode) -> bool:
        """Détermine si un nœud doit devenir un chunk."""
        # Articles et sections deviennent des chunks
        if node.type in ["article", "section", "clause"]:
            return True

        # Les chapitres avec peu de contenu direct
        if node.type == "chapter" and len(node.children) <= 3:
            return True

        # Les paragraphes isolés longs
        if node.type == "paragraph" and len(node.content) > 1000:
            return True

        return False
```

---

## Phase 5️⃣ : Extraction Spécialisée CCTP (Jour 11-12)

### 5.1 Service CCTP amélioré avec Docling
```python
# src/services/cctp_synthesis_service.py

class CCTPSynthesisService:

    async def extract_cctp_structure(self, document: ProcurementDocument):
        """Extrait la structure spécifique CCTP avec Docling."""

        # Récupérer l'arbre du document
        doc_tree = await self._get_document_tree(document.id)

        # Identifier les sections CCTP standards
        cctp_sections = {
            "contexte": self._find_nodes_by_keywords(doc_tree, ["contexte", "objet", "préambule"]),
            "specifications_techniques": self._find_nodes_by_keywords(doc_tree, ["spécifications", "exigences techniques"]),
            "architecture": self._find_nodes_by_keywords(doc_tree, ["architecture", "conception"]),
            "performances": self._find_nodes_by_keywords(doc_tree, ["performances", "sla", "niveau de service"]),
            "securite": self._find_nodes_by_keywords(doc_tree, ["sécurité", "authentification", "rgpd"]),
            "interfaces": self._find_nodes_by_keywords(doc_tree, ["interfaces", "api", "intégration"]),
            "livrables": self._find_nodes_by_keywords(doc_tree, ["livrables", "documentation"]),
            "planning": self._find_nodes_by_keywords(doc_tree, ["planning", "délais", "phases"])
        }

        # Extraction ciblée avec context
        synthesis = {}
        for section_name, nodes in cctp_sections.items():
            if nodes:
                synthesis[section_name] = await self._extract_section_content(nodes)

        return synthesis
```

---

## Phase 6️⃣ : Tables et Éléments Complexes (Jour 13-14)

### 6.1 Extraction avancée des tables
```python
class DoclingTableExtractor:

    async def extract_tables_with_context(self, docling_result):
        """Extrait les tables avec leur contexte."""

        tables_with_context = []

        for table in docling_result.tables:
            # Docling fournit la structure complète
            structured_table = {
                "headers": table.headers,
                "rows": table.data,
                "caption": table.caption,
                "page": table.page_number,
                "bbox": table.bounding_box,

                # Contexte avant/après
                "preceding_text": self._get_preceding_text(table, docling_result),
                "following_text": self._get_following_text(table, docling_result),

                # Type de table détecté
                "table_type": self._classify_table(table)  # "pricing", "requirements", "timeline", etc.
            }

            # Conversion en texte structuré pour embeddings
            table_text = self._table_to_markdown(structured_table)

            # Créer un chunk spécial pour la table
            table_chunk = DocumentChunk(
                chunk_text=table_text,
                metadata={
                    "type": "table",
                    "table_type": structured_table["table_type"],
                    "has_headers": bool(table.headers),
                    "row_count": len(table.data),
                    "column_count": len(table.data[0]) if table.data else 0
                }
            )

            tables_with_context.append(table_chunk)

        return tables_with_context
```

---

## Phase 7️⃣ : Migration Base de Données (Jour 15)

### 7.1 Migration Alembic
```python
# migrations/versions/xxx_add_document_structure.py

def upgrade():
    op.create_table('document_structures',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('tree_json', sa.JSON(), nullable=False),
        sa.Column('total_nodes', sa.Integer()),
        sa.Column('max_depth', sa.Integer()),
        sa.Column('section_count', sa.Integer()),
        sa.Column('sections_index', sa.JSON()),
        sa.Column('created_at', sa.DateTime()),
        sa.ForeignKeyConstraint(['document_id'], ['procurement_documents.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Index pour recherche rapide
    op.create_index('ix_document_structures_document_id', 'document_structures', ['document_id'])

    # Ajouter colonnes à document_embeddings
    op.add_column('document_embeddings',
        sa.Column('node_path', sa.String(500))  # "chapitre_1>article_2>section_3"
    )
    op.add_column('document_embeddings',
        sa.Column('structural_level', sa.Integer())  # Profondeur dans l'arbre
    )
```

---

## Phase 8️⃣ : Tests et Validation (Jour 16-18)

### 8.1 Tests unitaires
```python
# tests/unit/test_docling_processor.py

async def test_docling_extraction():
    processor = DoclingProcessor()

    with open("tests/fixtures/cctp_sample.pdf", "rb") as f:
        content = f.read()

    result = await processor.process_document(content, "cctp_sample.pdf")

    assert result.success
    assert result.document_tree is not None
    assert len(result.structured_content["sections"]) > 0
    assert len(result.structured_content["tables"]) > 0

    # Vérifier la structure hiérarchique
    tree = result.document_tree
    assert tree.type == "document"
    assert any(child.type == "chapter" for child in tree.children)
```

### 8.2 Tests E2E
```python
# scripts/test_e2e_docling_pipeline.py

async def test_full_pipeline_with_docling():
    # 1. Upload document
    response = await client.post("/documents/upload", files={"file": cctp_file})
    doc_id = response.json()["id"]

    # 2. Vérifier extraction Docling
    doc = await get_document(doc_id)
    assert doc["extraction_metadata"]["extraction_method"] == "docling"
    assert doc["extraction_metadata"]["tables_extracted"] > 0

    # 3. Vérifier structure stockée
    structure = await get_document_structure(doc_id)
    assert structure["tree_json"]["type"] == "document"
    assert structure["max_depth"] >= 3

    # 4. Vérifier chunking intelligent
    embeddings = await get_document_embeddings(doc_id)
    assert any(e["metadata"]["node_type"] == "article" for e in embeddings)

    # 5. Test recherche sémantique
    results = await search_similar("spécifications techniques", doc_id)
    assert results[0]["metadata"]["node_type"] in ["article", "section"]
```

---

## Phase 9️⃣ : Monitoring et Optimisation (Jour 19-20)

### 9.1 Métriques Docling
```python
# src/services/monitoring/docling_metrics.py

class DoclingMetrics:

    async def record_extraction(self, document_id: UUID, result: ProcessingResult):
        metrics = {
            "document_id": str(document_id),
            "extraction_time_ms": result.processing_time_ms,
            "sections_detected": len(result.structured_content.get("sections", [])),
            "tables_extracted": len(result.structured_content.get("tables", [])),
            "tree_depth": self._calculate_tree_depth(result.document_tree),
            "node_count": self._count_nodes(result.document_tree),
            "extraction_method": "docling",
            "ocr_used": result.metadata.get("ocr_enabled", False),
            "confidence_score": result.confidence_score
        }

        await self.store_metrics(metrics)
```

### 9.2 Configuration adaptative
```python
# src/services/document/adaptive_processor.py

class AdaptiveProcessorSelector:

    async def select_processor(self, file_content: bytes, filename: str) -> DocumentProcessor:
        """Sélectionne le processeur optimal selon le document."""

        # Analyse rapide du document
        file_size = len(file_content)
        has_images = self._quick_image_check(file_content)
        appears_scanned = self._is_likely_scanned(file_content)

        # Décision
        if appears_scanned:
            # Docling avec OCR pour documents scannés
            processor = DoclingProcessor()
            processor.enable_ocr = True
        elif file_size > 10_000_000:  # > 10MB
            # PyPDF2 pour gros documents simples (plus rapide)
            processor = PDFProcessor()
        else:
            # Docling par défaut pour extraction riche
            processor = DoclingProcessor()

        logger.info(f"Selected {processor.__class__.__name__} for {filename}")
        return processor
```

---

## 🚀 Bénéfices Attendus

1. **Structure hiérarchique complète** → Navigation précise dans le document
2. **Extraction tables avancée** → Données structurées exploitables
3. **Chunking intelligent** → Meilleure pertinence RAG
4. **Contexte préservé** → Réponses plus précises
5. **Support OCR natif** → Documents scannés supportés
6. **Layout multi-colonnes** → Documents complexes gérés
7. **Fallback graceful** → Robustesse maintenue

## 📊 Métriques de Succès

- ✅ 100% documents passent par Docling (sauf fallback)
- ✅ +40% précision extraction requirements
- ✅ +60% tables correctement extraites
- ✅ -30% chunks non pertinents
- ✅ +50% satisfaction recherche sémantique

## ⚠️ Points d'Attention

1. **Performance**: Docling plus lent que PyPDF2 (compenser par cache)
2. **Mémoire**: Documents volumineux peuvent consommer beaucoup de RAM
3. **Dépendances**: Docling a plusieurs dépendances lourdes
4. **Compatibilité**: Tester sur différents formats PDF français

## 📅 Planning de Migration

| Phase | Description | Durée | Priorité |
|-------|-------------|-------|----------|
| Phase 1 | Préparation & Installation | 2 jours | Haute |
| Phase 2 | Amélioration DoclingProcessor | 3 jours | Haute |
| Phase 3 | Intégration Pipeline | 3 jours | Haute |
| Phase 4 | Chunking Intelligent | 2 jours | Moyenne |
| Phase 5 | Extraction CCTP | 2 jours | Moyenne |
| Phase 6 | Tables et Éléments | 2 jours | Moyenne |
| Phase 7 | Migration BD | 1 jour | Haute |
| Phase 8 | Tests et Validation | 3 jours | Haute |
| Phase 9 | Monitoring | 2 jours | Basse |

**Total estimé**: 20 jours

## 🔄 Stratégie de Rollback

En cas de problème, chaque phase peut être annulée indépendamment :

1. **Phase 1-2**: Désinstaller Docling, revenir à PyPDF2
2. **Phase 3**: Modifier ProcessorFactory pour forcer PyPDF2
3. **Phase 4-6**: Désactiver nouvelles fonctionnalités via feature flags
4. **Phase 7**: Migration BD réversible avec `downgrade()`
5. **Phase 8-9**: Tests isolés, pas d'impact production

Le plan est **progressif** et **réversible** à chaque étape, garantissant une migration sans risque vers Docling comme processeur principal.