import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import KnowledgeDocument, Program, User
from app.rag import embed, ensure_document_chunks
from app.security import hash_password


PROGRAMS = [
    {
        "code": "IIT-PREPA",
        "institution": "IIT",
        "title": "Cycle préparatoire aux écoles d'ingénieurs",
        "level": "Cycle préparatoire",
        "summary": (
            "Cycle préparatoire intégré de l'IIT (MP1 et MP2) qui prépare aux filières ingénieur. "
            "Ouvert aux bacheliers scientifiques. Formation scientifique encadrée par des enseignants "
            "permanents de l'institut."
        ),
        "duration": "2 ans (MP1 puis MP2)",
        "prerequisites": (
            "Baccalauréat scientifique : mathématiques, sciences expérimentales, informatique ou technique."
        ),
        "tuition": (
            "556 DT / 9 mois (étudiants tunisiens) et 234 € / 9 mois (étudiants internationaux), "
            "montants indicatifs de première année ; majoration de 5 % par an ; frais d'inscription "
            "de 800 DT / 800 € en supplément."
        ),
        "subjects": [
            "Physique",
            "Analyse",
            "Algèbre",
            "Chimie",
            "Informatique",
            "Sciences et techniques de l'ingénieur",
            "Anglais",
            "Français",
        ],
        "careers": ["Poursuite en cycle ingénieur à l'IIT"],
        "source_url": "https://iit.tn/prepa/",
    },
    {
        "code": "IIT-LIC-GLSI",
        "institution": "IIT",
        "title": "Licence en Génie Logiciel et Système d'Information",
        "level": "Licence",
        "summary": (
            "Licence orientée conception, développement, test, déploiement et maintenance de solutions "
            "logicielles et de systèmes d'information. Enseignement en français et en anglais."
        ),
        "duration": "3 ans (180 crédits, LMD)",
        "prerequisites": (
            "Baccalauréat scientifique : mathématiques, sciences expérimentales, informatique ou technique. "
            "Formation accessible en français et en anglais."
        ),
        "tuition": (
            "667 DT / 9 mois (étudiants tunisiens) et 189 € / 9 mois (étudiants internationaux), "
            "montants indicatifs de première année ; majoration de 5 % par an ; frais d'inscription "
            "de 800 DT / 800 € en supplément."
        ),
        "subjects": [
            "Algorithmique",
            "Programmation",
            "Bases de données",
            "Systèmes d'information",
            "Génie logiciel",
            "Réseaux",
            "Développement web",
        ],
        "careers": [
            "Développeur logiciel et web",
            "Ingénieur des systèmes d'information",
            "Gestion de projets informatiques",
        ],
        "source_url": "https://iit.tn/licence-genie-logiciel-et-systheme-dinformation/",
    },
    {
        "code": "IIT-LIC-MSI",
        "institution": "IIT",
        "title": "Licence en Management des Systèmes Industriels",
        "level": "Licence",
        "summary": (
            "Formation à la gestion et à l'optimisation des systèmes industriels : maintenance préventive "
            "et prédictive, amélioration des processus de production, chaîne logistique et systèmes "
            "d'information. Un stage professionnel d'un mois est prévu à la clôture de chaque année."
        ),
        "duration": "Organisée en deux semestres par année universitaire ; durée totale à confirmer avec l'IIT",
        "prerequisites": "Baccalauréat ou diplôme reconnu équivalent, puis entretien de sélection.",
        "tuition": (
            "567 DT / 9 mois (étudiants tunisiens) et 167 € / 9 mois (étudiants internationaux), "
            "montants indicatifs de première année ; majoration de 5 % par an ; frais d'inscription "
            "de 800 DT / 800 € en supplément."
        ),
        "subjects": [
            "Lean manufacturing",
            "Management de projet",
            "Management de la qualité et sécurité au travail",
            "Chaîne logistique et systèmes d'information",
            "Maintenance industrielle et fiabilité",
        ],
        "careers": [
            "Responsable de service maintenance",
            "Cadre technique",
            "Automaticien",
            "Technicien d'essais et de mise en service",
        ],
        "source_url": "https://iit.tn/licences/licence-en-management-des-systemes-industriels/",
    },
    {
        "code": "IIT-ARCH",
        "institution": "IIT",
        "title": "Architecture (International School of Architecture - ISA)",
        "level": "Architecture",
        "summary": (
            "Cursus d'architecture de l'ISA, département de l'IIT, agréé par le Ministère de "
            "l'Enseignement Supérieur. Deux cycles : deux années de premier cycle puis quatre années "
            "de second cycle, couronnés par le Diplôme National d'Architecte. Ateliers, cours intégrés, "
            "workshops, stages, séminaires et voyages d'étude."
        ),
        "duration": "6 ans (2 + 4), Diplôme National d'Architecte",
        "prerequisites": (
            "Baccalauréat obligatoire. Pré-inscription en ligne, entretien avec un responsable du "
            "département, puis dépôt du dossier : copie de la CIN ou du passeport, copie du diplôme du "
            "baccalauréat, copie du relevé de notes de l'année du baccalauréat, 3 enveloppes, 3 photos "
            "et le règlement intérieur signé."
        ),
        "tuition": (
            "776 DT / 9 mois (étudiants tunisiens) et 278 € / 9 mois (étudiants internationaux), "
            "montants indicatifs de première année ; majoration de 5 % par an, tarifs stables de la "
            "4e à la 6e année ; frais d'inscription de 800 DT / 800 € en supplément."
        ),
        "subjects": [
            "Ateliers de projet",
            "Construction",
            "Urbanisme",
            "Histoire de l'architecture",
            "Sciences appliquées",
            "Droit et réglementation",
        ],
        "careers": ["Architecte (Diplôme National d'Architecte)"],
        "source_url": "https://iit.tn/architecture-2/",
    },
    {
        "code": "IIT-ING-INFO",
        "institution": "IIT",
        "title": "Génie Informatique (cycle ingénieur)",
        "level": "Cycle ingénieur",
        "summary": (
            "Diplôme d'ingénieur en génie informatique autorisé par le Ministère de l'Enseignement "
            "Supérieur depuis 2012 et accrédité par l'agence allemande ASIIN sous le label EURO-INF "
            "(niveau Master) depuis 2020."
        ),
        "duration": "Cycle ingénieur (accès après Prépa, Licence ou Mastère)",
        "prerequisites": "Cycle préparatoire, Licence ou Mastère.",
        "tuition": (
            "778 DT / 9 mois (étudiants tunisiens) et 234 € / 9 mois (étudiants internationaux), "
            "montants indicatifs de première année ; majoration de 5 % par an ; frais d'inscription "
            "de 800 DT / 800 € en supplément."
        ),
        "subjects": [
            "Génie logiciel",
            "Architecture logicielle",
            "Réseaux",
            "Bases de données",
            "Systèmes d'information",
            "Intelligence artificielle",
        ],
        "careers": [
            "Ingénieur informaticien",
            "Développeur / architecte logiciel",
            "Ingénieur systèmes et réseaux",
        ],
        "source_url": "https://iit.tn/filieres-ingenieur/genie-informatique-2/",
    },
    {
        "code": "IIT-ING-CIVIL",
        "institution": "IIT",
        "title": "Génie Civil (cycle ingénieur)",
        "level": "Cycle ingénieur",
        "summary": (
            "Formation d'ingénieur en génie civil : conception, construction, gestion, entretien et "
            "réparation des ouvrages de bâtiment et de travaux publics. Langue de formation : français."
        ),
        "duration": "Cycle ingénieur (accès après Prépa, Licence ou Mastère)",
        "prerequisites": "Cycle préparatoire, Licence ou Mastère. Langue de formation : français.",
        "tuition": (
            "484 DT / 9 mois (étudiants tunisiens) et 234 € / 9 mois (étudiants internationaux), "
            "montants indicatifs de première année ; majoration de 5 % par an ; frais d'inscription "
            "de 800 DT / 800 € en supplément."
        ),
        "subjects": [
            "Résistance des matériaux",
            "Béton armé",
            "Structures",
            "Géotechnique",
            "Travaux publics",
            "Gestion de chantier",
        ],
        "careers": [
            "Ingénieur génie civil",
            "Conducteur de travaux",
            "Ingénieur structures / BTP",
        ],
        "source_url": "https://iit.tn/filieres-ingenieur/genie-civil/",
    },
    {
        "code": "IIT-ING-IND",
        "institution": "IIT",
        "title": "Génie Industriel (cycle ingénieur)",
        "level": "Cycle ingénieur",
        "summary": (
            "Formation d'ingénieur capable d'analyser un système réel ou virtuel, de le résoudre et de "
            "l'exploiter pour en améliorer les performances. Filière labellisée EUR-ACE par ASIIN."
        ),
        "duration": "Cycle ingénieur (accès après Prépa, Licence ou Mastère)",
        "prerequisites": "Cycle préparatoire, Licence ou Mastère.",
        "tuition": (
            "612 DT / 9 mois (étudiants tunisiens) et 234 € / 9 mois (étudiants internationaux), "
            "montants indicatifs de première année ; majoration de 5 % par an ; frais d'inscription "
            "de 800 DT / 800 € en supplément."
        ),
        "subjects": [
            "Optimisation des processus",
            "Gestion de production",
            "Qualité et productivité",
            "Supply chain",
            "Recherche opérationnelle",
        ],
        "careers": [
            "Ingénieur génie industriel",
            "Responsable production",
            "Consultant en optimisation des processus",
        ],
        "source_url": "https://iit.tn/filieres-ingenieur/genie-industriel-2/",
    },
    {
        "code": "IIT-ING-MEC",
        "institution": "IIT",
        "title": "Génie Mécanique (cycle ingénieur)",
        "level": "Cycle ingénieur",
        "summary": (
            "Formation centrée sur la mécanique des systèmes physiques (mouvement, déformation, "
            "équilibre, métallurgie) et les mécanismes techniques, appliquée à la conception de produits "
            "et de systèmes mécaniques."
        ),
        "duration": "Cycle ingénieur (accès après Prépa, Licence ou Mastère)",
        "prerequisites": "Cycle préparatoire, Licence ou Mastère.",
        "tuition": (
            "556 DT / 9 mois (étudiants tunisiens) et 234 € / 9 mois (étudiants internationaux), "
            "montants indicatifs de première année ; majoration de 5 % par an ; frais d'inscription "
            "de 800 DT / 800 € en supplément."
        ),
        "subjects": [
            "Mécanique des solides",
            "Thermodynamique",
            "Matériaux et métallurgie",
            "Conception mécanique",
            "Fabrication",
        ],
        "careers": [
            "Ingénieur mécanique",
            "Bureau d'études",
            "Ingénieur méthodes / production",
        ],
        "source_url": "https://iit.tn/filieres-ingenieur/genie-mecanique-2/",
    },
    {
        "code": "IIT-ING-PROC",
        "institution": "IIT",
        "title": "Génie des Procédés (cycle ingénieur)",
        "level": "Cycle ingénieur",
        "summary": (
            "Formation d'ingénieur en génie des procédés : gestion de l'énergie, transformation optimale "
            "des matières premières et limitation des risques environnementaux et de sécurité."
        ),
        "duration": "Cycle ingénieur (accès après Prépa, Licence ou Mastère)",
        "prerequisites": "Cycle préparatoire, Licence ou Mastère.",
        "tuition": (
            "556 DT / 9 mois (étudiants tunisiens) et 234 € / 9 mois (étudiants internationaux), "
            "montants indicatifs de première année ; majoration de 5 % par an ; frais d'inscription "
            "de 800 DT / 800 € en supplément."
        ),
        "subjects": [
            "Opérations unitaires",
            "Transfert de matière et de chaleur",
            "Génie de la réaction chimique",
            "Énergie",
            "Sécurité industrielle",
        ],
        "careers": [
            "Ingénieur des procédés",
            "Ingénieur production chimique",
            "Ingénieur HSE",
        ],
        "source_url": "https://iit.tn/genie-des-procedes/",
    },
    {
        "code": "IIT-MASTER-IND40",
        "institution": "IIT",
        "title": "Mastère Industries 4.0",
        "level": "Mastère",
        "summary": (
            "Mastère orienté usine du futur : IoT, systèmes cyber-physiques, réalité virtuelle et "
            "augmentée, cloud computing, Big Data et informatique cognitive. Construit avec des "
            "industriels partenaires et adossé à un FABLAB fixe et mobile."
        ),
        "duration": "Mastère (accès après Licence)",
        "prerequisites": "Licence.",
        "tuition": (
            "556 DT / 9 mois (étudiants tunisiens) et 234 € / 9 mois (étudiants internationaux), "
            "montants indicatifs de première année ; majoration de 5 % par an ; frais d'inscription "
            "de 800 DT / 800 € en supplément."
        ),
        "subjects": [
            "IoT",
            "Systèmes cyber-physiques",
            "Réalité virtuelle et augmentée",
            "Cloud computing",
            "Big Data",
            "FABLAB",
        ],
        "careers": [
            "Responsable de la transformation digitale",
            "Expert en sécurité des systèmes d'information",
            "Designer industriel",
            "Développeur AR/VR et simulation",
        ],
        "source_url": "https://iit.tn/mastere/",
    },
    {
        "code": "ISB-LBA",
        "institution": "ISB",
        "title": "Licence in Business Administration (LBA)",
        "level": "Licence",
        "summary": (
            "Licence en administration des affaires entièrement enseignée en anglais. Couvre comptabilité "
            "et finance, marketing et analyse de marché, gestion des systèmes d'information, ingénierie "
            "des affaires et gestion des risques, entrepreneuriat et e-business."
        ),
        "duration": "3 ans, 180 crédits",
        "prerequisites": (
            "Baccalauréat et bons résultats en anglais et en mathématiques. Admission soumise à la "
            "commission d'admission du premier cycle."
        ),
        "tuition": "Non publié sur le site officiel ; contacter l'ISB au +216 74 248 222 ou info@isb.ens.tn.",
        "subjects": [
            "Principles of Management",
            "Financial Accounting",
            "Microeconomics",
            "Marketing",
            "Business Law",
            "Project Management",
            "Strategic Management",
        ],
        "careers": [
            "Chef d'entreprise",
            "Gestionnaire",
            "Chef des opérations",
            "Consultant en gestion",
            "Gestionnaire de projet",
        ],
        "source_url": "https://isb.tn/program-lba/",
    },
    {
        "code": "ISB-BI",
        "institution": "ISB",
        "title": "Licence en Business Intelligence (bilingue)",
        "level": "Licence",
        "summary": (
            "Licence bilingue à l'intersection de la data, de l'intelligence artificielle et de la "
            "gestion : analyse et visualisation des données, Data Analytics, IA et IA générative. "
            "Préparation aux certifications PCEP Python, NVIDIA Generative AI et Microsoft PL-300 Power BI."
        ),
        "duration": "3 ans, 180 crédits",
        "prerequisites": (
            "Baccalauréat et bon niveau en mathématiques et en anglais. Admission soumise à la "
            "commission d'admission du premier cycle."
        ),
        "tuition": "Non publié sur le site officiel ; contacter l'ISB au +216 74 248 222 ou info@isb.ens.tn.",
        "subjects": [
            "Algorithmes et structures de données",
            "Bases de données",
            "Analyse et fouille de données",
            "Entrepôt de données",
            "Big Data et Cloud",
            "Intelligence artificielle",
            "Power BI",
        ],
        "careers": [
            "Business Intelligence Analyst",
            "Data Analyst",
            "BI Consultant",
            "AI & BI Specialist",
        ],
        "source_url": "https://isb.tn/business-intelligence/",
    },
    {
        "code": "ISB-LNG",
        "institution": "ISB",
        "title": "Licence Nationale en Gestion (LNG)",
        "level": "Licence",
        "summary": (
            "Licence nationale en gestion enseignée en français, avec des parcours spécialisés en "
            "management, comptabilité, finance, logistique et production, marketing et ressources humaines."
        ),
        "duration": "3 ans (licence nationale)",
        "prerequisites": "Baccalauréat.",
        "tuition": "Non publié sur le site officiel ; contacter l'ISB au +216 74 248 222 ou info@isb.ens.tn.",
        "subjects": [
            "Management",
            "Comptabilité",
            "Finance",
            "Logistique et production",
            "Marketing",
            "Ressources humaines",
        ],
        "careers": [
            "Cadre en gestion",
            "Comptable",
            "Analyste financier",
            "Responsable logistique",
            "Responsable marketing",
            "Gestionnaire RH",
        ],
        "source_url": "https://isb.tn/licences-program/",
    },
    {
        "code": "ISB-MBA",
        "institution": "ISB",
        "title": "Master in Business Administration (MBA)",
        "level": "Mastère",
        "summary": (
            "MBA enseigné en anglais à l'ISB, destiné aux profils souhaitant approfondir la gestion, "
            "le leadership et la stratégie dans un cadre international."
        ),
        "duration": "2 ans (MBA)",
        "prerequisites": "Licence ; conditions d'admission à confirmer auprès de l'ISB.",
        "tuition": "Non publié sur le site officiel ; contacter l'ISB au +216 74 248 222 ou info@isb.ens.tn.",
        "subjects": ["Stratégie", "Leadership", "Finance", "Marketing", "Management"],
        "careers": ["Manager", "Consultant", "Entrepreneur"],
        "source_url": "https://isb.tn/program-mba/",
    },
    {
        "code": "ISB-MSC-FIN",
        "institution": "ISB",
        "title": "Master of Science (MSc) in Finance",
        "level": "Mastère",
        "summary": (
            "Master of Science en finance enseigné en anglais sur deux ans, ouvert aux titulaires d'une "
            "licence selon les conditions d'admission de l'ISB."
        ),
        "duration": "2 ans",
        "prerequisites": "Licence ; conditions d'admission à confirmer auprès de l'ISB.",
        "tuition": "Non publié sur le site officiel ; contacter l'ISB au +216 74 248 222 ou info@isb.ens.tn.",
        "subjects": ["Corporate finance", "Financial markets", "Investment", "Risk management"],
        "careers": ["Analyste financier", "Gestionnaire de portefeuille", "Consultant en finance"],
        "source_url": "https://isb.tn/program-msf/",
    },
]


