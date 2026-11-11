# RÉSIVO — Guide Terminologique et Règles d’Internationalisation (i18n)

> **Projet** : RÉSIVO (Plateforme de Gestion de Résidence Universitaire)  
> **Contexte** : Direction des Œuvres Universitaires (DOU) · Cité Universitaire de Tlemcen, Algérie  
> **Public cible** : Personnel administratif, agents de maintenance, étudiants résidents  
> **Locales prises en charge** : Français (`fr`, locale principale administrative), Anglais (`en`, locale technique / internationale)

---

## 1. Principes Fondamentaux et Règles de Marque

Dans l’administration universitaire algérienne (Ministère de l’Enseignement Supérieur et de la Recherche Scientifique - MESRS / Direction des Œuvres Universitaires - DOU), les communications administratives s’effectuent en arabe et en français formel. Le français utilisé dans RÉSIVO doit être rigoureux, clair, respectueux des normes institutionnelles et exempt d’anglicismes informels.

### Noms Propres et Termes Institutionnels Invariables (NE JAMAIS TRADUIRE)

Les termes suivants sont des noms de marque ou des désignations institutionnelles officielles. Ils demeurent **strictement inchangés** dans toutes les langues (français, anglais, etc.) :

| Terme Officiel | Règle d’usage | Exemple |
| :--- | :--- | :--- |
| **RÉSIVO** | Nom de la plateforme logicielle. Toujours écrit en majuscules avec l’accent aigu sur le É. | « Bienvenue sur RÉSIVO » / *“Welcome to RÉSIVO”* |
| **Cité Universitaire** | Désignation de l’établissement d’hébergement universitaire. Ne jamais traduire par *University City* ou *Campus Residence*. | « Cité Universitaire de Tlemcen » |
| **Direction des Œuvres Universitaires** | Organisme public de tutelle chargé de la vie étudiante et du logement. | « Direction des Œuvres Universitaires de Tlemcen » |
| **DOU** | Sigle officiel de la Direction des Œuvres Universitaires. Toujours en majuscules sans points. | « DOU Tlemcen » |
| **Wilaya** | Division administrative territoriale en Algérie. Ne pas traduire par *Province* ou *State*. | « Wilaya d’origine » / *“Home Wilaya”* |

---

## 2. Règles Typographiques Françaises

La localisation française de RÉSIVO applique scrupuleusement les règles du Code typographique de l’Imprimerie Nationale.

### 2.1 Ponctuation et Espaces Insécables (`\u00A0` / `&nbsp;`)
En typographie française, les signes de ponctuation dits « doubles » ou hauts sont précédés d’une espace insécable pour éviter qu’ils ne soient orphelins en début de ligne :
- Deux-points (**\u00A0:**)
- Point-virgule (**\u00A0;**)
- Point d’interrogation (**\u00A0?**)
- Point d’exclamation (**\u00A0!**)
- Signe pourcentage (**\u00A0%**)
- Guillemets ouvrants (**«\u00A0**) et fermants (**\u00A0»**)

*Exemples :*
- Correct : `Fermer RÉSIVO\u00A0?` | Incorrect : `Fermer RÉSIVO?` ou `Fermer RÉSIVO ?`
- Correct : `Mot de passe oublié\u00A0?` | Incorrect : `Mot de passe oublié?`
- Correct : `Occupation\u00A0: 85\u00A0%` | Incorrect : `Occupation: 85%`

### 2.2 Guillemets Français (« »)
- Utiliser systématiquement les chevrons doubles (« et ») entourant le texte avec des espaces insécables intérieures.
- Ne pas utiliser les guillemets anglais droits (`"..."`) ou courbes (`“...”`).
- *Exemple :* `« Liste officielle de l’université »`

### 2.3 Apostrophe Typographique Courbée (’)
- Utiliser l’apostrophe dactylographique courbée (`’`, Unicode `U+2019`) plutôt que l’apostrophe droite ASCII (`'`, Unicode `U+0027`).
- *Exemples :*
  - `Demandes d’hébergement` (et non `Demandes d'hébergement`)
  - `Niveau d’études` (et non `Niveau d'études`)
  - `S’inscrire` (et non `S'inscrire`)
  - `À l’instant` (et non `A l'instant`)

### 2.4 Majuscules Accentuées
En français, les majuscules doivent obligatoirement porter leurs accents :
- `É` (Électricité, Étage, É-mail, Étudiant)
- `À` (À l’instant, À propos)
- `È`, `Ê`, `Ç` (Œuvres, Cité)

### 2.5 Formats de Date et d’Heure
- **Heure au format 24 heures** : notation `HH:MM` ou `HH\u00A0h\u00A0MM`. RÉSIVO utilise le standard 24h sans mention AM/PM (`14:30`, `08:00`).
- **Dates** :
  - Format numérique court : `JJ/MM/AAAA` (ex. `12/10/2026`).
  - Format textuel : les noms de mois et de jours de la semaine s’écrivent impérativement en minuscules (ex. `lundi 12 octobre 2026`, `janvier`, `février`, `mars`, `avril`).

