"""Domain-specific allow-lists for PII false-positive prevention.

Terms in the allow-list are passed to Presidio's ``analyzer.analyze(allow_list=...)``
so that they are never flagged as PII regardless of model confidence.

Categories
----------
INSTITUTIONS
    Universities, testing bodies, and well-known organizations.
ACADEMIC_TERMS
    Degree names, program names, and academic titles.
PRONOUNS
    English pronouns and determiners commonly misidentified as PERSON.
TECHNICAL_TERMS
    Programming languages, software tools, and technical keywords.
ACTIVITIES
    Hobbies and extracurricular activities.
LANGUAGES
    Natural language names that should never be flagged as PII.
    Defense-in-depth: even with NRP excluded via post-filter,
    language names like "French" could be caught as PERSON.
FORM_LABELS
    French and English form field labels from structured documents
    (synthese, transcripts) that are mistakenly tagged as PII entities.
JOB_TITLES
    Professional titles and roles commonly misidentified as PERSON.
"""

from __future__ import annotations

INSTITUTIONS: frozenset[str] = frozenset(
    {
        "EPFL",
        "ETH",
        "ETH Zurich",
        "UNESCO",
        "UNICEF",
        "WHO",
        "IEEE",
        "ACM",
        "IELTS",
        "TOEFL",
        "TOEIC",
        "GRE",
        "GMAT",
        "SAT",
        "ICDL",
        "British Council",
        "Microsoft",
        "Google",
        "Amazon",
        "IBM",
        "Apple",
        "Meta",
        "MIT",
        "Stanford",
        "Harvard",
        "Oxford",
        "Cambridge",
        "Coursera",
        "edX",
        "Udemy",
    }
)

ACADEMIC_TERMS: frozenset[str] = frozenset(
    {
        "Master",
        "Master of Science",
        "Bachelor",
        "Bachelor of Science",
        "Bachelor of Arts",
        "PhD",
        "Doctorate",
        "MBA",
        "MFA",
        "Minor",
        "Major",
        "Diploma",
        "Certificate",
        "MTE",
        "Management",
        "Technology",
        "Entrepreneurship",
        "Computer Science",
        "Electrical Engineering",
        "Mechanical Engineering",
        "Civil Engineering",
        "Mathematics",
        "Physics",
        "Chemistry",
        "Biology",
        "Economics",
        "Finance",
        "GPA",
        "ECTS",
        "Semester",
        "Dean",
        "B.Tech",
        "M.Tech",
        "B.Sc",
        "M.Sc",
        "B.Eng",
        "M.Eng",
        "B.A",
        "M.A",
        "M.A.D",
        "BSc",
        "MSc",
        "BEng",
        "MEng",
        "Licence",
        "Baccalauréat",
        "Ingénieur",
        "Doctorat",
        "Maîtrise",
    }
)

PRONOUNS: frozenset[str] = frozenset(
    {
        "I",
        "He",
        "She",
        "It",
        "We",
        "They",
        "Me",
        "Him",
        "Her",
        "Us",
        "Them",
        "My",
        "His",
        "Its",
        "Our",
        "Their",
        "Myself",
        "Himself",
        "Herself",
        "Itself",
        "Ourselves",
        "Themselves",
        "You",
        "Your",
        "Yours",
        "Yourself",
    }
)

TECHNICAL_TERMS: frozenset[str] = frozenset(
    {
        "C++",
        "C#",
        "Python",
        "Java",
        "JavaScript",
        "TypeScript",
        "Visual Basic",
        "MATLAB",
        "R",
        "SQL",
        "HTML",
        "CSS",
        "Excel",
        "PowerPoint",
        "Word",
        "AutoCAD",
        "SolidWorks",
        "LaTeX",
        "Git",
        "Linux",
        "Windows",
        "macOS",
        "iOS",
        "Android",
        "AWS",
        "Azure",
        "Docker",
        "Kubernetes",
        "TensorFlow",
        "PyTorch",
        "Pandas",
        "NumPy",
        "React",
        "Node.js",
        "SAP",
        "ERP",
        "CRM",
        "Agile",
        "Scrum",
    }
)