KNOWLEDGE_DOCUMENTS = [
    {
        "title": "IIT — Présentation, campus et contacts",
        "institution": "IIT",
        "source_url": "https://iit.tn/",
        "is_sample": False,
        "content": (
            "L'Institut International de Technologie (IIT) est l'école d'ingénieurs du groupe North "
            "American Private University (NAU / Université nord-américaine privée), fondé en 2012 à "
            "Sfax, Tunisie. Le groupe comprend l'IIT (ingénierie), l'ISA (International School of "
            "Architecture, département de l'IIT), l'ISB (International School of Business) et NAU "
            "Executive Training Institute. L'IIT est autorisé par le Ministère tunisien de "
            "l'Enseignement Supérieur et de la Recherche Scientifique (MESRS). Adresses : Route de "
            "Tunis km 10, Technopole El Ons, Sfax ; Route Mharza km 1,5, Sfax. Téléphone : "
            "+216 74 46 50 20. E-mail : info@iit.tn. Site : https://iit.tn. "
            "L'ISB se trouve Route de Tunis km 10, Cité El Ons, Technopôle de Sfax ; téléphones "
            "+216 74 248 222 et +216 70 282 610 ; e-mail info@isb.ens.tn."
        ),
    },
    {
        "title": "IIT — Procédure d'admission et entretien",
        "institution": "IIT",
        "source_url": "https://iit.tn/admission/procedure-et-frais-dinscription/",
        "is_sample": False,
        "content": (
            "La candidature à toutes les filières d'ingénierie de l'IIT se fait par une pré-inscription "
            "en ligne sur le site de l'institut, avec une fenêtre distincte pour les candidats tunisiens "
            "et internationaux. Pour chaque filière, une commission d'au moins trois enseignants "
            "permanents désignés par la direction des études effectue un premier tri sur dossier selon "
            "des critères établis. L'admission se fait par concours sur dossier suivi d'un entretien de "
            "validation. Les candidats retenus sont invités à l'entretien avec des copies certifiées "
            "conformes aux originaux : diplôme du baccalauréat, autres diplômes, relevés de notes de "
            "chaque année d'enseignement et attestations de réussite. L'entretien vérifie le champ et le "
            "niveau des formations antérieures. À l'issue, la commission déclare le candidat accepté, "
            "refusé ou inscrit sur liste d'attente. Le formulaire de pré-inscription demande : nom, "
            "prénom, CIN ou passeport, pays, date de naissance, sexe, e-mail, téléphone, adresse, "
            "dernier diplôme obtenu et son année, diplôme souhaité, niveau (1, 2 ou 3), cours de jour ou "
            "du soir, et comment le candidat a connu l'IIT."
        ),
    },
    {
        "title": "IIT — Frais de scolarité, paiement et remboursement",
        "institution": "IIT",
        "source_url": "https://iit.tn/admission/procedure-et-frais-dinscription/",
        "is_sample": False,
        "content": (
            "Les frais de scolarité publiés par l'IIT sont indiqués par 9 mois et pour la première année "
            "uniquement, à titre indicatif. Cycle préparatoire : 556 DT (Tunisie) ou 234 € "
            "(international). Licence Génie Logiciel et Système d'Information : 667 DT ou 189 €. Licence "
            "Management des Systèmes Industriels : 567 DT ou 167 €. Architecture : 776 DT ou 278 €. "
            "Génie Informatique : 778 DT ou 234 €. Génie Civil : 484 DT ou 234 €. Génie Industriel : "
            "612 DT ou 234 €. Génie Mécanique : 556 DT ou 234 €. Génie des Procédés : 556 DT ou 234 €. "
            "Mastère Industries 4.0 : 556 DT ou 234 €. Un droit d'inscription de 800 DT (Tunisie) ou "
            "800 € (international) s'ajoute aux frais de scolarité. Une majoration annuelle de 5 % est "
            "appliquée à partir de la deuxième année, sauf en Architecture où les tarifs sont stables de "
            "la 4e à la 6e année. Une réduction de 5 % est accordée en cas de paiement de la totalité "
            "des frais à l'inscription. Les nouveaux tarifs ne s'appliquent qu'aux nouveaux étudiants. "
            "Toute inscription est ferme et définitive : en cas d'abandon, aucun remboursement n'est "
            "effectué et la totalité des frais reste due. Les étudiants internationaux paient selon le "
            "taux de change enregistré au 1er octobre de l'année en cours. Paiement par virement : "
            "Banque Zitouna, Agence Majida Boulila Sfax, compte 25 007 000 0000066789 17, au nom de "
            "North American Private University, IBAN TN59 25 007 000 0000066789 17, SWIFT BZITTNTTXXX."
        ),
    },
    {
        "title": "IIT — Bourses et aides financières",
        "institution": "IIT",
        "source_url": "https://iit.tn/admission/bourse/",
        "is_sample": False,
        "content": (
            "L'IIT accorde quatre types de bourses après avis de la commission et selon les modalités et "
            "limites fixées : bourse d'Excellence, bourse de Performance, bourse de Notoriété, et aide "
            "sociale / besoins spéciaux. La bourse n'est valable que pour l'année universitaire en cours "
            "et le nombre de bénéficiaires ne peut pas dépasser 10 % du nombre total des nouveaux "
            "inscrits. Les demandes de bourse doivent être présentées au maximum une semaine après la "
            "date d'inscription. Une commission nommée par le Directeur étudie les demandes et établit la "
            "liste des étudiants bénéficiaires."
        ),
    },
    {
        "title": "IIT — Cycle préparatoire",
        "institution": "IIT",
        "source_url": "https://iit.tn/prepa/",
        "is_sample": False,
        "content": (
            "Le cycle préparatoire de l'IIT prépare aux grandes écoles d'ingénieurs. Il est accessible à "
            "partir d'un baccalauréat scientifique : mathématiques, sciences expérimentales, informatique "
            "ou technique. Il fournit une formation scientifique solide et un encadrement rigoureux "
            "assuré par les professeurs de la région. Le cursus est organisé en MP1 puis MP2, avec "
            "Physique, Analyse, Algèbre, Chimie, Informatique, Sciences et techniques de l'ingénieur, "
            "Anglais et Français. Frais indicatifs de première année : 556 DT par 9 mois pour les "
            "étudiants tunisiens et 234 € par 9 mois pour les étudiants internationaux, plus 800 DT ou "
            "800 € de frais d'inscription, avec une majoration de 5 % par an. Contact : "
            "ameni.trigui@iit.ens.tn."
        ),
    },
    {
        "title": "IIT — Licences (Génie Logiciel et SI, Management des Systèmes Industriels)",
        "institution": "IIT",
        "source_url": "https://iit.tn/formation/",
        "is_sample": False,
        "content": (
            "L'IIT propose deux licences. La Licence en Génie Logiciel et Système d'Information est "
            "accessible avec un baccalauréat scientifique (mathématiques, sciences expérimentales, "
            "informatique ou technique) et est enseignée en français et en anglais. Elle vise à "
            "concevoir, analyser, évaluer, développer, tester, déployer et maintenir des systèmes "
            "d'information et des solutions logicielles. Débouchés : développeur logiciel et web, "
            "ingénieur des systèmes d'information, gestion de projets informatiques. Frais indicatifs : "
            "667 DT ou 189 € par 9 mois. La Licence en Management des Systèmes Industriels est ouverte "
            "aux titulaires d'un baccalauréat ou d'un diplôme reconnu équivalent, avec un entretien de "
            "sélection. Elle couvre le lean manufacturing, le management de projet, la qualité et la "
            "sécurité au travail, la chaîne logistique et les systèmes d'information, la maintenance "
            "industrielle et la fiabilité. Un stage d'un mois est effectué à la clôture de chaque année. "
            "Débouchés : responsable maintenance, cadre technique, automaticien, technicien d'essais. "
            "Frais indicatifs : 567 DT ou 167 € par 9 mois."
        ),
    },
    {
        "title": "IIT — Architecture (ISA)",
        "institution": "IIT",
        "source_url": "https://iit.tn/architecture-2/",
        "is_sample": False,
        "content": (
            "L'architecture est assurée par l'International School of Architecture (ISA), département "
            "de l'IIT, agréé par le Ministère de l'Enseignement Supérieur et de la Recherche "
            "Scientifique. Le cursus dure six ans, répartis en deux cycles : deux années au premier "
            "cycle et quatre années au second cycle, couronnés par le Diplôme National d'Architecte. "
            "L'enseignement alterne ateliers pratiques, cours intégrés, workshops, stages, séminaires et "
            "voyages d'étude, avec une formation pluridisciplinaire artistique, technique et juridique. "
            "L'inscription en première année exige le baccalauréat et suit trois étapes : pré-inscription "
            "en ligne, entretien avec un responsable du département, puis dépôt du dossier (copie de la "
            "CIN ou du passeport, copie du diplôme du baccalauréat, copie du relevé de notes de l'année "
            "du baccalauréat, 3 enveloppes, 3 photos, règlement intérieur signé). Frais indicatifs : "
            "776 DT ou 278 € par 9 mois, plus 800 DT ou 800 € d'inscription ; majoration de 5 % par an, "
            "tarifs stables de la 4e à la 6e année. Contact : hager.bejaoui@iit.ens.tn."
        ),
    },
    {
        "title": "IIT — Filières ingénieur et accréditations",
        "institution": "IIT",
        "source_url": "https://iit.tn/filieres-ingenieur/",
        "is_sample": False,
        "content": (
            "L'IIT propose cinq filières d'ingénieur accessibles après le cycle préparatoire, une "
            "licence ou un mastère : Génie Civil, Génie Informatique, Génie Industriel, Génie Mécanique "
            "et Génie des Procédés. Certaines pages de présentation mentionnent aussi le Génie des "
            "Télécommunications : sa disponibilité doit être confirmée avec l'institut. Le Génie "
            "Informatique est autorisé par le MESRS depuis 2012 et accrédité par l'agence allemande "
            "ASIIN sous le label EURO-INF niveau Master depuis 2020. Le Génie Industriel détient le "
            "label EUR-ACE délivré par ASIIN. L'IIT indique être la première institution privée "
            "tunisienne à obtenir ces deux labels. Frais indicatifs par 9 mois et pour la première "
            "année : Génie Civil 484 DT, Génie Industriel 612 DT, Génie Informatique 778 DT, Génie "
            "Mécanique 556 DT, Génie des Procédés 556 DT ; 234 € pour les étudiants internationaux ; "
            "plus 800 DT ou 800 € de frais d'inscription et une majoration de 5 % par an."
        ),
    },
    {
        "title": "IIT — Mastère Industries 4.0",
        "institution": "IIT",
        "source_url": "https://iit.tn/mastere/",
        "is_sample": False,
        "content": (
            "Le Mastère Industries 4.0 de l'IIT est accessible aux titulaires d'une licence. Il forme "
            "des experts de l'usine du futur : IoT, systèmes cyber-physiques, réalité virtuelle et "
            "augmentée, cloud computing, Big Data et informatique cognitive. Les points forts sont une "
            "forte implication des industries partenaires dans la construction du parcours et des "
            "projets, un programme issu d'un besoin industriel réel, une pédagogie active, un FABLAB "
            "bien équipé et un FABLAB mobile. Débouchés : responsable de la transformation digitale, "
            "expert en sécurité des systèmes d'information, designer industriel, conducteur "
            "d'installation automatisée ou robotisée, facilitateur de FabLab, développeur de logiciels "
            "de réalité augmentée, de simulation optique ou de réalité virtuelle. Frais indicatifs : "
            "556 DT ou 234 € par 9 mois. Contact : wafa.benmesmia@iit.ens.tn."
        ),
    },
    {
        "title": "ISB — Présentation, accréditations et contacts",
        "institution": "ISB",
        "source_url": "https://isb.tn/isb/",
        "is_sample": False,
        "content": (
            "L'International School of Business (ISB) est l'école de commerce du groupe North American "
            "Private University, située à Sfax, Tunisie, dans le Technopôle de Sfax. C'est la seule "
            "école de commerce indépendante enseignée en anglais dans le sud de la Tunisie. L'ISB est "
            "officiellement autorisée par le Ministère de l'Enseignement Supérieur et de la Recherche "
            "Scientifique (MESRS). Son unité Business Administration est accréditée par l'IACBE "
            "(International Accreditation Council for Business Education) ; l'ISB indique être la "
            "première université privée tunisienne accréditée par l'IACBE. L'école applique aussi la "
            "norme ISO 21001:2018. Elle propose des licences, des mastères, un MBA et des programmes de "
            "formation continue, ainsi que des échanges internationaux, des doubles diplômes et des "
            "partenariats universitaires dans plus de douze pays. Adresse : Route de Tunis km 10, Cité "
            "El Ons, Technopôle de Sfax. Téléphones : +216 74 248 222 et +216 70 282 610. E-mail : "
            "info@isb.ens.tn."
        ),
    },
    {
        "title": "ISB — Licences et conditions d'admission",
        "institution": "ISB",
        "source_url": "https://isb.tn/licences-program/",
        "is_sample": False,
        "content": (
            "L'ISB propose des licences en trois ans, 180 crédits, avec une rentrée en septembre et une "
            "date limite d'inscription au 15 septembre. La Licence in Business Administration (LBA) est "
            "enseignée en anglais ; elle exige le baccalauréat et de bons résultats en anglais et en "
            "mathématiques. Elle couvre comptabilité et finance, marketing et analyse de marché, gestion "
            "des systèmes d'information, ingénierie des affaires et gestion des risques, entrepreneuriat "
            "et e-business, avec 51 cours, 33 cours Business Core (131 crédits) et 18 cours Non-Business "
            "Core (49 crédits). La Licence en Business Intelligence (BI) est bilingue et combine data, "
            "intelligence artificielle et gestion, avec les certifications PCEP Python, NVIDIA "
            "Generative AI et Microsoft PL-300 Power BI. La Licence Nationale en Gestion (LNG) est en "
            "français avec des parcours en management, comptabilité, finance, logistique et production, "
            "marketing et ressources humaines. L'ISB propose aussi Business Economics, Transport et "
            "Logistique, Droit des Affaires et Droit Privé. Pour obtenir le diplôme, l'étudiant doit "
            "obtenir au minimum 2 GPA par an sur un maximum de 4. L'admission est soumise à la "
            "commission d'admission du premier cycle."
        ),
    },
    {
        "title": "ISB — Masters, MBA et admission",
        "institution": "ISB",
        "source_url": "https://isb.tn/program/",
        "is_sample": False,
        "content": (
            "L'ISB propose plusieurs masters : Master in Business Administration (MBA) en anglais, "
            "Mastère en Marketing Digital, Mastère en Comptabilité, Mastère Finance d'Entreprise et "
            "Ingénierie Financière, Master of Science (MSc) in Digital Marketing, Master of Science "
            "(MSc) in Finance, Master in Business Law, ainsi que des mastères en marketing des produits "
            "et services de santé, marketing distribution et relation client, management et marketing "
            "des produits agroalimentaires, audit interne et finance islamique. Le MBA et le MSc in "
            "Finance sont enseignés en anglais sur deux ans ; les titulaires d'une licence peuvent se "
            "renseigner sur les conditions d'admission. La pré-inscription se fait en ligne via le site "
            "de l'ISB ; les informations demandées sont confidentielles et la demande est étudiée par "
            "une commission pédagogique. Les frais des masters ne sont pas publiés sur le site : il "
            "faut contacter l'ISB au +216 74 248 222 ou info@isb.ens.tn."
        ),
    },
    {
        "title": "Calendrier et dates importantes (informations publiées)",
        "institution": "ISB",
        "source_url": "https://isb.tn/pre-inscription/",
        "is_sample": False,
        "content": (
            "Dates publiées : pour les licences LBA et Business Intelligence de l'ISB, la rentrée est en "
            "septembre et la date limite d'inscription est le 15 septembre. La pré-inscription ISB est "
            "ouverte via le formulaire en ligne du site. Pour l'IIT, aucune date limite ni calendrier "
            "académique n'est publié sur les pages consultées : la procédure est une pré-inscription en "
            "ligne suivie d'un entretien, et l'institut doit être contacté pour les dates exactes de la "
            "campagne d'admission et la rentrée. Il ne faut donc pas annoncer une date de rentrée IIT "
            "comme certaine : orienter le candidat vers le service des admissions (+216 74 46 50 20, "
            "info@iit.tn)."
        ),
    },
    {
        "title": "Reconnaissance du diplôme, accréditations et équivalences",
        "institution": "IIT",
        "source_url": "https://iit.tn/a-propos/accreditations/",
        "is_sample": False,
        "content": (
            "L'IIT et l'ISB sont autorisés par le Ministère tunisien de l'Enseignement Supérieur et de "
            "la Recherche Scientifique. Les formations d'ingénieur de l'IIT sont labellisées par "
            "l'agence allemande ASIIN : EUR-ACE en Génie Industriel et EURO-INF en Génie Informatique "
            "(niveau Master, depuis 2020). L'unité Business Administration de l'ISB est accréditée par "
            "l'IACBE et l'école applique la norme ISO 21001:2018. Ces labels attestent de la conformité "
            "des programmes à des référentiels internationaux. Aucune procédure d'équivalence de diplôme "
            "n'est publiée sur les sites officiels : pour une reconnaissance dans la fonction publique "
            "tunisienne ou à l'étranger, le candidat doit s'adresser au MESRS et à l'institut. "
            "L'assistant ne doit pas garantir une équivalence ni une reconnaissance officielle."
        ),
    },
    {
        "title": "Questions fréquentes des candidats (IIT et ISB)",
        "institution": "ISB",
        "source_url": "https://isb.tn/program-lba/",
        "is_sample": False,
        "content": (
            "Questions fréquentes et réponses sourcées. Où étudier la gestion ou l'informatique à Sfax ? "
            "L'IIT et l'ISB proposent respectivement des formations d'ingénieur et de commerce à Sfax. "
            "L'ISB est-elle agréée ? Oui, par le MESRS, et son unité Business Administration est "
            "accréditée IACBE. Existe-t-il des échanges internationaux ? Oui, un ou deux semestres chez "
            "des partenaires, selon les résultats académiques et les compétences linguistiques. Peut-on "
            "faire un MSc Finance après une licence ? Oui, l'ISB propose un MSc in Finance en anglais "
            "sur deux ans, sous conditions d'admission. Quels débouchés après Business Administration ? "
            "Gestion, commerce, entrepreneuriat, administration des entreprises, puis finance, "
            "marketing, management ou comptabilité. Quelles sont les conditions d'admission en Business "
            "Intelligence ? Baccalauréat et bon niveau en mathématiques et en anglais, avec l'accord de "
            "la commission d'admission. Quelle différence entre Business Intelligence et Data Science ? "
            "La BI se concentre sur l'analyse, la visualisation et l'exploitation des données pour la "
            "décision ; la Data Science ajoute des modèles prédictifs. Questions à escalader vers un "
            "conseiller : acceptation d'un dossier, réduction personnalisée, équivalence d'un diplôme "
            "étranger, dates exactes de la campagne IIT."
        ),
    },
    {
        "title": "Estimation des frais IIT pour 2026-2027 (non officielle)",
        "institution": "IIT",
        "source_url": "https://iit.tn/admission/procedure-et-frais-dinscription/",
        "is_sample": True,
        "content": (
            "Estimation de travail, non officielle. Les tarifs publiés par l'IIT sont ceux de la "
            "première année et l'institut applique une majoration de 5 % par an. En appliquant cette "
            "règle aux montants publiés, on obtient environ : Cycle préparatoire 584 DT ou 246 € ; "
            "Licence Génie Logiciel et SI 700 DT ou 198 € ; Licence Management des Systèmes Industriels "
            "595 DT ou 175 € ; Architecture 815 DT ou 292 € ; Génie Informatique 817 DT ou 246 € ; "
            "Génie Civil 508 DT ou 246 € ; Génie Industriel 643 DT ou 246 € ; Génie Mécanique 584 DT ou "
            "246 € ; Génie des Procédés 584 DT ou 246 € ; Mastère Industries 4.0 584 DT ou 246 €, par "
            "9 mois. Ces montants sont des estimations pour la première année et excluent les 800 DT ou "
            "800 € de frais d'inscription. Ils ne remplacent pas un devis officiel : toujours renvoyer "
            "le candidat vers l'IIT pour un montant à jour."
        ),
    },
]