### 2.6 Formats Numériques
- **Séparateur décimal** : la virgule (`,`). Exemple : `98,5\u00A0%`.
- **Séparateur de milliers** : l’espace insécable (`\u00A0`). Exemple : `1\u00A0250 étudiants`. Ne jamais utiliser la virgule ou le point comme séparateur de milliers en français.

---

## 3. Glossaire de Référence (Starter Glossary)

Tableau de correspondance strict entre les termes sources anglais et la terminologie formelle française adoptée :

| Terme Source (EN) | Terme Français Validé (FR) | Domaine / Clé i18n | Notes d’Usage |
| :--- | :--- | :--- | :--- |
| **Dashboard / Overview** | **Tableau de bord** | `nav.overview`, `overview.title` | Vue synthétique des métriques et alertes |
| **Applications** | **Demandes d’hébergement** | `nav.pending`, `pending.title` | Dossiers de logement déposés par les étudiants |
| **Pending** | **En attente** | `status.pending` | Statut d’un dossier ou ticket non encore traité |
| **Approved / Active** | **Approuvée / Active** | `status.approved`, `status.active` | Forme féminine pour une demande (`Approuvée`), masculin pour un compte (`Approuvé`) |
| **Rejected** | **Rejetée** | `status.rejected` | Demande refusée |
| **In progress** | **En cours** | `status.in_progress` | Intervention ou analyse en cours d’exécution |
| **Resolved** | **Résolue** | `status.resolved` | Problème de maintenance ou demande clôturée |
| **Residents** | **Résidents** | `nav.residents`, `residents.title` | Étudiants hébergés dans la cité universitaire |
| **Rooms** | **Chambres** | `nav.rooms`, `rooms.title` | Inventaire des chambres de la résidence |
| **Room** | **Chambre** | `terms.room` | Entité chambre individuelle ou partagée |
| **Block** | **Bloc** | `terms.block` | Pavillon ou bâtiment de la cité (ex. Pavillon A) |
| **Floor** | **Étage** | `terms.floor` | Niveau du bâtiment (RDC, 1er étage, etc.) |
| **Capacity** | **Capacité** | `terms.capacity` | Nombre maximal de lits d’une chambre |
| **Occupancy** | **Occupation** | `terms.occupancy` | Taux ou nombre de résidents assignés |
| **Available** | **Disponible** | `status.available` | Chambre ou place vacante |
| **Maintenance** | **Maintenance** | `nav.maintenance`, `maintenance.title` | Service technique des réparations |
| **Maintenance report / ticket** | **Signalement de maintenance** | `terms.maintenance_report` | Déclaration d’une panne ou dégradation |
| **Category** | **Catégorie** | `terms.category` | Domaine d’intervention technique |
| **Plumbing** | **Plomberie** | `category.plumbing` | Fuites, sanitaires, canalisations |
| **Electricity** | **Électricité** | `category.electricity` | Prises, éclairage, tableaux électriques |
| **Carpentry** | **Menuiserie** | `category.carpentry` | Portes, fenêtres, serrures, armoires |
| **Others** | **Autres** | `category.others` | Interventions diverses hors catégories principales |
| **Room change request** | **Demande de changement de chambre** | `nav.room_changes`, `room_changes.title`| Procédure de permutation ou transfert |
| **Official list / roster** | **Liste officielle de l’université** | `nav.official_list`, `official_list.title`| Roster académique délivré par l’Université |
| **Staff accounts** | **Comptes du personnel** | `nav.staff_accounts`, `staff.title`| Utilisateurs administratifs et agents |
| **Settings** | **Paramètres** | `nav.settings`, `settings.title` | Configuration de la console et préférences |
| **Language** | **Langue** | `settings.language` | Sélecteur de langue d’affichage |
| **Sign in** | **Se connecter** | `login.sign_in`, `auth.sign_in` | Action d’authentification |
| **Sign out** | **Se déconnecter** | `nav.sign_out`, `auth.sign_out` | Clôture de la session active |
| **Register** | **S’inscrire** | `auth.register` | Création de compte étudiant |
| **Password** | **Mot de passe** | `login.password_label`, `fields.password`| Identifiant secret |
| **Card ID** | **N° de carte étudiant** | `fields.card_id` | Identifiant national / universitaire unique |
| **Email** | **E-mail** | `fields.email`, `login.email_label` | Adresse électronique |
| **Phone** | **Téléphone** | `fields.phone` | Numéro de téléphone portable |
| **Faculty** | **Faculté** | `fields.faculty` | Entité universitaire de rattachement |
| **University** | **Université** | `fields.university` | Université d’inscription (ex. Université de Tlemcen) |
| **Study level** | **Niveau d’études** | `fields.study_level` | Cycle d’études (Licence L1/L2/L3, Master M1/M2, Doctorat) |
| **Wilaya** | **Wilaya** | `fields.wilaya` | Wilaya de résidence d’origine de l’étudiant |
| **Gender** | **Genre** | `gender.title`, `fields.gender` | Masculin / Féminin |
| **Male / Female** | **Masculin / Féminin** | `gender.male`, `gender.female` | Valeurs de genre |
| **Approve** | **Approuver** | `common.approve` | Action de validation administrative |
| **Reject** | **Rejeter** | `common.reject` | Action de refus d’un dossier |
| **Rejection reason** | **Motif du rejet** | `fields.rejection_reason` | Justification administrative obligatoire du refus |
| **Save** | **Enregistrer** | `common.save` | Enregistrement de formulaire ou modification |
| **Cancel** | **Annuler** | `common.cancel` | Abandon d’une action sans enregistrer |
| **Delete** | **Supprimer** | `common.delete` | Suppression d’une entité |
| **Search** | **Rechercher** | `common.search` | Champ ou bouton de filtrage textuel |
| **Filter** | **Filtrer** | `common.filter` | Critères de sélection |
| **All** | **Tous / Toutes** | `common.all`, `common.all_f` | « Tous » (masculin) / « Toutes » (féminin) |
| **Notifications** | **Notifications** | `settings.notifications` | Alertes système et notifications toast |
| **Quiet hours** | **Heures silencieuses** | `settings.quiet_hours` | Période sans notifications sonores/toasts |
| **Restart now** | **Redémarrer maintenant** | `common.restart_now` | Rechargement immédiat de l’application |
| **Digital resident pass** | **Carte de résident numérique** | `terms.digital_pass` | Pass virtuel avec QR code pour l’accès à la cité |
| **Roster match** | **Correspondance avec la liste officielle** | `status.matched` | Étudiant vérifié sur la liste universitaire |
| **Not in roster** | **Absent de la liste officielle** | `status.not_in_roster` | Étudiant non répertorié sur le listing officiel |
| **Contact email** | **E-mail de contact** | `fields.contact_email` | Adresse de contact étudiant (non vérifiée) |
| **Forgot your password? Please contact the housing office.** | **Mot de passe oublié\u00A0? Veuillez contacter le bureau des résidences.** | `auth.forgot_password_office` | Consigne en texte simple sur `/login` |