LANGUAGES: frozenset[str] = frozenset(
    {
        "English",
        "French",
        "German",
        "Italian",
        "Spanish",
        "Portuguese",
        "Arabic",
        "Chinese",
        "Mandarin",
        "Cantonese",
        "Japanese",
        "Korean",
        "Hindi",
        "Urdu",
        "Bengali",
        "Russian",
        "Turkish",
        "Persian",
        "Farsi",
        "Dutch",
        "Swedish",
        "Norwegian",
        "Danish",
        "Finnish",
        "Polish",
        "Czech",
        "Romanian",
        "Hungarian",
        "Greek",
        "Hebrew",
        "Thai",
        "Vietnamese",
        "Indonesian",
        "Malay",
        "Swahili",
        "Tamil",
        "Telugu",
        "Tagalog",
        "Ukrainian",
        "Serbian",
        "Croatian",
        "Bulgarian",
        "Slovak",
        "Slovenian",
        "Catalan",
        "Basque",
        "Galician",
        "Luxembourgish",
        "Albanian",
        "Macedonian",
        "Bosnian",
        "Montenegrin",
        "Latvian",
        "Lithuanian",
        "Estonian",
        "Maltese",
        "Icelandic",
        "Georgian",
        "Armenian",
        "Azerbaijani",
        "Kazakh",
        "Uzbek",
        "Nepali",
        "Sinhala",
        "Pashto",
        "Kurdish",
        "Amharic",
        "Tigrinya",
        "Somali",
        "Yoruba",
        "Igbo",
        "Hausa",
        "Zulu",
        "Xhosa",
        "Afrikaans",
    }
)

ACTIVITIES: frozenset[str] = frozenset(
    {
        "Swimming",
        "Archery",
        "Cycling",
        "Hiking",
        "Running",
        "Football",
        "Basketball",
        "Tennis",
        "Volleyball",
        "Chess",
        "Yoga",
        "Music",
        "Piano",
        "Guitar",
        "Photography",
        "Painting",
        "Cooking",
        "Reading",
        "Traveling",
        "Volunteering",
        "Scouting",
        "Debate",
    }
)

FORM_LABELS: frozenset[str] = frozenset(
    {
        # French form labels from synthese / transcripts
        "Nom",
        "Prénom",
        "Adresse",
        "Téléphone",
        "Ville",
        "Pays",
        "Nationalité",
        "Domicile",
        "Date de naissance",
        "Lieu de naissance",
        "Sexe",
        "Féminin",
        "Masculin",
        "Célibataire",
        "État civil",
        "Courriel",
        "Email",
        "Fax",
        "Site web",
        "Rue",
        "Code postal",
        "Canton",
        "Commune",
        # English equivalents
        "Name",
        "First name",
        "Last name",
        "Surname",
        "Address",
        "Telephone",
        "Phone",
        "City",
        "Country",
        "Nationality",
        "Date of birth",
        "Place of birth",
        "Gender",
        "Marital status",
        "Postal code",
        "Province",
    }
)

JOB_TITLES: frozenset[str] = frozenset(
    {
        "Engineer",
        "Coordinator",
        "Director",
        "Manager",
        "Professor",
        "Instructor",
        "Lecturer",
        "Researcher",
        "Analyst",
        "Consultant",
        "Architect",
        "Developer",
        "Designer",
        "Specialist",
        "Supervisor",
        "Administrator",
        "Assistant",
        "Associate",
        "Intern",
        "Volunteer",
        "Technician",
        "Officer",
        "Representative",
        "Advisor",
        "Coach",
        "Mentor",
        "Student",
        "Member",
        # French titles
        "Ingénieur",
        "Directeur",
        "Directrice",
        "Professeur",
        "Responsable",
        "Conseiller",
        "Technicien",
        "Stagiaire",
        "Volontaire",
        "Recteur",
    }
)

ALL_CATEGORIES: tuple[frozenset[str], ...] = (
    INSTITUTIONS,
    ACADEMIC_TERMS,
    PRONOUNS,
    TECHNICAL_TERMS,
    ACTIVITIES,
    LANGUAGES,
    FORM_LABELS,
    JOB_TITLES,
)
# All allow-list categories, for iteration.


def build_allow_list(
    *, extra: frozenset[str] | None = None, exclude: frozenset[str] | None = None
) -> list[str]:
    """Merge all categories into a single allow-list for Presidio.

    Parameters
    ----------
    extra
        Additional terms to include beyond the built-in categories.
    exclude
        Terms to remove from the merged list (e.g., if a term is actually PII
        in a specific context).

    Returns
    -------
    list[str]
        Sorted, deduplicated list of safe terms.
    """
    merged: set[str] = set()
    for category in ALL_CATEGORIES:
        merged.update(category)

    if extra is not None:
        merged.update(extra)
    if exclude is not None:
        merged -= exclude

    return sorted(merged)