DEMO_ACCOUNTS = [
    ("demo.admin@smartcampus.example.com", "Platform administrator", "admin", None),
    ("demo.iit@smartcampus.example.com", "IIT academic adviser", "academic_iit", "IIT"),
    ("demo.isb@smartcampus.example.com", "ISB academic adviser", "academic_isb", "ISB"),
    ("demo.interviewer@smartcampus.example.com", "Interview coordinator", "interviewer", None),
    ("demo.director@smartcampus.example.com", "Admissions director", "director", None),
]


async def seed_demo_data(db: Session) -> None:
    if os.getenv("APP_ENV", "development") == "production":
        return
    if os.getenv("SEED_DEMO_DATA", "true").casefold() != "true":
        return

    for item in PROGRAMS:
        if db.scalar(select(Program).where(Program.code == item["code"])) is None:
            db.add(Program(**item, is_sample=False, is_active=True))

    for item in KNOWLEDGE_DOCUMENTS:
        if db.scalar(
            select(KnowledgeDocument).where(KnowledgeDocument.title == item["title"])
        ) is None:
            db.add(
                KnowledgeDocument(
                    **item,
                    embedding=await embed(f'{item["title"]} {item["content"]}'),
                )
            )

    db.flush()
    for document in db.scalars(select(KnowledgeDocument)):
        if not document.chunks:
            await ensure_document_chunks(db, document)

    demo_password = os.getenv("DEMO_PASSWORD", "CampusDemo2026!")
    for email, name, role, institution in DEMO_ACCOUNTS:
        if db.scalar(select(User).where(User.email == email)) is None:
            db.add(
                User(
                    name=name,
                    email=email,
                    role=role,
                    institution=institution,
                    password_hash=hash_password(demo_password),
                )
            )
    db.commit()