---

## 4. Règles Grammaticales et Conventions d’Interface (UI Copywriting)

### 4.1 Formes Verbales des Actions (Boutons et Liens)
- **Infinitif obligatoire** pour les libellés de boutons et d’actions directes :
  - *Enregistrer* (et non *Enregistrez*)
  - *Annuler*, *Supprimer*, *Modifier*, *Actualiser*, *Réessayer*
  - *Se connecter*, *Se déconnecter*, *Approuver*, *Rejeter*
- **Participe passé** pour les statuts d’états :
  - *Approuvée*, *Rejetée*, *En attente*, *Résolue*, *Enregistré*

### 4.2 Accord en Genre et en Nombre
Veiller à accorder le statut selon l’entité qualifiée :
- **Une demande d’hébergement** : *En attente*, *Approuvée*, *Rejetée*
- **Un signalement de maintenance** : *En attente*, *En cours*, *Résolu*
- **Un compte utilisateur** : *Actif*, *Suspendu*, *Vérifié*
- **Une chambre** : *Disponible*, *Complète*, *En maintenance*

### 4.3 Pluralisation (Spécification CLDR)
Le français et l’anglais diffèrent sur la gestion du zéro :
- **En anglais** : `count == 1` prend la forme `_one` ; `count == 0` et `count > 1` prennent la forme `_other`.
- **En français** : `count == 0` et `count == 1` prennent tous deux la forme singulière `_one` (ex. *0 minute*, *1 minute*) ; `count >= 2` prend la forme `_other` (ex. *2 minutes*).
Les clés de traduction pour les éléments quantifiés suivent systématiquement la nomenclature conventionnelle :
- `<clé>_one`
- `<clé>_other`

---

## 5. Architecture des Fichiers de Traduction (JSON)

Les catalogues JSON (`desktop/i18n/en.json` et `desktop/i18n/fr.json`) partagent exactement la même structure d’arborescence hiérarchique.

### Modules Normalisés :
- `common` : actions génériques, dialogues de confirmation, états globaux.
- `nav` : barre latérale, en-têtes et navigation globale.
- `status` : statuts partagés des demandes, tickets et chambres.
- `category` : corps de métier et natures d’incidents techniques.
- `gender` : options d’identification civile.
- `login` : interface de connexion du personnel, héros visuel, messages de validation.
- `close_dialog` : politique de fermeture, avertissements de tâches en cours.
- `tray` : menu contextuel et infobulles de la zone de notification Windows.
- `time` : formatage des durées relatives avec gestion plurielle.
- `terms` / `fields` : entités métier et formulaires administratifs.

Tout ajout de clé dans un catalogue doit immédiatement être répercuté dans l’autre catalogue avec les mêmes noms de paramètres entre accolades (`{count}`, `{name}`, etc.).
