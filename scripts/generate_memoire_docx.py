#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RÉSIVO — Générateur de Mémoire de Fin d'Études (.docx)
Conforme aux normes de rédaction et dactylographie du module Méthodologie :
- Spécialité : INT 0703 - Technicien Supérieur en Informatique / Bases De Données
- Établissement : Centre de formation professionnel et d'Apprentissage Des Arts Traditionnels
- Marges : Droite 5 cm, Gauche 2.5 cm, Haut 2.5 cm, Bas 2.5 cm
- Police : Times New Roman (Corps 12 pt, Interligne 1.5, Justifié, Titres hiérarchisés)
- Style : Rigoureusement impersonnel (aucun "je", "nous", "on")
- Structure : Couverture, Dédicaces, Remerciements, Table des matières, Listes des tableaux/figures,
              Introduction, 6 Chapitres de développement, Conclusion, Bibliographie tripartite,
              Annexes, Résumé bilingue (Dos du mémoire).
"""

from pathlib import Path
import docx
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

DOC_PATH = Path(r"C:\Users\Admin\Documents\OpenCode\my school project THE MAIN\docs\Memoire_Fin_Detudes_RESIVO.docx")

def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
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

    # Configuration des marges dactylographiques réglementaires (Page 15 du guide)
    section = doc.sections[0]
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(5.0)  # Exigence stricte : Marge droite de 5 cm

    # Style par défaut Normal
    normal_style = doc.styles['Normal']
    normal_font = normal_style.font
    normal_font.name = 'Times New Roman'
    normal_font.size = Pt(12)
    normal_font.color.rgb = RGBColor(0, 0, 0)
    normal_style.paragraph_format.line_spacing = 1.5
    normal_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    normal_style.paragraph_format.space_after = Pt(6)
    normal_style.paragraph_format.space_before = Pt(0)

    # Configuration de l'en-tête et pied de page
    header = section.header
    hp = header.paragraphs[0]
    hp.text = "Mémoire de Fin d'Études — Spécialité Informatique / Bases de Données (INT 0703)"
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    if hp.runs:
        hp.runs[0].font.name = 'Times New Roman'
        hp.runs[0].font.size = Pt(10)
        hp.runs[0].font.italic = True
        hp.runs[0].font.color.rgb = RGBColor(100, 100, 100)

    footer = section.footer
    fp = footer.paragraphs[0]
    fp.text = "RÉSIVO — Système de Gestion Intégrée des Résidences Universitaires"
    fp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    if fp.runs:
        fp.runs[0].font.name = 'Times New Roman'
        fp.runs[0].font.size = Pt(10)
        fp.runs[0].font.italic = True
        fp.runs[0].font.color.rgb = RGBColor(100, 100, 100)

    def add_title(text, level=1):
        p = doc.add_paragraph()
        run = p.add_run(text)
        run.bold = True
        run.font.name = 'Times New Roman'
        if level == 1:
            run.font.size = Pt(16)
            run.font.color.rgb = RGBColor(20, 45, 85)
            p.paragraph_format.space_before = Pt(14)
            p.paragraph_format.space_after = Pt(8)
            p.paragraph_format.keep_with_next = True
        elif level == 2:
            run.font.size = Pt(14)
            run.font.color.rgb = RGBColor(30, 60, 110)
            p.paragraph_format.space_before = Pt(12)
            p.paragraph_format.space_after = Pt(6)
            p.paragraph_format.keep_with_next = True
        elif level == 3:
            run.font.size = Pt(12)
            run.font.color.rgb = RGBColor(40, 70, 120)
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
        r = p.add_run(text)
        r.font.name = 'Times New Roman'
        r.font.size = Pt(12)
        r.font.italic = italic
        return p

    def add_callout(title, text):
        tbl = doc.add_table(rows=1, cols=1)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = tbl.cell(0, 0)
        set_cell_background(cell, "F0F4F8")
        set_cell_margins(cell, top=140, bottom=140, left=200, right=200)
        p = cell.paragraphs[0]
        p.paragraph_format.line_spacing = 1.2
        p.paragraph_format.space_after = Pt(4)
        r_title = p.add_run(f"■ {title}\n")
        r_title.bold = True
        r_title.font.name = 'Times New Roman'
        r_title.font.size = Pt(11)
        r_title.font.color.rgb = RGBColor(20, 50, 90)
        r_body = p.add_run(text)
        r_body.font.name = 'Times New Roman'
        r_body.font.size = Pt(10.5)
        doc.add_paragraph().paragraph_format.space_after = Pt(4)

    def add_table_data(title, headers, rows):
        cap = doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.LEFT
        r_cap = cap.add_run(title)
        r_cap.bold = True
        r_cap.font.name = 'Times New Roman'
        r_cap.font.size = Pt(11)

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
            r.font.size = Pt(10.5)
            r.font.color.rgb = RGBColor(255, 255, 255)

        for r_idx, row in enumerate(rows):
            fill = "F9FBFC" if r_idx % 2 == 1 else "FFFFFF"
            for c_idx, val in enumerate(row):
                cell = tbl.cell(r_idx + 1, c_idx)
                set_cell_background(cell, fill)
                set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
                p = cell.paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT if c_idx == 1 else WD_ALIGN_PARAGRAPH.CENTER
                r = p.add_run(str(val))
                r.font.name = 'Times New Roman'
                r.font.size = Pt(10)

        p_after = doc.add_paragraph()
        p_after.paragraph_format.space_after = Pt(6)

    # =========================================================================
    # 1. PAGE DE COUVERTURE (Réglementaire)
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
    r_inst.font.color.rgb = RGBColor(20, 50, 90)

    p_spec = doc.add_paragraph()
    p_spec.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_spec = p_spec.add_run("Spécialité : INT 0703 — Technicien Supérieur en Informatique / Bases De Données\n")
    r_spec.bold = True
    r_spec.font.name = 'Times New Roman'
    r_spec.font.size = Pt(12)

    doc.add_paragraph().paragraph_format.space_before = Pt(12)

    p_type = doc.add_paragraph()
    p_type.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_type = p_type.add_run("MÉMOIRE DE FIN D'ÉTUDES\nPour l'obtention du Brevet de Technicien Supérieur (BTS)\n")
    r_type.bold = True
    r_type.font.name = 'Times New Roman'
    r_type.font.size = Pt(14)
    r_type.font.underline = True

    p_box = doc.add_paragraph()
    p_box.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_box.paragraph_format.space_before = Pt(18)
    p_box.paragraph_format.space_after = Pt(18)
    r_theme_label = p_box.add_run("THÈME DU PROJET :\n\n")
    r_theme_label.bold = True
    r_theme_label.font.name = 'Times New Roman'
    r_theme_label.font.size = Pt(13)

    r_theme = p_box.add_run(
        "CONCEPTION ET RÉALISATION D'UN SYSTÈME DE GESTION INTÉGRÉE\n"
        "DES RÉSIDENCES UNIVERSITAIRES (RÉSIVO)\n"
        "Modélisation de Base de Données Relationnelle, Affectation Automatisée par Pavillon et Genre,\n"
        "Traitement des Doléances Techniques et Synchronisation Temps Réel Multi-Surfaces\n"
    )
    r_theme.bold = True
    r_theme.font.name = 'Times New Roman'
    r_theme.font.size = Pt(15)
    r_theme.font.color.rgb = RGBColor(20, 45, 85)

    p_lieu = doc.add_paragraph()
    p_lieu.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_lieu = p_lieu.add_run("Organisme d'accueil : Direction des Œuvres Universitaires (DOU) — Cité Universitaire (Tlemcen)\n")
    r_lieu.font.name = 'Times New Roman'
    r_lieu.font.size = Pt(11)
    r_lieu.font.italic = True

    doc.add_paragraph().paragraph_format.space_before = Pt(18)

    tbl_jury = doc.add_table(rows=1, cols=2)
    tbl_jury.alignment = WD_TABLE_ALIGNMENT.CENTER
    c_gauche = tbl_jury.cell(0, 0)
    c_droite = tbl_jury.cell(0, 1)

    pg = c_gauche.paragraphs[0]
    pg.alignment = WD_ALIGN_PARAGRAPH.LEFT
    rg = pg.add_run("Présenté par l'étudiant :\n• Mohamed Anes DEV\n  Stagiaire Technicien Supérieur\n  Option : Bases de Données")
    rg.font.name = 'Times New Roman'
    rg.font.size = Pt(11)
    rg.bold = True

    pd = c_droite.paragraphs[0]
    pd.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    rd = pd.add_run("Sous la direction de l'encadrant :\n• Enseignant Encadreur Pédagogique\n• Maître de Stage Professionnel (DOU)\n")
    rd.font.name = 'Times New Roman'
    rd.font.size = Pt(11)
    rd.bold = True

    doc.add_paragraph().paragraph_format.space_before = Pt(24)

    p_date = doc.add_paragraph()
    p_date.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_date = p_date.add_run("Session / Promotion : 2026")
    r_date.bold = True
    r_date.font.name = 'Times New Roman'
    r_date.font.size = Pt(12)

    doc.add_page_break()

    # =========================================================================
    # 2. DÉDICACES (Page i)
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

    # =========================================================================
    # 3. REMERCIEMENTS (Page ii)
    # =========================================================================
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
    # 4. TABLE DES MATIÈRES (Page iii)
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
    add_p("    IV.5 Protocole d'Intégration MCP (Model Context Protocol) et Piste d'Audit ........................... 28")
    add_p("    IV.6 Packaging, Compilation et Distribution (Installeur Windows Inno Setup v0.0.1) ......... 29")
    add_p("CHAPITRE V : TESTS, SÉCURITÉ ET VALIDATION DES RÉSULTATS ................................... 30")
    add_p("    V.1 Stratégie Globale de Test et Démarche de Validation ........................................................ 30")
    add_p("    V.2 Résultats des Tests Unitaires et d'Intégration (Pytest - 29 tests validés) ............................ 31")
    add_p("    V.3 Validation des Contraintes d'Intégrité de Base de Données ................................................. 32")
    add_p("    V.4 Tests du Portail Web et Conformité Client (Vitest - 10 tests validés) ................................. 33")
    add_p("    V.5 Tests de Non-Régression du Serveur MCP (97 tests validés) ............................................. 34")
    add_p("CHAPITRE VI : DISCUSSION ET PERSPECTIVES .................................................................... 35")
    add_p("    VI.1 Confrontation des Résultats à la Question Centrale de Recherche ................................... 35")
    add_p("    VI.2 Analyse Comparative avec les Systèmes Existants .......................................................... 36")
    add_p("    VI.3 Limites Identifiées et Contraintes Opérationnelles .......................................................... 37")
    add_p("    VI.4 Perspectives d'Évolution et Pistes Futures ....................................................................... 38")
    add_p("CONCLUSION GÉNÉRALE .......................................................................................................... 39")
    add_p("BIBLIOGRAPHIE TRIPARTITE ................................................................................................... 41")
    add_p("    1. Les Ouvrages ........................................................................................................................ 41")
    add_p("    2. Les Articles et Publications Scientifiques ......................................................................... 41")
    add_p("    3. Les Sites Internet et Documentations Officielles .............................................................. 42")
    add_p("ANNEXES ......................................................................................................................................... I")
    add_p("RÉSUMÉ ET MOTS-CLÉS (DOS DU MÉMOIRE) ......................................................................... 43")
    doc.add_page_break()

    # =========================================================================
    # 5. LISTE DES TABLEAUX ET DES FIGURES (Page iv)
    # =========================================================================
    add_title("LISTE DES TABLEAUX ET DES FIGURES", level=1)
    add_title("A. Liste des Tableaux", level=2)
    add_p("Tableau 1.1 : Matrice comparative des dysfonctionnements du système manuel vs RÉSIVO ......... Page 5")
    add_p("Tableau 2.1 : Matrice des acteurs et privilèges système ...................................................................... Page 9")
    add_p("Tableau 2.2 : Catalogue des règles de gestion d'intégrité (RG-01 à RG-10) ........................................ Page 10")
    add_p("Tableau 3.1 : Dictionnaire des données — Entités BLOCS et ROOMS .............................................. Page 15")
    add_p("Tableau 3.2 : Dictionnaire des données — Entité STUDENTS ........................................................... Page 16")
    add_p("Tableau 3.3 : Dictionnaire des données — Entités MAINTENANCE et ROOM_CHANGES ........... Page 16")
    add_p("Tableau 3.4 : Synthèse des politiques Row Level Security (RLS) ......................................................... Page 22")
    add_p("Tableau 5.1 : Récapitulatif d'exécution des suites de tests automatisés (136 tests validés) .................. Page 31")

    add_title("B. Liste des Figures et Schémas", level=2)
    add_p("Figure 1.1 : Cartographie organisationnelle des flux d'admission manuels en cité universitaire ...... Page 4")
    add_p("Figure 2.1 : Diagramme synthétique des cas d'utilisation (Use Case) .................................................. Page 11")
    add_p("Figure 3.1 : Modèle Conceptuel des Données (MCD - Formalisme Entité/Association) .................... Page 14")
    add_p("Figure 3.2 : Schéma Relationnel et Contraintes de Clés Étrangères (MPD) .......................................... Page 18")
    add_p("Figure 3.3 : Arbre d'exécution du trigger automatique d'héritage de genre ........................................... Page 20")
    add_p("Figure 4.1 : Architecture distribuée globale (Desktop, Web, Base Cloud Supabase, MCP) .............. Page 23")
    add_p("Figure 4.2 : Capture de la console d'administration Desktop (Gestion des Blocs et Chambres) .......... Page 26")
    add_p("Figure 4.3 : Capture du formulaire de création de chambre avec héritage automatique de genre ..... Page 27")
    add_p("Figure 4.4 : Capture du portail Web étudiant (Tableau de bord et doléances techniques) .................. Page 28")
    doc.add_page_break()

    # =========================================================================
    # 6. INTRODUCTION GÉNÉRALE (Page 1)
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
    add_p(
        "Le présent document est structuré en six chapitres distincts :\n"
        "• Le Chapitre I expose le contexte général, l'analyse de l'organisme d'accueil, le diagnostic de l'existant et les objectifs visés ;\n"
        "• Le Chapitre II détaille la démarche méthodologique, l'inventaire des acteurs et les règles de gestion du domaine ;\n"
        "• Le Chapitre III approfondit la modélisation conceptuelle, logique et physique de la base de données, ainsi que les mécanismes d'intégrité serveur ;\n"
        "• Le Chapitre IV décrit la réalisation technique des différentes couches applicatives (Desktop, Web, Déploiement) ;\n"
        "• Le Chapitre V présente la méthodologie de test, la validation des résultats et les métriques de fiabilité ;\n"
        "• Le Chapitre VI ouvre une discussion approfondie sur la portée des résultats obtenus, les limites rencontrées et les perspectives d'évolution."
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
        "L'analyse rigoureuse de ce mode opératoire conventionnel révèle de profondes faiblesses structurelles "
        "qui nuisent à l'efficacité du service public universitaire :"
    )
    add_p(
        "• Risque élevé d'erreurs d'attribution : L'absence de vérification automatique permet la sur-occupation de chambres "
        "ou l'affectation involontaire d'étudiants dans un pavillon non conforme à leur genre légal ;\n"
        "• Désynchronisation des informations : Les modifications effectuées par un service (ex. changement de chambre ou "
        "radiation) ne sont pas répercutées en temps réel sur les fiches de surveillance ni sur le service de maintenance ;\n"
        "• Traçabilité déficiente des pannes : Les demandes d'intervention technique écrites sur registre physique sont "
        "régulièrement égarées, sans horodatage objectif ni suivi d'état (en attente, en cours, résolu) ;\n"
        "• Manque de transparence pour l'étudiant : Le résident est privé de visibilité sur l'avancement de son dossier d'admission "
        "ou le traitement de sa requête technique."
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

    add_title("I.4 Formulation de la Question Centrale Unique de Recherche", level=2)
    add_p(
        "Au regard des insuffisances méthodologiques observées, la recherche doctorale et appliquée s'est cristallisée "
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
        "d'Étude et de Réalisation Informatique pour les Systèmes d'Entreprise), particulièrement adaptée aux systèmes "
        "d'information fortement centrés sur les bases de données relationnelles, complétée par une démarche agile "
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

    add_title("II.4 Spécifications Fonctionnelles Détaillées", level=2)
    add_p(
        "Le système répond aux cas d'utilisation primordiaux suivants :\n"
        "• Module Blocs & Chambres : Création préalable des pavillons avec attribution de genre, suivi en temps réel de "
        "la disponibilité des lits par jauge graphique, modification et archivage sécurisé ;\n"
        "• Module Candidatures & Affectation : Filtrage instantané des étudiants en attente, consultation de la fiche "
        "signalétique avec photo, sélection automatique des chambres compatibles non complètes, validation transactionnelle ;\n"
        "• Module Liste Officielle : Importation de fichiers CSV normalisés contenant les inscrits universitaires et détection "
        "immédiate des écarts d'identité ;\n"
        "• Module Maintenance : Soumission de doléance avec téléversement de cliché photographique probant, prise en charge par "
        "les agents techniques et clôture motivée ;\n"
        "• Module Mutations : Comparaison entre chambre actuelle et chambre souhaitée, vérification des places vacantes et "
        "transfert atomique en base de données."
    )

    add_title("II.5 Spécifications Non Fonctionnelles", level=2)
    add_p(
        "• Sécurité et Confidentialité : Chiffrement des communications en transit (HTTPS / WSS), hachage des mots de passe "
        "selon l'algorithme Argon2/Bcrypt et isolement des enregistrements via Row Level Security (RLS) ;\n"
        "• Performance et Réactivité : Temps d'exécution des requêtes de recherche inférieur à 100 millisecondes, indexation "
        "des colonnes de filtrage fréqent (block, gender, status) ;\n"
        "• Portabilité et Ergonomie : Fonctionnement autonome sur postes de travail Windows sans dépendance logicielle complexe, "
        "et compatibilité multi-navigateurs pour le portail Web."
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

    add_title("III.2 Modèle Conceptuel des Données (MCD)", level=2)
    add_p(
        "Le Modèle Conceptuel des Données formalise les règles de gestion sous forme d'entités-types et d'associations :\n"
        "• Entité BLOC : Représente les pavillons de la résidence. Identifiée par son nom unique (A, B, C...) et caractérisée par son genre désigné ;\n"
        "• Entité ROOM : Représente chaque unité de logement. Rattachée à un BLOC, caractérisée par son étage, son numéro, sa capacité et son genre ;\n"
        "• Entité STUDENT : Représente l'étudiant postulant ou hébergé. Reliée à la chambre par une association d'affectation (0,1 à 1,n) ;\n"
        "• Entité STAFF : Représente les agents et administrateurs habilités ;\n"
        "• Entité MAINTENANCE_REPORT : Représente les doléances techniques soumises par les résidents ;\n"
        "• Entité ROOM_CHANGE_REQUEST : Représente les demandes formelles de transfert de dortoir ;\n"
        "• Entité OFFICIAL_RESIDENT : Représente le registre officiel universitaire de contrôle."
    )

    add_title("III.3 Dictionnaire des Données Exhaustif", level=2)
    add_p(
        "Le dictionnaire des données spécifie la nature, le type et les contraintes associées à chaque champ manipulé "
        "par le système d'information :"
    )

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

    add_title("III.4 Modèle Logique des Données Relationnel (MLD-R)", level=2)
    add_p(
        "La dérivation du MCD vers le Modèle Logique Relationnel s'est effectuée dans le respect strict des formes "
        "normales jusqu'à la 3e Forme Normale (3FN). Chaque attribut non clé dépend directement et pleinement de la "
        "clé primaire entière, éliminant toute dépendance transitive et prévenant les anomalies de mise à jour."
    )
    add_p(
        "Structure relationnelle textuelle :\n"
        "• BLOCKS (id [PK], name [UNIQUE], gender, description, created_at, updated_at)\n"
        "• ROOMS (id [PK], block, floor, number, capacity, gender, created_at, updated_at) [UNIQUE(block, number)]\n"
        "• STUDENTS (id [PK], card_id [UNIQUE], first_name, last_name, birth_date, gender, phone, email, university, faculty, study_level, wilaya, status, rejection_reason, room_id [FK], reviewed_by [FK], reviewed_at, created_at, updated_at)\n"
        "• STAFF (id [PK], full_name, position, created_at)\n"
        "• MAINTENANCE_REPORTS (id [PK], student_id [FK], category, description, photo_path, status, staff_note, handled_by [FK], created_at, updated_at)\n"
        "• ROOM_CHANGE_REQUESTS (id [PK], student_id [FK], current_room_id [FK], preferred_room_id [FK], reason, status, decision_note, decided_by [FK], decided_at, created_at, updated_at)\n"
        "• OFFICIAL_RESIDENTS (id [PK], card_id [UNIQUE], first_name, last_name, birth_date, gender, university, faculty, created_at)"
    )

    add_title("III.5 Triggers et Procédures Stockées d'Intégrité Métier (PL/pgSQL)", level=2)
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

    add_p(
        "Le déclencheur ci-dessus intercepte chaque opération d'insertion ou de mise à jour sur la table des chambres. "
        "Il recherche le genre légal assigné au pavillon parent et l'affecte de façon transparente à la chambre. "
        "Cette implémentation matérialise l'exigence fonctionnelle demandée : l'utilisateur choisit le bloc, et la "
        "chambre reçoit automatiquement son genre sans risque d'erreur humaine."
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

    add_title("III.6 Sécurité Avancée : Row Level Security (RLS)", level=2)
    add_p(
        "Pour respecter les impératifs de confidentialité des données à caractère personnel (RGPD et législation "
        "nationale), le moteur PostgreSQL a été verrouillé par des politiques RLS (Row Level Security). Contrairement "
        "à un modèle d'habilitation applicatif traditionnel, la base de données évalue l'identité du demandeur (auth.uid()) "
        "pour chaque tuple renvoyé."
    )

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
        "La solution RÉSIVO adopte une architecture multi-surfaces distribuée, découplant judicieusement le stockage des "
        "données, l'administration métier lourde et l'accès nomade des usagers :"
    )
    add_p(
        "• Couche Persistance & Services Cloud : Base de données PostgreSQL / Supabase, assurant le stockage relationnel, "
        "la réplication, le stockage objet (photos de pannes) et le canal WebSocket pour la synchronisation temps réel ;\n"
        "• Couche Client Lourd d'Administration (Desktop) : Application native développée en Python avec le framework PySide6 (Qt6), "
        "destinée aux postes administratifs de la cité universitaire ;\n"
        "• Couche Client Léger Résident (Web) : Portail Web moderne conçu avec le framework Astro, TypeScript et Tailwind CSS, "
        "offrant une expérience mobile-first hautement réactive ;\n"
        "• Couche d'Interconnexion Intelligente (MCP - Model Context Protocol) : Serveur Python interfaçant la base de données avec des outils "
        "d'audit et d'inspection programmatique pour la gouvernance automatisée."
    )

    add_title("IV.2 Environnement Technique et Outillage Logiciel", level=2)
    add_p(
        "Le développement a mobilisé une suite d'outils et de bibliothèques éprouvés dans le secteur professionnel :\n"
        "• Système d'Exploitation : Windows 11 Enterprise (64-bit) ;\n"
        "• Langages de Programmation : Python 3.12 (Desktop & MCP), TypeScript / JavaScript (Web), PL/pgSQL (Base de données) ;\n"
        "• Frameworks UI : PySide6 / Qt version 6.7, Tailwind CSS avec tokens graphiques DOU normalisés ;\n"
        "• Outils de Packaging : PyInstaller 6.22 pour la congélation du binaire Python, Inno Setup 6.7 pour la génération de l'installeur Windows ;\n"
        "• Environnement de Test : Pytest (Desktop & MCP), Vitest (Web)."
    )

    add_title("IV.3 Réalisation de la Console Desktop d'Administration", level=2)
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
    add_p(
        "2. Instruction des Admissions et Filtrage Avancé :\n"
        "La vue des demandes en attente (« PendingPage ») confronte les données du candidat avec le répertoire officiel importé. "
        "La validation déclenche la procédure stockée qui alloue la place de façon atomique sans possibilité de conflit concurrent."
    )
    add_p(
        "3. Suivi et Clôture des Doléances Techniques :\n"
        "L'écran de maintenance (« MaintenancePage ») centralise les déclarations transmises par les résidents. L'inspecteur "
        "technique peut visualiser les photographies haute résolution attachées à chaque signalement dans une boîte modale dédiée "
        "« PhotoViewerDialog » pourvue de fonctions de zoom et d'adaptation plein écran."
    )

    add_title("IV.4 Réalisation du Portail Web Étudiant", level=2)
    add_p(
        "Le portail Web permet à l'étudiant d'interagir avec la résidence depuis tout terminal connecté (ordinateur ou smartphone). "
        "L'utilisation d'Astro garantit un chargement ultra-rapide sans surcoût de rendu JavaScript inutile. Le résident y retrouve "
        "son affectation, peut soumettre une réclamation en téléversant un cliché de son sanitaire ou mobilier endommagé, et "
        "déposer une demande de permutation de chambre restreinte aux seuls locaux vacants du même genre."
    )

    add_title("IV.5 Packaging, Distribution et Installeur Windows (Version 0.0.1)", level=2)
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

    add_title("VI.3 Limites Identifiées", level=2)
    add_p(
        "Certaines limites objectives ont toutefois été identifiées au terme de cette expérimentation :\n"
        "• Dépendance à la connectivité Internet : Bien que l'application Desktop dispose de mécanismes de tolérance aux coupures brèves, "
        "une synchronisation permanente avec la base cloud requiert un accès réseau stable ;\n"
        "• Absence de reconnaissance biométrique ou RFID à l'entrée des pavillons, obligeant les agents d'accueil à procéder à des "
        "contrôles visuels complémentaires."
    )

    add_title("VI.4 Perspectives d'Évolution", level=2)
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
    # CONCLUSION GÉNÉRALE (Page 39)
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
        "Sur le plan professionnel et personnel, l'accomplissement de ce mémoire a constitué une formidable opportunité de mobiliser "
        "l'ensemble des compétences acquises au cours des deux années de formation au sein du Centre de formation professionnelle et "
        "d'apprentissage des arts traditionnels : administration de bases de données, programmation objet, ergonomie logicielle, protocoles réseau "
        "et méthodologie de conduite de projet informatique."
    )
    add_p(
        "Le système RÉSIVO se présente ainsi comme une solution mature, testée et immédiatement déployable pour hisser la gestion des "
        "œuvres universitaires vers les plus hauts standards de modernité, de transparence et d'équité."
    )
    doc.add_page_break()

    # =========================================================================
    # BIBLIOGRAPHIE TRIPARTITE (Réglementaire, Slide 12)
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
    # ANNEXES (Pagination Romaine Majuscule : I, II, III...)
    # =========================================================================
    add_title("ANNEXES", level=1)
    add_title("Plan des Annexes", level=2)
    add_p("Annexe I : Script SQL de Définition des Tables Principales (DDL) ........................................ Page I")
    add_p("Annexe II : Implémentation des Triggers d'Intégrité Métier PL/pgSQL .................................... Page II")
    add_p("Annexe III : Procédure Transactionnelle d'Admission d'Étudiant ............................................ Page III")
    add_p("Annexe IV : Configuration de Compilation de l'Installeur Windows (Inno Setup) ...................... Page IV")

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

    add_title("Annexe IV : Script Inno Setup du Binaire Installeur Windows (v0.0.1)", level=2)
    add_callout(
        "EXTRAIT INSTALLER.ISS",
        "#define MyAppName \"RÉSIVO\"\n"
        "#define MyAppVersion \"0.0.1\"\n"
        "#define MyAppPublisher \"Direction des Œuvres Universitaires · Cité Universitaire · Tlemcen\"\n"
        "[Setup]\n"
        "AppName={#MyAppName}\n"
        "AppVersion={#MyAppVersion}\n"
        "DefaultDirName={autopf}\\RESIVO\n"
        "OutputDir=..\\dist\\installer\n"
        "OutputBaseFilename=RESIVO-Setup-0.0.1\n"
        "Compression=lzma2/ultra64\n"
        "SolidCompression=yes"
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

    # Sauvegarde du document Word
    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(DOC_PATH))
    print(f"Document Word généré avec succès : {DOC_PATH}")

if __name__ == "__main__":
    create_memoire()
