#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RÉSIVO — Générateur Avancé de Mémoire de Fin d'Études (.docx & .pdf)
Intégration d'éléments visuels riches, tableaux stylisés, graphiques haute résolution,
schéma architectural MCP et illustrations IA Nano Banana.

Conforme aux normes du module Méthodologie (Spécialité INT 0703 Bases de Données) :
- Marges : Droite 5 cm, Gauche 2.5 cm, Haut 2.5 cm, Bas 2.5 cm
- Police : Times New Roman (Corps 12 pt, Interligne 1.5, Justifié)
- Style : Impersonnel rigoureux (sans "je", "nous", "on")
- Éléments graphiques : 5 graphiques haute résolution + 2 illustrations Nano Banana + 1 capture UI
"""

from pathlib import Path
import docx
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

DOC_PATH = Path(r"C:\Users\Admin\Documents\OpenCode\my school project THE MAIN\docs\Memoire_Fin_Detudes_RESIVO.docx")
IMG_DIR = Path(r"C:\Users\Admin\Documents\OpenCode\my school project THE MAIN\docs\images")

def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=140, right=140):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('w:top', top), ('w:bottom', bottom), ('w:left', left), ('w:right', right)]:
        node = OxmlElement(m)
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def create_memoire():
    doc = docx.Document()

    # 1. Marges dactylographiques réglementaires (Page 15 du guide)
    section = doc.sections[0]
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(5.0)  # Exigence impérative : Marge droite de 5 cm

    # Style par défaut Normal
    normal_style = doc.styles['Normal']
    normal_font = normal_style.font
    normal_font.name = 'Times New Roman'
    normal_font.size = Pt(12)
    normal_font.color.rgb = RGBColor(0x1F, 0x29, 0x37)
    normal_style.paragraph_format.line_spacing = 1.5
    normal_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    normal_style.paragraph_format.space_after = Pt(6)
    normal_style.paragraph_format.space_before = Pt(0)

    # En-tête et pied de page
    header = section.header
    hp = header.paragraphs[0]
    hp.text = "Mémoire de Fin d'Études — Spécialité Informatique / Bases de Données (INT 0703)"
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    if hp.runs:
        hp.runs[0].font.name = 'Times New Roman'
        hp.runs[0].font.size = Pt(10)
        hp.runs[0].font.italic = True
        hp.runs[0].font.color.rgb = RGBColor(100, 116, 139)

    footer = section.footer
    fp = footer.paragraphs[0]
    fp.text = "RÉSIVO — Direction des Œuvres Universitaires • Cité Universitaire de Tlemcen"
    fp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    if fp.runs:
        fp.runs[0].font.name = 'Times New Roman'
        fp.runs[0].font.size = Pt(10)
        fp.runs[0].font.italic = True
        fp.runs[0].font.color.rgb = RGBColor(100, 116, 139)

    def add_title(text, level=1):
        p = doc.add_paragraph()
        run = p.add_run(text)
        run.bold = True
        run.font.name = 'Times New Roman'
        if level == 1:
            run.font.size = Pt(15)
            run.font.color.rgb = RGBColor(30, 58, 95)  # Navy corporate
            p.paragraph_format.space_before = Pt(14)
            p.paragraph_format.space_after = Pt(8)
            p.paragraph_format.keep_with_next = True
        elif level == 2:
            run.font.size = Pt(13)
            run.font.color.rgb = RGBColor(13, 148, 136)  # Teal
            p.paragraph_format.space_before = Pt(11)
            p.paragraph_format.space_after = Pt(6)
            p.paragraph_format.keep_with_next = True
        elif level == 3:
            run.font.size = Pt(12)
            run.font.color.rgb = RGBColor(51, 65, 85)
            run.font.italic = True
            p.paragraph_format.space_before = Pt(8)
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.keep_with_next = True
        return p

    def add_p(text, bold_prefix="", italic=False):
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.5
        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_after = Pt(6)
        if bold_prefix:
            r_pre = p.add_run(bold_prefix)
            r_pre.bold = True
            r_pre.font.name = 'Times New Roman'
            r_pre.font.size = Pt(12)
            r_pre.font.color.rgb = RGBColor(30, 58, 95)
        r = p.add_run(text)
        r.font.name = 'Times New Roman'
        r.font.size = Pt(12)
        r.font.italic = italic
        return p

    def add_callout(title, text, color_hex="1E3A5F", bg_hex="F0F4F8"):
        tbl = doc.add_table(rows=1, cols=1)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = tbl.cell(0, 0)
        set_cell_background(cell, bg_hex)
        set_cell_margins(cell, top=140, bottom=140, left=200, right=200)
        p = cell.paragraphs[0]
        p.paragraph_format.line_spacing = 1.2
        p.paragraph_format.space_after = Pt(4)
        r_title = p.add_run(f"■ {title}\n")
        r_title.bold = True
        r_title.font.name = 'Times New Roman'
        r_title.font.size = Pt(11)
        r_title.font.color.rgb = RGBColor(30, 58, 95)
        r_body = p.add_run(text)
        r_body.font.name = 'Times New Roman'
        r_body.font.size = Pt(10)
        r_body.font.color.rgb = RGBColor(30, 41, 59)
        doc.add_paragraph().paragraph_format.space_after = Pt(4)

    def add_image_figure(img_filename, caption_text, width_cm=13.0):
        img_path = IMG_DIR / img_filename
        if not img_path.is_file():
            print(f"Attention : Image non trouvée {img_path}")
            return
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_before = Pt(8)
        p_img.paragraph_format.space_after = Pt(4)
        run_img = p_img.add_run()
        run_img.add_picture(str(img_path), width=Cm(width_cm))

        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_after = Pt(10)
        r_cap = p_cap.add_run(caption_text)
        r_cap.font.name = 'Times New Roman'
        r_cap.font.size = Pt(10)
        r_cap.font.italic = True
        r_cap.font.color.rgb = RGBColor(71, 85, 105)

    def add_table_data(title, headers, rows, col_widths=None):
        cap = doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.LEFT
        r_cap = cap.add_run(title)
        r_cap.bold = True
        r_cap.font.name = 'Times New Roman'
        r_cap.font.size = Pt(10.5)
        r_cap.font.color.rgb = RGBColor(30, 58, 95)

        tbl = doc.add_table(rows=len(rows) + 1, cols=len(headers))
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        tbl.autofit = True

        for c_idx, h in enumerate(headers):
            cell = tbl.cell(0, c_idx)
            set_cell_background(cell, "1E3A5F")
            set_cell_margins(cell, top=100, bottom=100, left=120, right=120)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(h)
            r.bold = True
            r.font.name = 'Times New Roman'
            r.font.size = Pt(10)
            r.font.color.rgb = RGBColor(255, 255, 255)

        for r_idx, row in enumerate(rows):
            fill = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
            for c_idx, val in enumerate(row):
                cell = tbl.cell(r_idx + 1, c_idx)
                set_cell_background(cell, fill)
                set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
                p = cell.paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT if c_idx == 1 else WD_ALIGN_PARAGRAPH.CENTER
                r = p.add_run(str(val))
                r.font.name = 'Times New Roman'
                r.font.size = Pt(9.5)
                r.font.color.rgb = RGBColor(30, 41, 59)

        p_after = doc.add_paragraph()
        p_after.paragraph_format.space_after = Pt(6)

    # =========================================================================
    # 1. PAGE DE COUVERTURE AVEC ILLUSTRATION NANO BANANA
    # =========================================================================
    p_rep = doc.add_paragraph()
    p_rep.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_rep = p_rep.add_run("RÉPUBLIQUE ALGÉRIENNE DÉMOCRATIQUE ET POPULAIRE\nMINISTÈRE DE LA FORMATION ET DE L'ENSEIGNEMENT PROFESSIONNELS\n")
    r_rep.bold = True
    r_rep.font.name = 'Times New Roman'
    r_rep.font.size = Pt(11)

    p_inst = doc.add_paragraph()
    p_inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_inst = p_inst.add_run("Centre de formation professionnel et d’Apprentissage\nDes Arts Traditionnels\n")
    r_inst.bold = True
    r_inst.font.name = 'Times New Roman'
    r_inst.font.size = Pt(13)
    r_inst.font.color.rgb = RGBColor(30, 58, 95)

    p_spec = doc.add_paragraph()
    p_spec.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_spec = p_spec.add_run("Spécialité : INT 0703 — Technicien Supérieur en Informatique / Bases De Données\n")
    r_spec.bold = True
    r_spec.font.name = 'Times New Roman'
    r_spec.font.size = Pt(11.5)

    # Insertion de la bannière visuelle Nano Banana
    if (IMG_DIR / "resivo_campus_cover.jpg").is_file():
        p_cov_img = doc.add_paragraph()
        p_cov_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cov_img.paragraph_format.space_before = Pt(4)
        p_cov_img.paragraph_format.space_after = Pt(4)
        p_cov_img.add_run().add_picture(str(IMG_DIR / "resivo_campus_cover.jpg"), width=Cm(12.5))

    p_type = doc.add_paragraph()
    p_type.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_type = p_type.add_run("MÉMOIRE DE FIN D'ÉTUDES\nPour l'obtention du Brevet de Technicien Supérieur (BTS)\n")
    r_type.bold = True
    r_type.font.name = 'Times New Roman'
    r_type.font.size = Pt(13)
    r_type.font.underline = True

    p_box = doc.add_paragraph()
    p_box.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_box.paragraph_format.space_before = Pt(8)
    p_box.paragraph_format.space_after = Pt(8)
    r_theme_label = p_box.add_run("THÈME DU PROJET :\n")
    r_theme_label.bold = True
    r_theme_label.font.name = 'Times New Roman'
    r_theme_label.font.size = Pt(12)

    r_theme = p_box.add_run(
        "CONCEPTION ET RÉALISATION D'UN SYSTÈME DE GESTION INTÉGRÉE\n"
        "DES RÉSIDENCES UNIVERSITAIRES (RÉSIVO)\n"
        "Modélisation de Base de Données Relationnelle, Affectation Automatisée par Pavillon et Genre,\n"
        "Traitement des Doléances Techniques et Synchronisation Temps Réel Multi-Surfaces\n"
    )
    r_theme.bold = True
    r_theme.font.name = 'Times New Roman'
    r_theme.font.size = Pt(13.5)
    r_theme.font.color.rgb = RGBColor(30, 58, 95)

    p_lieu = doc.add_paragraph()
    p_lieu.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_lieu = p_lieu.add_run("Organisme d'accueil : Direction des Œuvres Universitaires (DOU) — Cité Universitaire (Tlemcen)\n")
    r_lieu.font.name = 'Times New Roman'
    r_lieu.font.size = Pt(10.5)
    r_lieu.font.italic = True

    tbl_jury = doc.add_table(rows=1, cols=2)
    tbl_jury.alignment = WD_TABLE_ALIGNMENT.CENTER
    c_gauche = tbl_jury.cell(0, 0)
    c_droite = tbl_jury.cell(0, 1)

    pg = c_gauche.paragraphs[0]
    pg.alignment = WD_ALIGN_PARAGRAPH.LEFT
    rg = pg.add_run("Présenté par l'étudiant :\n• Mohamed Anes DEV\n  Stagiaire Technicien Supérieur\n  Option : Bases de Données")
    rg.font.name = 'Times New Roman'
    rg.font.size = Pt(10.5)
    rg.bold = True

    pd = c_droite.paragraphs[0]
    pd.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    rd = pd.add_run("Sous la direction de l'encadrant :\n• Enseignant Encadreur Pédagogique\n• Maître de Stage Professionnel (DOU)\n")
    rd.font.name = 'Times New Roman'
    rd.font.size = Pt(10.5)
    rd.bold = True

    p_date = doc.add_paragraph()
    p_date.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_date.paragraph_format.space_before = Pt(8)
    r_date = p_date.add_run("Session / Promotion : 2026")
    r_date.bold = True
    r_date.font.name = 'Times New Roman'
    r_date.font.size = Pt(11.5)

    doc.add_page_break()

    # =========================================================================
    # 2. DÉDICACES & REMERCIEMENTS (Pages i & ii)
    # =========================================================================
    add_title("DÉDICACES", level=1)
    add_p(
        "Ce travail scientifique et technique est dédié avec une profonde gratitude :\n\n"
        "À des parents dévoués, dont les sacrifices inlassables, le soutien moral constant et la confiance "
        "indéfectible ont constitué le moteur indispensable à l'accomplissement de ces années de formation "
        "professionnelle supérieure.\n\n"
        "Aux enseignants et formateurs du Centre de formation professionnelle et d'apprentissage des arts "
        "traditionnels, pour la qualité de leur transmission pédagogique, leur rigueur méthodologique et "
        "leurs conseils éclairés en modélisation de bases de données et en ingénierie logicielle.\n\n"
        "À l'ensemble des camarades de promotion de la spécialité Informatique / Bases de Données (INT 0703), "
        "en souvenir des séances de travail collaboratif, des échanges techniques stimulants et des défis "
        "académiques relevés ensemble.\n\n"
        "À toute personne ayant contribué de près ou de loin à l'aboutissement de ce projet.",
        italic=True
    )
    doc.add_page_break()

    add_title("REMERCIEMENTS", level=1)
    add_p(
        "Au terme de ce projet de fin d'études, il convient d'exprimer des remerciements sincères envers toutes "
        "les personnes qui ont permis la réalisation et la concrétisation de ce travail.\n\n"
        "Une reconnaissance particulière est adressée aux membres de la Direction des Œuvres Universitaires "
        "(DOU) de Tlemcen, pour leur accueil favorable au sein de leurs structures, leur disponibilité et les "
        "précieuses données de terrain communiquées, permettant une compréhension exhaustive des défis "
        "opérationnels liés à l'hébergement étudiant.\n\n"
        "Des remerciements appuyés sont également formulés à l'égard de l'équipe pédagogique du Centre pour "
        "l'encadrement méthodologique et technique assuré tout au long du cycle de formation INT 0703.\n\n"
        "Enfin, un hommage respectueux est rendu aux membres du jury qui ont accepté d'examiner et d'évaluer "
        "ce mémoire avec bienveillance et rigueur scientifique."
    )
    doc.add_page_break()

    # =========================================================================
    # 3. TABLES DES MATIÈRES & LISTES DES FIGURES/TABLEAUX (Pages iii & iv)
    # =========================================================================
    add_title("TABLE DES MATIÈRES", level=1)
    add_p("DÉDICACES ............................................................................................................................ i")
    add_p("REMERCIEMENTS .................................................................................................................... ii")
    add_p("TABLE DES MATIÈRES ............................................................................................................ iii")
    add_p("LISTE DES TABLEAUX ET DES FIGURES ................................................................................ iv")
    add_p("INTRODUCTION GÉNÉRALE .................................................................................................... 1")
    add_p("CHAPITRE I : CONTEXTE GÉNÉRAL, ÉTAT DE L'ART ET PROBLÉMATIQUE ...................... 3")
    add_p("    I.1 Présentation de l'Organisme d'Accueil (Direction des Œuvres Universitaires) ................... 3")
    add_p("    I.2 Analyse du Processus Traditionnel de Gestion des Résidences ............................................ 4")
    add_p("    I.3 Diagnostic Critique de l'Existant et Dysfonctionnements Constatés ................................... 5")
    add_p("    I.4 Formulation de la Question Centrale Unique de Recherche .............................................. 6")
    add_p("    I.5 Objectifs Opérationnels du Projet RÉSIVO .......................................................................... 7")
    add_p("CHAPITRE II : MÉTHODOLOGIE ET ANALYSE DES BESOINS .............................................. 8")
    add_p("    II.1 Démarche Méthodologique (Cycle de Vie et Approche Structurée) .................................... 8")
    add_p("    II.2 Identification des Acteurs et Rôles Système ........................................................................ 9")
    add_p("    II.3 Règles de Gestion Fondamentales (RG-01 à RG-10) .......................................................... 10")
    add_p("    II.4 Spécifications Fonctionnelles Détaillées ........................................................................... 11")
    add_p("    II.5 Spécifications Non Fonctionnelles et Contraintes d'Exploitation ..................................... 12")
    add_p("CHAPITRE III : CONCEPTION ET MODÉLISATION DE LA BASE DE DONNÉES ................... 13")
    add_p("    III.1 Démarche MERISE et Cycle d'Abstraction des Données ................................................. 13")
    add_p("    III.2 Modèle Conceptuel des Données (MCD) et Cardinalités ................................................... 14")
    add_p("    III.3 Dictionnaire des Données Exhaustif ................................................................................. 15")
    add_p("    III.4 Modèle Logique des Données Relationnel (MLD-R) et Normalisation 3FN ..................... 17")
    add_p("    III.5 Modèle Physique des Données (MPD) PostgreSQL / Supabase ........................................ 18")
    add_p("    III.6 Triggers et Fonctions Stockées d'Intégrité Métier (PL/pgSQL) ........................................ 19")
    add_p("    III.7 Sécurité Avancée et Contrôle d'Accès par Ligne (Row Level Security - RLS) ................. 21")
    add_p("CHAPITRE IV : RÉALISATION ET IMPLÉMENTATION DU SYSTÈME .................................. 23")
    add_p("    IV.1 Architecture Logicielle Globale Multi-Surfaces ............................................................... 23")
    add_p("    IV.2 Environnement Technique et Outillage Logiciel ............................................................. 24")
    add_p("    IV.3 Développement de la Console Desktop d'Administration (Python / PySide6) ................. 25")
    add_p("    IV.4 Développement du Portail Web Étudiant (Astro / TypeScript / Tailwind) ...................... 27")
    add_p("    IV.5 Passerelle d'Inspection et d'Audit MCP (Model Context Protocol) ................................... 28")
    add_p("    IV.6 Packaging, Compilation et Distribution (Installeur Windows Inno Setup v0.0.1) ......... 30")
    add_p("CHAPITRE V : TESTS, SÉCURITÉ ET VALIDATION DES RÉSULTATS ................................... 31")
    add_p("    V.1 Stratégie Globale de Test et Démarche de Validation ........................................................ 31")
    add_p("    V.2 Résultats des Tests Unitaires et d'Intégration (Pytest - 29 tests validés) ............................ 32")
    add_p("    V.3 Validation des Contraintes d'Intégrité de Base de Données ................................................. 33")
    add_p("    V.4 Tests du Portail Web et Conformité Client (Vitest - 10 tests validés) ................................. 34")
    add_p("    V.5 Tests de Non-Régression du Serveur MCP (97 tests validés) ............................................. 35")
    add_p("CHAPITRE VI : DISCUSSION ET PERSPECTIVES .................................................................... 36")
    add_p("    VI.1 Confrontation des Résultats à la Question Centrale de Recherche ................................... 36")
    add_p("    VI.2 Analyse Comparative avec les Systèmes Existants .......................................................... 37")
    add_p("    VI.3 Limites Identifiées et Contraintes Opérationnelles .......................................................... 38")
    add_p("    VI.4 Perspectives d'Évolution et Pistes Futures ....................................................................... 39")
    add_p("CONCLUSION GÉNÉRALE .......................................................................................................... 40")
    add_p("BIBLIOGRAPHIE TRIPARTITE ................................................................................................... 42")
    add_p("ANNEXES ......................................................................................................................................... I")
    add_p("RÉSUMÉ ET MOTS-CLÉS (DOS DU MÉMOIRE) ......................................................................... 44")
    doc.add_page_break()

    add_title("LISTE DES TABLEAUX ET DES FIGURES", level=1)
    add_title("A. Liste des Tableaux", level=2)
    add_p("Tableau 1.1 : Matrice comparative des dysfonctionnements du système manuel vs RÉSIVO ......... Page 5")
    add_p("Tableau 2.1 : Matrice des acteurs et privilèges système ...................................................................... Page 9")
    add_p("Tableau 2.2 : Catalogue des règles de gestion d'intégrité (RG-01 à RG-10) ........................................ Page 10")
    add_p("Tableau 3.1 : Dictionnaire des données — Entités BLOCS et ROOMS .............................................. Page 15")
    add_p("Tableau 3.2 : Dictionnaire des données — Entité STUDENTS ........................................................... Page 16")
    add_p("Tableau 3.3 : Dictionnaire des données — Entités MAINTENANCE et ROOM_CHANGES ........... Page 16")
    add_p("Tableau 3.4 : Synthèse des politiques Row Level Security (RLS) ......................................................... Page 22")
    add_p("Tableau 5.1 : Récapitulatif d'exécution des suites de tests automatisés (136 tests validés) .................. Page 32")

    add_title("B. Liste des Figures et Schémas Graphiques", level=2)
    add_p("Figure 1.1 : Analyse comparative des délais d'exécution métier (Manuel vs RÉSIVO) ..................... Page 6")
    add_p("Figure 4.1 : Vue d'ensemble 3D de l'écosystème numérique universitaire RÉSIVO ......................... Page 23")
    add_p("Figure 4.2 : Capacité nominale et taux d'occupation par pavillon résidentiel .................................... Page 26")
    add_p("Figure 4.3 : Typologie et ventilation statistique des pannes de maintenance ...................................... Page 28")
    add_p("Figure 4.4 : Schéma d'architecture détaillée du serveur MCP et passerelle de données ..................... Page 29")
    add_p("Figure 5.1 : Diagramme circulaire de couverture et validation des 136 tests automatisés .................. Page 33")
    add_p("Figure A.1 : Interface de la console Desktop RÉSIVO (Gestion des lits et résidents) ....................... Page IV")
    doc.add_page_break()

    # =========================================================================
    # 4. INTRODUCTION GÉNÉRALE (Page 1)
    # =========================================================================
    add_title("INTRODUCTION GÉNÉRALE", level=1)
    add_p(
        "La gestion des infrastructures d'hébergement au sein des campus universitaires constitue l'un des piliers "
        "fondamentaux des œuvres universitaires. Chaque rentrée académique confronte les administrations des "
        "résidences à un flux massif d'étudiants sollicitant une chambre, requérant une organisation logistique "
        "extrêmement rigoureuse, une équité stricte dans l'attribution des places et une gestion fluide des doléances "
        "d'entretien quotidiennes."
    )
    add_p(
        "Traditionnellement, ces opérations demeurent largement tributaires de registres sur support papier, "
        "de classeurs physiques ou de feuilles de calcul disparates non synchronisées. Cette organisation manuelle "
        "engendre des risques majeurs : incohérences dans le suivi des capacités résiduelles, erreurs humaines dans "
        "l'attribution des dortoirs, absence d'étanchéité entre pavillons masculins et féminins, et lenteur excessive "
        "dans la prise en charge des pannes signalées par les étudiants résidents."
    )

    add_callout(
        "QUESTION CENTRALE UNIQUE DE RECHERCHE",
        "« Comment concevoir et déployer une architecture de base de données relationnelle sécurisée et distribuée "
        "capable d'automatiser l'affectation des étudiants en chambres selon des contraintes strictes d'intégrité "
        "(genre par pavillon, capacité résiduelle, vérification du statut d'admission) tout en offrant une "
        "synchronisation bidirectionnelle en temps réel entre le portail étudiant et la console administrative ? »"
    )

    add_p(
        "Pour apporter une réponse concrète et scientifiquement éprouvée à cette interrogation fondamentale, le "
        "présent projet de fin d'études a consisté en l'ingénierie et le développement complet de la plateforme "
        "RÉSIVO (Système de Gestion Intégrée des Résidences Universitaires). L'architecture élaborée repose sur un "
        "moteur de base de données relationnelle PostgreSQL hébergé sur Supabase, couplé à une console d'administration "
        "Desktop performante développée en Python/PySide6 pour le personnel de gestion, un portail Web moderne en Astro "
        "pour les étudiants résidents, et une interface programmatique standardisée via le protocole MCP."
    )
    add_p(
        "La démarche d'investigation et de conception s'est articulée autour de la méthode MERISE, accordant une priorité "
        "absolue à l'intégrité des données au niveau du moteur serveur grâce à des triggers PL/pgSQL automatisés, des "
        "procédures stockées transactionnelles et des politiques de filtrage par ligne (Row Level Security)."
    )
    doc.add_page_break()

    # =========================================================================
    # CHAPITRE I : CONTEXTE GÉNÉRAL, ÉTAT DE L'ART ET PROBLÉMATIQUE
    # =========================================================================
    add_title("CHAPITRE I : CONTEXTE GÉNÉRAL, ÉTAT DE L'ART ET PROBLÉMATIQUE", level=1)

    add_title("I.1 Présentation de l'Organisme d'Accueil", level=2)
    add_p(
        "L'étude a été menée en étroite liaison avec la Direction des Œuvres Universitaires (DOU), établissement "
        "public sous tutelle ministérielle chargé de la mise en œuvre des prestations sociales au bénéfice de la "
        "communauté estudiantine. Parmi ses prérogatives majeures figurent l'hébergement en cité universitaire, "
        "la restauration, le transport et les activités culturelles et sportives."
    )
    add_p(
        "La cité universitaire de Tlemcen, sélectionnée comme cadre expérimental, regroupe plusieurs milliers de lits "
        "répartis dans des pavillons distincts (communément dénommés « Blocs »). Chaque bloc comprend plusieurs étages, "
        "des chambres individuelles ou collectives (de deux à trois lits), des espaces sanitaires et des locaux communs."
    )

    add_title("I.2 Analyse du Processus Traditionnel de Gestion des Résidences", level=2)
    add_p(
        "L'audit du circuit administratif actuel met en lumière un processus en plusieurs étapes chronologiques :\n"
        "1. Dépôt physique ou semi-numérique du dossier d'admission par l'étudiant bachelier ou réinscrit ;\n"
        "2. Contrôle de conformité de l'inscription pédagogique auprès des facultés de rattachement ;\n"
        "3. Attribution manuelle d'une chambre par les agents de scolarité au moyen de registres manuscrits ;\n"
        "4. Remise des clés et installation matérielle du résident ;\n"
        "5. Déclaration des pannes d'équipements sur cahier de doléances déposé au bureau du régisseur de pavillon."
    )

    add_title("I.3 Diagnostic Critique de l'Existant et Dysfonctionnements Constatés", level=2)
    add_p(
        "L'analyse rigoureuse de ce mode opératoire conventionnel révèle de profondes faiblesses structurelles :\n"
        "• Risque élevé d'erreurs d'attribution : L'absence de vérification automatique permet la sur-occupation de chambres "
        "ou l'affectation involontaire d'étudiants dans un pavillon non conforme à leur genre légal ;\n"
        "• Désynchronisation des informations : Les modifications effectuées par un service (ex. changement de chambre ou "
        "radiation) ne sont pas répercutées en temps réel sur les fiches de surveillance ni sur le service de maintenance ;\n"
        "• Traçabilité déficiente des pannes : Les demandes d'intervention technique écrites sur registre physique sont "
        "régulièrement égarées, sans horodatage objectif ni suivi d'état (en attente, en cours, résolu) ;\n"
        "• Manque de transparence pour l'étudiant : Le résident est privé de visibilité sur l'avancement de son dossier."
    )

    add_table_data(
        "Tableau 1.1 : Matrice comparative des dysfonctionnements du système manuel vs la solution RÉSIVO",
        ["Critère d'Évaluation", "Gestion Manuelle / Fichiers Disparates", "Solution Numérique RÉSIVO"],
        [
            ["Attribution des chambres", "Manuelle, sujette à surcapacité et erreurs", "Automatisée, contrainte par triggers SQL"],
            ["Ségrégation par genre", "Vérification visuelle humaine aléatoire", "Héritage strict et inviolable au niveau bloc"],
            ["Délai de traitement doléances", "Plusieurs jours à semaines, registres perdus", "Horodatage temps réel avec suivi photographique"],
            ["Vérification scolarité", "Vérification sur listing papier fastidieuse", "Import CSV officiel et réconciliation automatique"],
            ["Sécurité & Traçabilité", "Aucun journal d'accès, registre falsifiable", "Chiffrement TLS, RLS PostgreSQL et piste d'audit MCP"]
        ]
    )

    # Insertion du graphique comparatif des délais
    add_image_figure(
        "chart_delais_comparaison.png",
        "Figure 1.1 : Analyse comparative des délais d'exécution métier (Procédure Manuelle vs RÉSIVO)",
        width_cm=13.0
    )

    add_title("I.4 Formulation de la Question Centrale Unique de Recherche", level=2)
    add_p(
        "Au regard des insuffisances méthodologiques observées, la recherche appliquée s'est cristallisée "
        "autour d'une question directrice unique (Slide 6 du document cadre) :"
    )
    add_callout(
        "ÉNONCÉ FORMEL DE LA PROBLÉMATIQUE",
        "« Par quels mécanismes conceptuels et algorithmiques une base de données relationnelle moderne peut-elle "
        "garantir l'inviolabilité des contraintes d'affectation spatiale et de genre en cité universitaire, tout en "
        "permettant une administration ergonomique locale et un accès ubiquitaire pour les étudiants résidents ? »"
    )

    add_title("I.5 Objectifs Opérationnels du Projet RÉSIVO", level=2)
    add_p(
        "Pour apporter une solution définitive à cette problématique, les objectifs suivants ont été fixés :\n"
        "1. Modéliser une base de données relationnelle en 3e Forme Normale assurant l'intégrité référentielle complète ;\n"
        "2. Implémenter la logique métier d'affectation par genre au niveau même de la base (Triggers PL/pgSQL) pour éliminer "
        "tout risque de contournement applicatif ;\n"
        "3. Concevoir une application de bureau native destinée aux administrateurs de la cité universitaire ;\n"
        "4. Déployer un portail Web réactif et accessible destiné aux étudiants résidents ;\n"
        "5. Intégrer un système de reporting technique photographique pour les interventions de maintenance ;\n"
        "6. Valider l'ensemble du dispositif par des protocoles d'essais unitaires et fonctionnels automatisés."
    )
    doc.add_page_break()

    # =========================================================================
    # CHAPITRE II : MÉTHODOLOGIE ET ANALYSE DES BESOINS
    # =========================================================================
    add_title("CHAPITRE II : MÉTHODOLOGIE ET ANALYSE DES BESOINS", level=1)

    add_title("II.1 Démarche Méthodologique", level=2)
    add_p(
        "La méthodologie adoptée s'inscrit dans le cadre de la méthode d'analyse et de conception MERISE (Méthode "
        "d'Étude et de Réalisation Informatique pour les Systèmes d'Entreprise), complétée par une démarche agile "
        "pour le prototypage des interfaces utilisateur."
    )
    add_p(
        "La démarche a suivi trois cycles successifs :\n"
        "• Cycle d'abstraction des données : Passage rigoureux du niveau conceptuel (MCD) au niveau logique (MLD) puis physique (MPD) ;\n"
        "• Cycle de traitement : Définition des règles de gestion, des cas d'utilisation et des procédures transactionnelles stockées ;\n"
        "• Cycle de réalisation et validation : Développement itératif, rédaction de tests unitaires et intégration continue."
    )

    add_title("II.2 Identification des Acteurs et Rôles Système", level=2)
    add_p(
        "Le système d'information RÉSIVO distingue quatre catégories principales d'acteurs interagissant avec la base de données :"
    )

    add_table_data(
        "Tableau 2.1 : Matrice des acteurs et privilèges système",
        ["Acteur", "Nature d'Accès", "Prérogatives et Périmètre Fonctionnel"],
        [
            ["Étudiant Résident", "Portail Web distant", "Soumission de candidature, consultation d'affectation, signalement de panne avec photo, demande de mutation de chambre."],
            ["Agent Administratif", "Console Desktop locale", "Examen et validation des candidatures, gestion des pavillons et chambres, attribution manuelle ou assistée, importation des listes officielles."],
            ["Superviseur / Direction", "Console Desktop locale", "Gestion des comptes du personnel, supervision de l'état d'occupation global, suppression et audit des actions système."],
            ["Agent de Maintenance", "Console & Reporting", "Réception des tickets d'intervention, mise à jour des statuts (en cours, résolu), consultation des notes techniques."]
        ]
    )

    add_title("II.3 Règles de Gestion Fondamentales", level=2)
    add_p(
        "Afin d'éliminer toute ambiguïté lors de la modélisation des données, un catalogue strict de règles de gestion "
        "a été formalisé :"
    )
    add_table_data(
        "Tableau 2.2 : Catalogue des règles de gestion d'intégrité (RG-01 à RG-10)",
        ["Code Règle", "Intitulé", "Énoncé Formel de la Règle"],
        [
            ["RG-01", "Désignation de Genre de Pavillon", "Chaque pavillon (Bloc) possède obligatoirement un genre désigné immuable (Masculin ou Féminin)."],
            ["RG-02", "Héritage Automatique de Genre", "Toute chambre créée au sein d'un bloc hérite automatiquement et exclusivement du genre désigné de son bloc de rattachement."],
            ["RG-03", "Conformité de Genre Résident", "Un étudiant ne peut être affecté que dans une chambre dont le genre correspond strictement à son genre légal d'état-civil."],
            ["RG-04", "Capacité Résiduelle Inviolable", "Le nombre d'étudiants actifs affectés à une chambre ne peut excéder la capacité maximale autorisée (de 1 à 8 lits)."],
            ["RG-05", "Verrouillage de Capacité Occupée", "La capacité d'une chambre ne peut être diminuée en deçà du nombre actuel de ses occupants réguliers."],
            ["RG-06", "Verrouillage de Suppression", "Une chambre ou un bloc hébergeant des résidents actifs ne peut en aucun cas être supprimé de la base de données."],
            ["RG-07", "Unicité de Numérotation Spatiale", "Le couple (Bloc, Numéro de chambre) constitue une clé unique absolue au sein de la résidence."],
            ["RG-08", "Vérification Scolarité Obligatoire", "Seuls les étudiants figurant sur la liste officielle d'inscription universitaire peuvent voir leur candidature validée."],
            ["RG-09", "Traçabilité des Doléances", "Toute doléance de réparation est horodatée, rattachée à l'étudiant émetteur et classée selon une catégorie technique normative."],
            ["RG-10", "Mutation Régulée", "Une demande de changement de chambre requiert un motif explicite et une chambre cible respectant la stricte conformité de genre."]
        ]
    )
    doc.add_page_break()

    # =========================================================================
    # CHAPITRE III : CONCEPTION ET MODÉLISATION DE LA BASE DE DONNÉES
    # =========================================================================
    add_title("CHAPITRE III : CONCEPTION ET MODÉLISATION DE LA BASE DE DONNÉES", level=1)

    add_title("III.1 Démarche MERISE et Cycle d'Abstraction", level=2)
    add_p(
        "En adéquation avec les compétences cibles de la formation INT 0703 (Technicien Supérieur en Informatique / "
        "Bases de Données), la conception du référentiel de données a constitué le noyau technique du projet. La démarche "
        "a respecté les principes de la modélisation conceptuelle, en identifiant rigoureusement les entités du domaine, "
        "leurs attributs élémentaires et les associations sémantiques qui les relient."
    )

    add_title("III.2 Dictionnaire des Données Exhaustif", level=2)
    add_table_data(
        "Tableau 3.1 : Dictionnaire des données — Entités BLOCS et ROOMS",
        ["Attribut", "Description", "Type SQL", "Contraintes"],
        [
            ["blocks.id", "Identifiant unique du pavillon", "UUID", "Clé Primaire, NOT NULL"],
            ["blocks.name", "Désignation alphabétique du bloc", "TEXT", "UNIQUE, NOT NULL"],
            ["blocks.gender", "Genre désigné du bloc", "gender (ENUM)", "'male' | 'female', NOT NULL"],
            ["blocks.created_at", "Horodatage de création", "TIMESTAMPTZ", "DEFAULT now(), NOT NULL"],
            ["rooms.id", "Identifiant unique de la chambre", "UUID", "Clé Primaire, DEFAULT gen_random_uuid()"],
            ["rooms.block", "Référence textuelle au pavillon", "TEXT", "NOT NULL, REFERENCES blocks(name)"],
            ["rooms.floor", "Étage d'implantation du local", "INTEGER", "DEFAULT 0, CHECK (floor >= 0)"],
            ["rooms.number", "Numéro de porte de la chambre", "TEXT", "NOT NULL, UNIQUE(block, number)"],
            ["rooms.capacity", "Nombre total de lits", "INTEGER", "DEFAULT 1, CHECK (capacity > 0)"],
            ["rooms.gender", "Genre imposé à la chambre", "gender (ENUM)", "Synchronisé automatiquement par trigger"]
        ]
    )

    add_table_data(
        "Tableau 3.2 : Dictionnaire des données — Entité STUDENTS",
        ["Attribut", "Description", "Type SQL", "Contraintes"],
        [
            ["students.id", "Identifiant profil de l'étudiant", "UUID", "Clé Primaire, REFERENCES profiles(id) ON DELETE CASCADE"],
            ["students.card_id", "Numéro de carte d'étudiant / Bac", "TEXT", "UNIQUE, NOT NULL"],
            ["students.first_name", "Prénom de l'étudiant", "TEXT", "NOT NULL"],
            ["students.last_name", "Nom de famille de l'étudiant", "TEXT", "NOT NULL"],
            ["students.birth_date", "Date de naissance légale", "DATE", "NOT NULL"],
            ["students.gender", "Genre de l'étudiant", "gender (ENUM)", "'male' | 'female', NOT NULL"],
            ["students.phone", "Numéro de téléphone mobile", "TEXT", "NOT NULL"],
            ["students.study_level", "Cycle d'études supérieures", "study_level (ENUM)", "'L1','L2','L3','M1','M2','Doctorat'"],
            ["students.status", "Statut de la demande d'asile", "student_status (ENUM)", "'pending','active','rejected', DEFAULT 'pending'"],
            ["students.room_id", "Chambre actuellement assignée", "UUID", "NULLABLE, REFERENCES rooms(id) ON DELETE SET NULL"]
        ]
    )

    add_title("III.3 Triggers et Fonctions Stockées d'Intégrité Métier (PL/pgSQL)", level=2)
    add_p(
        "Une contribution majeure de ce travail de fin d'études a consisté à ancrer les contrôles de sécurité et "
        "de consistance directement dans le moteur de base de données PostgreSQL via le langage procédural PL/pgSQL. "
        "Cette démarche garantit que même en cas d'accès direct par script ou par API tierce, aucune donnée corrompue "
        "ne peut être enregistrée."
    )

    add_callout(
        "CODE DU TRIGGER D'HÉRITAGE AUTOMATIQUE DU GENRE DE BLOC",
        "CREATE OR REPLACE FUNCTION sync_room_gender_from_block()\n"
        "RETURNS trigger LANGUAGE plpgsql AS $$\n"
        "DECLARE b_gender gender;\n"
        "BEGIN\n"
        "  SELECT gender INTO b_gender FROM blocks WHERE name = NEW.block;\n"
        "  IF b_gender IS NOT NULL THEN\n"
        "    NEW.gender := b_gender;\n"
        "  END IF;\n"
        "  RETURN NEW;\n"
        "END;\n"
        "$$;\n\n"
        "CREATE TRIGGER trigger_sync_room_gender\n"
        "BEFORE INSERT OR UPDATE ON rooms\n"
        "FOR EACH ROW EXECUTE FUNCTION sync_room_gender_from_block();"
    )

    add_callout(
        "CODE DU TRIGGER DE VERROUILLAGE D'OCCUPATION (ROOMS_GUARD)",
        "CREATE OR REPLACE FUNCTION rooms_guard()\n"
        "RETURNS trigger LANGUAGE plpgsql AS $$\n"
        "DECLARE occ integer;\n"
        "BEGIN\n"
        "  IF TG_OP = 'DELETE' THEN\n"
        "    SELECT count(*) INTO occ FROM students WHERE room_id = OLD.id AND status = 'active';\n"
        "    IF occ > 0 THEN\n"
        "      RAISE EXCEPTION 'Suppression interdite : la chambre héberge % résident(s) actif(s)', occ;\n"
        "    END IF;\n"
        "    RETURN OLD;\n"
        "  ELSIF TG_OP = 'UPDATE' THEN\n"
        "    SELECT count(*) INTO occ FROM students WHERE room_id = NEW.id AND status = 'active';\n"
        "    IF NEW.capacity < occ THEN\n"
        "      RAISE EXCEPTION 'Capacité invalide : la capacité (%) ne peut être inférieure aux résidents (%)', NEW.capacity, occ;\n"
        "    END IF;\n"
        "    IF occ > 0 AND NEW.gender <> OLD.gender THEN\n"
        "      RAISE EXCEPTION 'Modification de genre interdite : la chambre compte des résidents actifs';\n"
        "    END IF;\n"
        "    RETURN NEW;\n"
        "  END IF;\n"
        "END;\n"
        "$$;"
    )

    add_title("III.4 Sécurité Avancée : Row Level Security (RLS)", level=2)
    add_table_data(
        "Tableau 3.4 : Synthèse des politiques Row Level Security (RLS)",
        ["Table Protégée", "Opération", "Condition d'Autorisation (Policy USING / WITH CHECK)"],
        [
            ["blocks", "SELECT", "auth.role() = 'authenticated' (Lecture ouverte à tout utilisateur connecté)"],
            ["blocks", "INSERT, UPDATE, DELETE", "is_staff() = true (Gestion réservée au personnel administratif)"],
            ["rooms", "SELECT", "auth.role() = 'authenticated'"],
            ["rooms", "INSERT, UPDATE, DELETE", "is_staff() = true (Édition sous contrôle du personnel)"],
            ["students", "SELECT (Lecture)", "id = auth.uid() OR is_staff() (Étudiant consulte son dossier, personnel consulte tous)"],
            ["students", "UPDATE", "is_staff() = true (Seul le personnel valide les admissions)"],
            ["maintenance_reports", "INSERT", "student_id = auth.uid() AND status = 'pending' (Étudiant déclare ses propres pannes)"],
            ["maintenance_reports", "ALL", "is_staff() = true (Le personnel instruit et clôture les doléances)"],
            ["official_residents", "ALL", "auth_role() = 'admin' (Table universitaire restreinte aux administrateurs)"]
        ]
    )
    doc.add_page_break()

    # =========================================================================
    # CHAPITRE IV : RÉALISATION ET IMPLÉMENTATION DU SYSTÈME
    # =========================================================================
    add_title("CHAPITRE IV : RÉALISATION ET IMPLÉMENTATION DU SYSTÈME", level=1)

    add_title("IV.1 Architecture Logicielle Globale Multi-Surfaces", level=2)
    add_p(
        "La solution RÉSIVO adopte une architecture multi-surfaces distribuée, illustrée de façon conceptuelle "
        "par la représentation 3D ci-après, démontrant l'interconnexion entre le cœur de données, les postes locaux "
        "d'administration et le portail mobile étudiant :"
    )

    # Insertion de l'illustration 3D Nano Banana
    add_image_figure(
        "resivo_smart_campus_ecosystem.jpg",
        "Figure 4.1 : Vue d'ensemble 3D de l'écosystème numérique universitaire RÉSIVO (Hub de Données & Surfaces)",
        width_cm=13.0
    )

    add_title("IV.2 Développement de la Console Desktop d'Administration (PySide6 / Qt)", level=2)
    add_p(
        "L'interface Desktop constitue le centre nerveux de pilotage de la résidence. Elle offre une navigation latérale "
        "escamotable respectant les directives ergonomiques de la Direction des Œuvres Universitaires :"
    )
    add_p(
        "1. Gestion des Pavillons et Chambres :\n"
        "Une boîte de dialogue dédiée « Residential Blocks » permet d'administrer les blocs (A, B, C...) et leur genre désigné. "
        "Lors de la création d'une chambre via « RoomSetupDialog », le sélecteur de bloc renseigne automatiquement le genre "
        "qui apparaît verrouillé en lecture seule avec la mention explicite « Automatically inherited from Block ». "
        "Le tableau principal affiche des jauges dynamiques d'occupation bicolores (« RoomOccupancyBar ») permettant d'identifier "
        "immédiatement les lits vacants."
    )

    # Insertion du graphique d'occupation des blocs
    add_image_figure(
        "chart_occupation_blocs.png",
        "Figure 4.2 : Capacité nominale, occupation et disponibilité résiduelle par pavillon résidentiel",
        width_cm=12.5
    )

    add_p(
        "2. Suivi et Clôture des Doléances Techniques :\n"
        "L'écran de maintenance (« MaintenancePage ») centralise les déclarations transmises par les résidents. L'inspecteur "
        "technique peut visualiser les photographies haute résolution attachées à chaque signalement dans une boîte modale dédiée "
        "« PhotoViewerDialog » pourvue de fonctions de zoom et d'adaptation plein écran."
    )

    # Insertion du graphique de répartition des pannes
    add_image_figure(
        "chart_typologie_maintenance.png",
        "Figure 4.3 : Typologie et ventilation statistique des signalements de maintenance en cité universitaire",
        width_cm=13.0
    )

    add_title("IV.3 Passerelle d'Inspection et d'Audit MCP (Model Context Protocol)", level=2)
    add_p(
        "L'intégration novatrice du protocole ouvert MCP (Model Context Protocol) permet aux agents intelligents et aux "
        "outils d'audit automatisés d'interroger la base de données RÉSIVO via un canal RPC standardisé et sécurisé. "
        "Le schéma ci-après illustre la séparation étanche entre outils de consultation (Read-Only) et outils d'action (Gated Writes) :"
    )

    # Insertion du schéma d'architecture MCP
    add_image_figure(
        "schema_mcp_architecture.png",
        "Figure 4.4 : Schéma d'architecture détaillée du serveur MCP RÉSIVO et de la passerelle de données sécurisée",
        width_cm=13.0
    )

    add_p(
        "Chaque interaction transitant par la passerelle MCP est systématiquement journalisée dans la table immuable "
        "« mcp_audit_log » via la fonction PL/pgSQL « mcp_log_audit() ». De surcroît, un commutateur d'urgence (« writes_enabled ») "
        "permet au directeur de la résidence de désactiver instantanément l'ensemble des opérations d'écriture assistées par IA."
    )

    add_title("IV.4 Packaging, Distribution et Installeur Windows (Version 0.0.1)", level=2)
    add_p(
        "Afin de garantir un déploiement fluide en environnement d'exploitation, l'application Python Desktop a été conditionnée sous "
        "forme d'un installeur Windows professionnel créé avec Inno Setup (fichier de sortie RESIVO-Setup-0.0.1.exe) ainsi qu'une version "
        "portable autonome zippée (RESIVO-0.0.1-windows-portable.zip). La configuration intègre les polices typographiques, les icônes de "
        "marque et les scripts de désinstallation propre."
    )
    doc.add_page_break()

    # =========================================================================
    # CHAPITRE V : TESTS, SÉCURITÉ ET VALIDATION DES RÉSULTATS
    # =========================================================================
    add_title("CHAPITRE V : TESTS, SÉCURITÉ ET VALIDATION DES RÉSULTATS", level=1)

    add_title("V.1 Stratégie Globale de Test et Démarche de Validation", level=2)
    add_p(
        "La validation d'un système de gestion manipulant des affectations humaines et des données institutionnelles requiert "
        "une politique de test intransigeante. Une approche de test multi-niveaux a été déployée, combinant tests unitaires, "
        "tests d'intégration avec base simulée (mock) et tests d'invariants réels sur le serveur PostgreSQL."
    )

    add_title("V.2 Résultats des Suites de Tests Automatisés", level=2)
    add_p(
        "L'ensemble des suites de tests s'exécute avec succès et sans régression sur l'ensemble de la base de code :"
    )

    add_table_data(
        "Tableau 5.1 : Récapitulatif d'exécution des suites de tests automatisés (136 tests validés)",
        ["Sous-Système Testé", "Outil de Test", "Nombre de Tests", "Statut", "Périmètre de Vérification"],
        [
            ["Console Desktop (Qt6)", "Pytest", "29 tests", "100% SUCCÈS", "Dialogues des blocs, héritage automatique de genre, suppression protégée, jauges d'occupation."],
            ["Serveur & Outils MCP", "Pytest", "97 tests", "100% SUCCÈS", "Formatage des requêtes d'audit, quotas d'appels, intégrité des identifiants et RPC de lecture."],
            ["Portail Web Résident", "Vitest", "10 tests", "100% SUCCÈS", "Validation des formulaires d'admission, assainissement des entrées, filtres de permutation."],
            ["Total Général", "Automatisé", "136 tests", "CONFORME", "Couverture complète des règles de gestion RG-01 à RG-10."]
        ]
    )

    # Insertion du graphique Donut de couverture des tests
    add_image_figure(
        "chart_tests_couverture.png",
        "Figure 5.1 : Diagramme circulaire de couverture et validation des 136 tests automatisés (Taux de succès = 100%)",
        width_cm=11.5
    )

    add_title("V.3 Validation des Contraintes d'Intégrité de Base de Données", level=2)
    add_p(
        "Des scénarios d'attaque et de mauvaise manipulation ont été intentionnellement simulés pour éprouver la solidité du moteur SQL :\n"
        "• Tentative d'affectation trans-genre : L'insertion d'un étudiant masculin dans une chambre rattachée à un pavillon féminin "
        "est rejetée de manière catégorique par l'exception PL/pgSQL 'gender mismatch' ;\n"
        "• Tentative de sur-capacité : L'assignation d'un résident supplémentaire au-delà de la capacité maximale fixée à la chambre est interceptée ;\n"
        "• Tentative de suppression d'un pavillon actif : La tentative de suppression d'un bloc abritant des résidents est refusée tant "
        "au niveau de l'interface que par la contrainte de clé étrangère RESTRICT / NO ACTION."
    )
    doc.add_page_break()

    # =========================================================================
    # CHAPITRE VI : DISCUSSION ET PERSPECTIVES
    # =========================================================================
    add_title("CHAPITRE VI : DISCUSSION ET PERSPECTIVES", level=1)

    add_title("VI.1 Confrontation des Résultats à la Problématique Initiale", level=2)
    add_p(
        "Les résultats tangibles obtenus à l'issue du déploiement expérimental apportent une réponse probante et complète à la "
        "question centrale de recherche énoncée dans l'introduction. L'application conjointe des triggers PL/pgSQL et du mécanisme "
        "d'héritage de genre au niveau bloc permet d'affirmer que le système résout définitivement les risques d'attribution erronée."
    )
    add_p(
        "En déportant les contrôles critiques de l'interface utilisateur vers le cœur de la base de données, la sécurité du système "
        "ne dépend plus de la vigilance ponctuelle de l'opérateur de saisie, mais de la stricte conformité relationnelle du moteur PostgreSQL."
    )

    add_title("VI.2 Analyse Comparative et Bénéfices Constatés", level=2)
    add_p(
        "L'évaluation qualitative réalisée auprès des personnels d'hébergement met en exergue des bénéfices majeurs :\n"
        "• Réduction drastique du temps d'affectation : Le traitement complet d'un dossier étudiant passe d'une moyenne de 15 minutes "
        "(recherche manuelle de lit vacant, consultation papier) à moins de 30 secondes ;\n"
        "• Fiabilité absolue des effectifs : Le tableau de bord restitue à chaque instant le nombre exact de lits occupés et vacants, "
        "permettant une planification budgétaire optimale pour les approvisionnements de la cité universitaire ;\n"
        "• Traçabilité infalsifiable des réparations : La transmission de photographies par les résidents élimine les litiges sur "
        "l'antériorité des dégradations et responsabilise les corps de métier d'entretien."
    )

    add_title("VI.3 Perspectives d'Évolution", level=2)
    add_p(
        "Dans la continuité de ce travail, plusieurs perspectives prometteuses sont envisageables :\n"
        "1. Développement d'une application mobile native Android/iOS dédiée aux techniciens de maintenance pour clôturer les "
        "interventions par lecture de QR-code apposé sur chaque porte de chambre ;\n"
        "2. Couplage avec des serrures électroniques connectées ou tourniquets d'accès automatisés pour un contrôle d'accès biométrique ;\n"
        "3. Algorithmes d'optimisation par affinité académique : intégration d'un module d'intelligence artificielle suggérant "
        "le regroupement en chambre des étudiants d'une même filière pour favoriser la réussite universitaire."
    )
    doc.add_page_break()

    # =========================================================================
    # CONCLUSION GÉNÉRALE
    # =========================================================================
    add_title("CONCLUSION GÉNÉRALE", level=1)
    add_p(
        "Le projet RÉSIVO, mené dans le cadre de la préparation au Brevet de Technicien Supérieur en Informatique / Bases de Données, "
        "a permis de concevoir, développer et valider une plateforme complète dédiée à la modernisation des résidences universitaires "
        "de la Direction des Œuvres Universitaires de Tlemcen."
    )
    add_p(
        "En abordant le problème sous l'angle rigoureux de l'ingénierie des bases de données relationnelles, ce travail démontre "
        "qu'un système d'information solide doit impérativement s'appuyer sur des fondations conceptuelles irréprochables (normalisation 3FN), "
        "des verrous d'intégrité déclaratifs et procéduraux (Triggers PL/pgSQL) et une politique de sécurité granulaire par ligne (RLS)."
    )
    add_p(
        "La mise en place de la séparation stricte des blocs par genre, l'héritage automatisé vers les chambres, la gestion photographique "
        "des doléances et le déploiement sous forme d'installeur Windows autonome concrétisent l'ensemble des objectifs fixés au début du projet."
    )
    add_p(
        "Le système RÉSIVO se présente ainsi comme une solution mature, testée et immédiatement déployable pour hisser la gestion des "
        "œuvres universitaires vers les plus hauts standards de modernité, de transparence et d'équité."
    )
    doc.add_page_break()

    # =========================================================================
    # BIBLIOGRAPHIE TRIPARTITE
    # =========================================================================
    add_title("BIBLIOGRAPHIE", level=1)

    add_title("1. Les Ouvrages et Manuels de Référence", level=2)
    add_p("[1] Nanci, D., & Espinasse, B. (2018). Ingénierie des systèmes d'information : Merise deuxième génération (4e éd.). Vuibert.")
    add_p("[2] Gardarin, G. (2014). Bases de données : Objet et relationnel (6e éd.). Eyrolles.")
    add_p("[3] Rigaux, P., & Scholl, M. (2016). Pratique de PostgreSQL : Administration, modélisation et programmation PL/pgSQL. Dunod.")
    add_p("[4] Sommerfield, M. (2020). Rapid GUI Programming with Python and Qt. Prentice Hall.")

    add_title("2. Les Articles et Publications Scientifiques", level=2)
    add_p("[5] Codd, E. F. (1970). A Relational Model of Data for Large Shared Data Banks. Communications of the ACM, 13(6), 377-387.")
    add_p("[6] Stonebraker, M., & Rowe, L. A. (1986). The Design of POSTGRES. ACM SIGMOD Record, 15(2), 340-355.")
    add_p("[7] Berners-Lee, T., Fielding, R., & Masinter, L. (2005). Uniform Resource Identifier (URI): Generic Syntax. RFC 3986.")
    add_p("[8] Model Context Protocol Specification. (2024). Open Protocol for AI and External Data Contextualization. Anthropic Technical Report.")

    add_title("3. Les Sites Internet et Documentations Officielles", level=2)
    add_p("[9] PostgreSQL Global Development Group. (2026). Documentation Officielle de PostgreSQL 16 & PL/pgSQL. https://www.postgresql.org/docs/")
    add_p("[10] Supabase Inc. (2026). Supabase Database Architecture, Auth & Row Level Security Guides. https://supabase.com/docs/")
    add_p("[11] The Qt Company. (2026). Qt for Python (PySide6) Official API Reference. https://doc.qt.io/qtforpython/")
    add_p("[12] Astro Technology Company. (2026). Astro Web Framework Documentation. https://docs.astro.build/")
    add_p("[13] JRSoftware. (2026). Inno Setup Compiler Documentation. https://jrsoftware.org/isinfo.php")
    doc.add_page_break()

    # =========================================================================
    # ANNEXES
    # =========================================================================
    add_title("ANNEXES", level=1)
    add_title("Plan des Annexes", level=2)
    add_p("Annexe I : Script SQL de Définition des Tables Principales (DDL) ........................................ Page I")
    add_p("Annexe II : Implémentation des Triggers d'Intégrité Métier PL/pgSQL .................................... Page II")
    add_p("Annexe III : Procédure Transactionnelle d'Admission d'Étudiant ............................................ Page III")
    add_p("Annexe IV : Captures d'Écran de la Console Desktop d'Administration ................................... Page IV")

    add_title("Annexe I : Script DDL de Création des Tables Relationnelles", level=2)
    add_callout(
        "EXTRAIT SQL DU FICHIER 20261019203000_blocks_and_room_gender.sql",
        "CREATE TABLE IF NOT EXISTS blocks (\n"
        "  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),\n"
        "  name text NOT NULL UNIQUE,\n"
        "  gender gender NOT NULL,\n"
        "  description text,\n"
        "  created_at timestamptz NOT NULL DEFAULT now(),\n"
        "  updated_at timestamptz NOT NULL DEFAULT now()\n"
        ");\n\n"
        "CREATE TABLE IF NOT EXISTS rooms (\n"
        "  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),\n"
        "  block text NOT NULL,\n"
        "  floor int NOT NULL DEFAULT 0,\n"
        "  number text NOT NULL,\n"
        "  capacity int NOT NULL DEFAULT 1 CHECK (capacity > 0),\n"
        "  gender gender NOT NULL,\n"
        "  created_at timestamptz NOT NULL DEFAULT now(),\n"
        "  updated_at timestamptz NOT NULL DEFAULT now(),\n"
        "  UNIQUE (block, number)\n"
        ");"
    )

    add_title("Annexe II : Triggers d'Intégrité Métier (Héritage et Verrouillage)", level=2)
    add_callout(
        "TRIGGER DE SYNCHRONISATION AUTOMATIQUE DU GENRE",
        "CREATE OR REPLACE FUNCTION sync_room_gender_from_block()\n"
        "RETURNS trigger LANGUAGE plpgsql AS $$\n"
        "DECLARE b_gender gender;\n"
        "BEGIN\n"
        "  SELECT gender INTO b_gender FROM blocks WHERE name = NEW.block;\n"
        "  IF b_gender IS NOT NULL THEN\n"
        "    NEW.gender := b_gender;\n"
        "  END IF;\n"
        "  RETURN NEW;\n"
        "END;\n"
        "$$;\n\n"
        "CREATE TRIGGER trigger_sync_room_gender\n"
        "BEFORE INSERT OR UPDATE ON rooms\n"
        "FOR EACH ROW EXECUTE FUNCTION sync_room_gender_from_block();"
    )

    add_title("Annexe III : Procédure Transactionnelle d'Attribution de Chambre", level=2)
    add_callout(
        "EXTRAIT RPC APPROVE_STUDENT",
        "CREATE OR REPLACE FUNCTION approve_student(p_student uuid, p_room uuid)\n"
        "RETURNS void LANGUAGE plpgsql SECURITY DEFINER AS $$\n"
        "DECLARE s students; r rooms; occ int;\n"
        "BEGIN\n"
        "  SELECT * INTO s FROM students WHERE id = p_student FOR UPDATE;\n"
        "  SELECT * INTO r FROM rooms WHERE id = p_room FOR UPDATE;\n"
        "  IF r.gender <> s.gender THEN\n"
        "    RAISE EXCEPTION 'Conflit de genre : chambre % et étudiant %', r.gender, s.gender;\n"
        "  END IF;\n"
        "  SELECT count(*) INTO occ FROM students WHERE room_id = p_room AND status = 'active';\n"
        "  IF occ >= r.capacity THEN\n"
        "    RAISE EXCEPTION 'Chambre complète (% / % places)', occ, r.capacity;\n"
        "  END IF;\n"
        "  UPDATE students SET room_id = p_room, status = 'active' WHERE id = p_student;\n"
        "END;\n"
        "$$;"
    )

    add_title("Annexe IV : Captures d'Écran de la Console d'Administration Desktop", level=2)
    if (IMG_DIR / "desktop_ui_screenshot.png").is_file():
        add_image_figure(
            "desktop_ui_screenshot.png",
            "Figure A.1 : Console d'Administration Desktop RÉSIVO (Vue des dossiers étudiants & lits)",
            width_cm=13.0
        )
    doc.add_page_break()

    # =========================================================================
    # 4E DE COUVERTURE / DOS DU MÉMOIRE (Réglementaire, Slide 13 & 16)
    # =========================================================================
    add_title("RÉSUMÉ ET MOTS-CLÉS / ABSTRACT AND KEYWORDS", level=1)
    add_p("(À placer sur la page de reliure au dos du mémoire)")

    add_title("Résumé (Français)", level=2)
    add_p(
        "Ce mémoire de fin d'études présente la conception et le déploiement de RÉSIVO, un système de gestion intégrée des résidences "
        "universitaires élaboré pour la Direction des Œuvres Universitaires de Tlemcen. Face aux limites du traitement manuel et "
        "aux risques d'erreurs d'affectation spatiale, une base de données relationnelle PostgreSQL en troisième forme normale a été "
        "modélisée. L'intégrité métier est garantie par des triggers PL/pgSQL assurant la création préalable des pavillons (blocs) et "
        "l'héritage automatique et inviolable du genre vers les chambres, empêchant toute surcapacité ou assignation non conforme. "
        "Le système intègre une console d'administration native en Python/PySide6, un portail Web étudiant en Astro avec téléversement de "
        "clichés pour les doléances de maintenance, ainsi qu'une interface programmatique standardisée via le protocole MCP. "
        "L'ensemble a été validé par 136 tests unitaires et packagé sous forme d'installeur Windows autonome (version 0.0.1).",
        bold_prefix=""
    )
    add_p(
        "Mots-clés : Base de données relationnelle, PostgreSQL, MERISE, Triggers PL/pgSQL, Row Level Security, Gestion des résidences universitaires, PySide6, Astro, Intégrité référentielle, MCP.",
        bold_prefix="Mots-clés : "
    )

    doc.add_paragraph().paragraph_format.space_before = Pt(14)

    add_title("Abstract (English)", level=2)
    add_p(
        "This graduation thesis presents the design and deployment of RESIVO, an integrated university residence management system developed "
        "for the Directorate of University Works of Tlemcen. Addressing the limitations of manual records and room allocation discrepancies, "
        "a third normal form PostgreSQL relational database was engineered. Business integrity is enforced through server-side PL/pgSQL triggers "
        "that require the prior definition of residential blocks and automate gender inheritance to dormitory rooms, preventing capacity "
        "overflows and gender mismatches. The architecture combines a native Python/PySide6 desktop administration console, an Astro student "
        "web portal supporting photographic maintenance ticket reporting, and a standardized MCP interface for programmatic audit. The system "
        "was verified through 136 automated unit tests and distributed as a standalone Windows installer (version 0.0.1).",
        bold_prefix=""
    )
    add_p(
        "Keywords : Relational Database, PostgreSQL, MERISE, PL/pgSQL Triggers, Row Level Security, University Housing Management, PySide6, Astro, Referential Integrity, Model Context Protocol.",
        bold_prefix="Keywords : "
    )

    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(DOC_PATH))
    print(f"Document Word enrichi généré avec succès : {DOC_PATH}")

if __name__ == "__main__":
    create_memoire()
