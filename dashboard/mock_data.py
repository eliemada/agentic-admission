"""Mock evaluation data for dashboard demo.

Generates realistic candidate evaluations for the MTE admission dashboard.
This module is used only for demo/development; the real dashboard reads
pre-computed JSON files from data/processed/evaluations/.
"""

from __future__ import annotations

SEMESTERS = ["2025-26-spring"]

MOCK_EVALUATIONS: list[dict] = [
    {
        "candidate_id": "chen_wei",
        "semester": "2025-26-spring",
        "school": "ETH Zurich",
        "school_country": "Switzerland",
        "gpa": "5.6",
        "gpa_max": "6.0",
        "study_level": "Bachelor",
        "gender": "M",
        "summary": (
            "Exceptional candidate from ETH Zurich with outstanding academic record "
            "(5.6/6.0) and strong quantitative foundations. Two recommendation letters "
            "highlight independent research in distributed systems and leadership in "
            "student engineering projects. Clear motivation for the MTE program with "
            "a concrete entrepreneurial vision in deep-tech."
        ),
        "status": "admit",
        "confidence": 0.92,
        "evaluations": [
            {
                "role": "Academic",
                "decision": "ACCEPT",
                "confidence": 0.90,
                "reasoning": (
                    "Academic record is excellent — top 5% at ETH Zurich in Computer "
                    "Science. GPA of 5.6/6.0 demonstrates consistent high performance "
                    "across demanding quantitative courses. Transcript shows strong marks "
                    "in algorithms, systems, and mathematics. No concerns about academic "
                    "preparation for the MTE program."
                ),
                "scores": {"academic": 9, "motivation": 8, "recommendation": 9, "experience": 7},
                "document_references": [
                    {
                        "doc_type": "transcript",
                        "note": "Consistently top marks in algorithms, distributed systems, and linear algebra",
                    },
                    {
                        "doc_type": "recommendation_letter",
                        "note": "Prof. at ETH Systems Group praises independent research contributions",
                    },
                ],
            },
            {
                "role": "Reference",
                "decision": "ACCEPT",
                "confidence": 0.88,
                "reasoning": (
                    "Beyond strong academics, the candidate shows genuine entrepreneurial "
                    "drive. Motivation letter articulates a clear vision for applying ML "
                    "to industrial automation. Led a team of 6 in a university hackathon "
                    "that produced a working prototype. Cultural fit with MTE's "
                    "interdisciplinary philosophy is strong."
                ),
                "scores": {"academic": 9, "motivation": 9, "recommendation": 8, "experience": 7},
                "document_references": [
                    {
                        "doc_type": "motivation_letter",
                        "note": "Clear articulation of entrepreneurial vision in deep-tech/ML automation",
                    }
                ],
            },
            {
                "role": "Motivation",
                "decision": "ACCEPT",
                "confidence": 0.93,
                "reasoning": (
                    "Strong technical depth evidenced by coursework in ML, distributed "
                    "systems, and software engineering. Semester project on federated "
                    "learning shows ability to work at the frontier. Technical skills "
                    "are well-suited for the MTE program's technology track."
                ),
                "scores": {"academic": 9, "motivation": 8, "recommendation": 9, "experience": 8},
                "document_references": [
                    {
                        "doc_type": "transcript",
                        "note": "Semester project on federated learning received highest mark",
                    }
                ],
            },
        ],
        "moderator": {
            "final_decision": "ACCEPT",
            "reasoning": (
                "Unanimous recommendation from all three evaluators. Academic excellence "
                "at a top-tier institution, clear technical depth, and genuine "
                "entrepreneurial motivation. No significant concerns raised."
            ),
            "report": (
                "All three panel members recommend acceptance with high confidence "
                "(0.88-0.93). The candidate combines a strong ETH Zurich transcript "
                "with demonstrated research ability and a clear entrepreneurial vision. "
                "Recommended for admission."
            ),
        },
        "documents": [
            "application_summary",
            "motivation_letter",
            "recommendation_letter",
            "transcript",
            "cv",
        ],
    },
    {
        "candidate_id": "garcia_maria",
        "semester": "2025-26-spring",
        "school": "Stanford University",
        "school_country": "United States",
        "gpa": "3.92",
        "gpa_max": "4.0",
        "study_level": "Bachelor",
        "gender": "F",
        "summary": (
            "Outstanding research profile with a published NeurIPS workshop paper on "
            "multi-agent systems — directly relevant to the program's focus. Stellar "
            "recommendation from a Stanford faculty member in AI research. Strong "
            "GPA (3.92/4.0) with particular depth in machine learning and statistics."
        ),
        "status": "admit",
        "confidence": 0.95,
        "evaluations": [
            {
                "role": "Academic",
                "decision": "ACCEPT",
                "confidence": 0.94,
                "reasoning": (
                    "Near-perfect GPA at Stanford, one of the world's most competitive "
                    "CS programs. Coursework is highly relevant: advanced ML, Bayesian "
                    "statistics, entrepreneurship. Published research demonstrates "
                    "academic maturity beyond typical applicants."
                ),
                "scores": {"academic": 10, "motivation": 9, "recommendation": 10, "experience": 8},
                "document_references": [
                    {
                        "doc_type": "transcript",
                        "note": "3.92/4.0 at Stanford CS with advanced ML and statistics coursework",
                    },
                    {
                        "doc_type": "recommendation_letter",
                        "note": "Stanford AI Lab faculty describes candidate as 'one of the strongest undergraduates I've mentored'",
                    },
                ],
            },
            {
                "role": "Reference",
                "decision": "ACCEPT",
                "confidence": 0.91,
                "reasoning": (
                    "Exceptional combination of technical skills and leadership. "
                    "Co-founded a student startup that reached 500 users. Motivation "
                    "letter shows mature understanding of the tech-business interface. "
                    "Would bring valuable Silicon Valley perspective to the cohort."
                ),
                "scores": {"academic": 10, "motivation": 9, "recommendation": 10, "experience": 9},
                "document_references": [
                    {
                        "doc_type": "motivation_letter",
                        "note": "Discusses co-founding a student startup and lessons learned from the experience",
                    },
                    {
                        "doc_type": "cv",
                        "note": "Internship at Google Brain + startup co-founder experience",
                    },
                ],
            },
            {
                "role": "Motivation",
                "decision": "ACCEPT",
                "confidence": 0.96,
                "reasoning": (
                    "Published NeurIPS workshop paper on multi-agent reinforcement "
                    "learning. Google Brain internship focused on large-scale ML systems. "
                    "Technical depth is outstanding and directly aligned with the "
                    "program's technology component."
                ),
                "scores": {"academic": 10, "motivation": 8, "recommendation": 10, "experience": 9},
                "document_references": [
                    {
                        "doc_type": "recommendation_letter",
                        "note": "Details candidate's NeurIPS workshop paper on multi-agent RL",
                    }
                ],
            },
        ],
        "moderator": {
            "final_decision": "ACCEPT",
            "reasoning": (
                "Strongest candidate in this round. Unanimous acceptance with the "
                "highest average confidence (0.94). Research publication, top-tier "
                "institution, and entrepreneurial experience make this a clear admit."
            ),
            "report": (
                "Unanimous ACCEPT with very high confidence. Published researcher, "
                "Stanford CS top performer, startup experience. One of the strongest "
                "profiles in this admission round. Recommended for admission with "
                "potential scholarship consideration."
            ),
        },
        "documents": [
            "application_summary",
            "motivation_letter",
            "recommendation_letter",
            "transcript",
            "cv",
            "language_certificate",
        ],
    },
    {
        "candidate_id": "mueller_hans",
        "semester": "2025-26-spring",
        "school": "TU Munich",
        "school_country": "Germany",
        "gpa": "2.1",
        "gpa_max": "1.0",
        "study_level": "Bachelor",
        "gender": "M",
        "summary": (
            "Solid academic foundation at TU Munich (GPA 2.1, German scale) with "
            "relevant engineering coursework. One recommendation letter is strong but "
            "the other raises concerns about teamwork and communication skills. "
            "Motivation letter lacks specificity about entrepreneurial goals."
        ),
        "status": "discuss",
        "confidence": 0.55,
        "evaluations": [
            {
                "role": "Academic",
                "decision": "WAITLIST",
                "confidence": 0.50,
                "reasoning": (
                    "GPA of 2.1 (German scale) is decent but not exceptional — roughly "
                    "top 30% at TU Munich. Core coursework is relevant but grades in "
                    "management electives are mediocre. Meets minimum requirements but "
                    "doesn't stand out academically."
                ),
                "scores": {"academic": 6, "motivation": 5, "recommendation": 6, "experience": 5},
                "document_references": [
                    {
                        "doc_type": "transcript",
                        "note": "Strong in engineering courses but weaker in management electives (2.7-3.0 range)",
                    }
                ],
            },
            {
                "role": "Reference",
                "decision": "DISCUSS",
                "confidence": 0.45,
                "reasoning": (
                    "Mixed signals. First recommendation is enthusiastic about technical "
                    "skills, but second recommender mentions difficulties in team projects "
                    "and communication. Motivation letter is generic — could apply to any "
                    "program. Unclear why MTE specifically."
                ),
                "scores": {"academic": 6, "motivation": 4, "recommendation": 5, "experience": 5},
                "document_references": [
                    {
                        "doc_type": "recommendation_letter",
                        "note": "Second recommender notes 'room for improvement in collaborative settings'",
                    },
                    {
                        "doc_type": "motivation_letter",
                        "note": "Generic motivation — no specific mention of MTE curriculum or entrepreneurial goals",
                    },
                ],
            },
            {
                "role": "Motivation",
                "decision": "ACCEPT",
                "confidence": 0.65,
                "reasoning": (
                    "Technically competent — solid grades in core engineering and CS "
                    "courses. Bachelor thesis on IoT systems shows practical skill. "
                    "Technical preparation is sufficient for the program, though not "
                    "outstanding."
                ),
                "scores": {"academic": 7, "motivation": 5, "recommendation": 6, "experience": 6},
                "document_references": [
                    {
                        "doc_type": "transcript",
                        "note": "Bachelor thesis on IoT sensor networks — practical systems work",
                    }
                ],
            },
        ],
        "moderator": {
            "final_decision": "DISCUSS",
            "reasoning": (
                "Split panel: technical evaluator leans accept, holistic evaluator "
                "has concerns about motivation and teamwork. Academic profile is "
                "borderline. Recommend committee discussion, particularly around "
                "the teamwork concerns raised in the second recommendation."
            ),
            "report": (
                "No consensus — decisions range from WAITLIST to ACCEPT. Key concern "
                "is the mismatch between technical competence and soft skills/motivation. "
                "Committee should probe the teamwork flag from the second recommender "
                "and assess whether the candidate's goals genuinely align with MTE."
            ),
        },
        "documents": [
            "application_summary",
            "motivation_letter",
            "recommendation_letter",
            "transcript",
            "cv",
        ],
    },
    {
        "candidate_id": "kumar_priya",
        "semester": "2025-26-spring",
        "school": "IIT Bombay",
        "school_country": "India",
        "gpa": "8.5",
        "gpa_max": "10.0",
        "study_level": "Bachelor",
        "gender": "F",
        "summary": (
            "Strong technical candidate from IIT Bombay with excellent industry "
            "experience — two internships including one at Google Bangalore. GPA of "
            "8.5/10.0 places her in the top quartile. Recommendation letters "
            "consistently praise problem-solving ability and initiative."
        ),
        "status": "admit",
        "confidence": 0.85,
        "evaluations": [
            {
                "role": "Academic",
                "decision": "ACCEPT",
                "confidence": 0.82,
                "reasoning": (
                    "GPA of 8.5/10.0 at IIT Bombay is strong — this is among India's "
                    "most selective institutions. Coursework is well-rounded across CS, "
                    "mathematics, and economics. Two solid internships add practical "
                    "dimension to academic record."
                ),
                "scores": {"academic": 8, "motivation": 8, "recommendation": 8, "experience": 9},
                "document_references": [
                    {
                        "doc_type": "transcript",
                        "note": "Top quartile at IIT Bombay with strong breadth across CS, math, economics",
                    }
                ],
            },
            {
                "role": "Reference",
                "decision": "ACCEPT",
                "confidence": 0.85,
                "reasoning": (
                    "Impressive trajectory. Comes from a non-privileged background and "
                    "gained admission to IIT through national competitive exam. Google "
                    "internship validates industry-readiness. Motivation letter shows "
                    "genuine interest in bringing technology solutions to emerging markets."
                ),
                "scores": {"academic": 8, "motivation": 9, "recommendation": 8, "experience": 9},
                "document_references": [
                    {
                        "doc_type": "motivation_letter",
                        "note": "Compelling narrative about technology for emerging markets",
                    },
                    {
                        "doc_type": "cv",
                        "note": "Google Bangalore internship + fintech startup internship",
                    },
                ],
            },
            {
                "role": "Motivation",
                "decision": "ACCEPT",
                "confidence": 0.87,
                "reasoning": (
                    "Strong software engineering skills demonstrated through internships "
                    "and coursework. Familiar with ML, cloud infrastructure, and agile "
                    "development. Technical skills are well-aligned with MTE requirements."
                ),
                "scores": {"academic": 8, "motivation": 8, "recommendation": 8, "experience": 9},
                "document_references": [
                    {
                        "doc_type": "recommendation_letter",
                        "note": "Google internship supervisor highlights strong engineering and initiative",
                    }
                ],
            },
        ],
        "moderator": {
            "final_decision": "ACCEPT",
            "reasoning": (
                "Unanimous acceptance. Strong combination of academic performance "
                "at a top institution, meaningful industry experience, and compelling "
                "motivation. The emerging markets angle adds diversity to the cohort."
            ),
            "report": (
                "All evaluators recommend ACCEPT (confidence 0.82-0.87). Solid IIT "
                "Bombay profile with Google internship experience. Motivation for "
                "tech entrepreneurship in emerging markets is genuine and well-articulated. "
                "Recommended for admission."
            ),
        },
        "documents": [
            "application_summary",
            "motivation_letter",
            "recommendation_letter",
            "transcript",
            "cv",
            "language_certificate",
        ],
    },
    {
        "candidate_id": "nakamura_yuki",
        "semester": "2025-26-spring",
        "school": "University of Tokyo",
        "school_country": "Japan",
        "gpa": "3.4",
        "gpa_max": "4.0",
        "study_level": "Master",
        "gender": "M",
        "summary": (
            "Interesting interdisciplinary profile combining CS Master's from UTokyo "
            "with a Bachelor's in Business Administration. GPA is above average but "
            "not exceptional. Already holds a Master's degree — committee should "
            "discuss added value of a second Master's program."
        ),
        "status": "discuss",
        "confidence": 0.52,
        "evaluations": [
            {
                "role": "Academic",
                "decision": "DISCUSS",
                "confidence": 0.48,
                "reasoning": (
                    "GPA of 3.4/4.0 at UTokyo is acceptable but not competitive against "
                    "other applicants this round. Already holds a Master's degree — the "
                    "committee should assess whether MTE adds meaningful value beyond "
                    "what the candidate already has."
                ),
                "scores": {"academic": 7, "motivation": 6, "recommendation": 7, "experience": 6},
                "document_references": [
                    {
                        "doc_type": "transcript",
                        "note": "Solid but unremarkable — 3.4/4.0 with strongest marks in HCI courses",
                    },
                    {"doc_type": "diploma", "note": "Already holds MSc in CS from UTokyo (2024)"},
                ],
            },
            {
                "role": "Reference",
                "decision": "ACCEPT",
                "confidence": 0.60,
                "reasoning": (
                    "The dual background in business and CS is exactly what MTE targets. "
                    "Motivation letter explains that the Japanese job market doesn't offer "
                    "the same tech-entrepreneurship ecosystem. Wants to build bridges "
                    "between Japanese manufacturing and European tech. Unique perspective "
                    "for the cohort."
                ),
                "scores": {"academic": 7, "motivation": 8, "recommendation": 7, "experience": 7},
                "document_references": [
                    {
                        "doc_type": "motivation_letter",
                        "note": "Articulates Japan-Europe technology bridge vision — unique angle",
                    }
                ],
            },
            {
                "role": "Motivation",
                "decision": "DISCUSS",
                "confidence": 0.50,
                "reasoning": (
                    "Technical skills are adequate — Master's thesis on human-computer "
                    "interaction is solid but not deeply technical. Limited evidence of "
                    "systems-level or ML expertise that would distinguish this candidate. "
                    "The business background is a plus but technical depth is a question."
                ),
                "scores": {"academic": 7, "motivation": 7, "recommendation": 7, "experience": 6},
                "document_references": [
                    {
                        "doc_type": "transcript",
                        "note": "Master's thesis in HCI — competent but not deeply technical",
                    }
                ],
            },
        ],
        "moderator": {
            "final_decision": "DISCUSS",
            "reasoning": (
                "Interesting profile but no consensus. The holistic evaluator sees "
                "value in the dual background and unique Japan-Europe vision. Strict "
                "and technical evaluators question whether MTE is the right fit given "
                "existing Master's degree and moderate technical depth."
            ),
            "report": (
                "Split decision — one ACCEPT, two DISCUSS. The candidate brings a "
                "unique perspective but the committee should address: (1) added value "
                "of a second Master's, (2) depth of technical skills, (3) feasibility "
                "of the Japan-Europe bridge vision. Interview recommended."
            ),
        },
        "documents": [
            "application_summary",
            "motivation_letter",
            "recommendation_letter",
            "transcript",
            "diploma",
            "cv",
        ],
    },
    {
        "candidate_id": "petrov_ivan",
        "semester": "2025-26-spring",
        "school": "Moscow State University",
        "school_country": "Russia",
        "gpa": "3.8",
        "gpa_max": "5.0",
        "study_level": "Bachelor",
        "gender": "M",
        "summary": (
            "Below-average GPA (3.8/5.0) from Moscow State University with limited "
            "extracurricular engagement. Motivation letter focuses primarily on "
            "relocating to Europe rather than on the program's academic or "
            "entrepreneurial components. Recommendation letters are lukewarm."
        ),
        "status": "reject",
        "confidence": 0.78,
        "evaluations": [
            {
                "role": "Academic",
                "decision": "REJECT",
                "confidence": 0.80,
                "reasoning": (
                    "GPA of 3.8/5.0 is below average even accounting for institutional "
                    "context. Transcript shows inconsistent performance — strong in "
                    "mathematics but weak in applied courses. Does not meet the academic "
                    "threshold for competitive admission."
                ),
                "scores": {"academic": 4, "motivation": 3, "recommendation": 4, "experience": 3},
                "document_references": [
                    {
                        "doc_type": "transcript",
                        "note": "Inconsistent grades — strong math (4.5+) but weak applied courses (3.0-3.5)",
                    }
                ],
            },
            {
                "role": "Reference",
                "decision": "REJECT",
                "confidence": 0.75,
                "reasoning": (
                    "Motivation letter is concerning — primary motivation appears to be "
                    "geographic relocation rather than genuine interest in MTE's program. "
                    "No mention of entrepreneurship, technology management, or specific "
                    "career goals aligned with the program. Recommendation letters are "
                    "generic and lack enthusiasm."
                ),
                "scores": {"academic": 4, "motivation": 2, "recommendation": 3, "experience": 3},
                "document_references": [
                    {
                        "doc_type": "motivation_letter",
                        "note": "Focuses on 'European opportunities' — no mention of entrepreneurship or MTE specifics",
                    },
                    {
                        "doc_type": "recommendation_letter",
                        "note": "Generic letter — 'the student attended my course and received a satisfactory grade'",
                    },
                ],
            },
            {
                "role": "Motivation",
                "decision": "REJECT",
                "confidence": 0.78,
                "reasoning": (
                    "Limited technical depth. No projects, internships, or research "
                    "experience mentioned in CV. Coursework is theoretical with little "
                    "evidence of practical application. Technical preparation is "
                    "insufficient for the MTE program."
                ),
                "scores": {"academic": 4, "motivation": 3, "recommendation": 3, "experience": 2},
                "document_references": [
                    {
                        "doc_type": "cv",
                        "note": "No internships, projects, or extracurricular technical activities listed",
                    }
                ],
            },
        ],
        "moderator": {
            "final_decision": "REJECT",
            "reasoning": (
                "Unanimous rejection. Academic record is below threshold, motivation "
                "is misaligned with program goals, and recommendation letters provide "
                "no compelling evidence of potential."
            ),
            "report": (
                "All three evaluators recommend REJECT. Below-average academics, "
                "motivation misaligned with MTE goals, and no practical experience. "
                "Candidate does not meet admission criteria."
            ),
        },
        "documents": [
            "application_summary",
            "motivation_letter",
            "recommendation_letter",
            "transcript",
            "cv",
        ],
    },
    {
        "candidate_id": "okafor_chioma",
        "semester": "2025-26-spring",
        "school": "University of Lagos",
        "school_country": "Nigeria",
        "gpa": "4.5",
        "gpa_max": "5.0",
        "study_level": "Bachelor",
        "gender": "F",
        "summary": (
            "Impressive trajectory — first-class honours at University of Lagos with "
            "a GPA of 4.5/5.0. Founded a fintech startup serving 2,000+ users in "
            "Lagos while completing her degree. Recommendation letters describe "
            "exceptional drive and resilience."
        ),
        "status": "admit",
        "confidence": 0.83,
        "evaluations": [
            {
                "role": "Academic",
                "decision": "ACCEPT",
                "confidence": 0.75,
                "reasoning": (
                    "GPA of 4.5/5.0 is first-class honours at UNILAG, which is Nigeria's "
                    "most competitive institution. However, institutional ranking is lower "
                    "than other applicants' schools. Coursework is relevant but depth of "
                    "advanced topics is limited by curriculum. Academic record is strong "
                    "within institutional context."
                ),
                "scores": {"academic": 7, "motivation": 9, "recommendation": 8, "experience": 9},
                "document_references": [
                    {
                        "doc_type": "transcript",
                        "note": "First-class honours — top of graduating class in Computer Science",
                    }
                ],
            },
            {
                "role": "Reference",
                "decision": "ACCEPT",
                "confidence": 0.90,
                "reasoning": (
                    "Extraordinary candidate given context. Built a functioning fintech "
                    "product while studying full-time — this is exactly the entrepreneurial "
                    "profile MTE seeks. Motivation letter is the strongest in this round: "
                    "articulate, specific, and grounded in real experience. Would add "
                    "tremendous diversity and energy to the cohort."
                ),
                "scores": {"academic": 7, "motivation": 10, "recommendation": 9, "experience": 10},
                "document_references": [
                    {
                        "doc_type": "motivation_letter",
                        "note": "Describes building a fintech startup from scratch — 2,000+ active users",
                    },
                    {
                        "doc_type": "recommendation_letter",
                        "note": "Dean of Engineering: 'most entrepreneurial student in 20 years of teaching'",
                    },
                ],
            },
            {
                "role": "Motivation",
                "decision": "ACCEPT",
                "confidence": 0.80,
                "reasoning": (
                    "Built a full-stack fintech application (mobile + backend) — this "
                    "demonstrates real technical skill beyond what coursework alone shows. "
                    "Some gaps in theoretical CS (limited access to advanced courses) but "
                    "practical ability is clearly strong."
                ),
                "scores": {"academic": 7, "motivation": 9, "recommendation": 8, "experience": 9},
                "document_references": [
                    {
                        "doc_type": "cv",
                        "note": "Full-stack fintech app: React Native + Node.js + PostgreSQL",
                    }
                ],
            },
        ],
        "moderator": {
            "final_decision": "ACCEPT",
            "reasoning": (
                "Unanimous acceptance. While academic institution is lower-ranked, "
                "the candidate's entrepreneurial achievements and trajectory are "
                "exceptional. The holistic evaluator's assessment is particularly "
                "compelling — this is the profile MTE was designed for."
            ),
            "report": (
                "All evaluators recommend ACCEPT. The startup experience, strong "
                "academic performance in context, and compelling motivation make this "
                "a strong admit. Consider for the entrepreneurship scholarship track."
            ),
        },
        "documents": [
            "application_summary",
            "motivation_letter",
            "recommendation_letter",
            "transcript",
            "cv",
        ],
    },
    {
        "candidate_id": "smith_jordan",
        "semester": "2025-26-spring",
        "school": "MIT",
        "school_country": "United States",
        "gpa": "4.8",
        "gpa_max": "5.0",
        "study_level": "Bachelor",
        "gender": "M",
        "summary": (
            "Top-tier academic profile from MIT with exceptional GPA (4.8/5.0) and "
            "strong quantitative skills. Two summer internships at Boston-area startups "
            "show entrepreneurial interest. Recommendation from an MIT Sloan professor "
            "highlights analytical thinking and business acumen."
        ),
        "status": "admit",
        "confidence": 0.89,
        "evaluations": [
            {
                "role": "Academic",
                "decision": "ACCEPT",
                "confidence": 0.92,
                "reasoning": (
                    "Outstanding GPA at MIT — one of the world's top engineering schools. "
                    "Coursework spans CS, applied mathematics, and management science. "
                    "Academic preparation is excellent and well-suited for MTE."
                ),
                "scores": {"academic": 10, "motivation": 8, "recommendation": 9, "experience": 8},
                "document_references": [
                    {
                        "doc_type": "transcript",
                        "note": "4.8/5.0 at MIT with dual focus in CS and management science",
                    }
                ],
            },
            {
                "role": "Reference",
                "decision": "ACCEPT",
                "confidence": 0.84,
                "reasoning": (
                    "Strong profile but slightly less compelling motivation than other "
                    "top candidates. Startup internships are relevant but motivation "
                    "letter reads somewhat transactional — focused on career advancement "
                    "rather than a specific vision. Still a strong candidate overall."
                ),
                "scores": {"academic": 10, "motivation": 7, "recommendation": 9, "experience": 8},
                "document_references": [
                    {
                        "doc_type": "motivation_letter",
                        "note": "Well-written but career-focused rather than vision-driven",
                    }
                ],
            },
            {
                "role": "Motivation",
                "decision": "ACCEPT",
                "confidence": 0.90,
                "reasoning": (
                    "Exceptional technical foundation. Coursework in algorithms, systems, "
                    "and optimization is rigorous. Startup internships involved real "
                    "engineering work (backend systems, data pipelines). Strong technical "
                    "preparation."
                ),
                "scores": {"academic": 10, "motivation": 7, "recommendation": 9, "experience": 8},
                "document_references": [
                    {
                        "doc_type": "cv",
                        "note": "Backend engineering at two Boston-area startups (data pipelines, APIs)",
                    },
                    {
                        "doc_type": "recommendation_letter",
                        "note": "MIT Sloan professor: strong analytical thinking, 'natural bridge between engineering and business'",
                    },
                ],
            },
        ],
        "moderator": {
            "final_decision": "ACCEPT",
            "reasoning": (
                "Unanimous acceptance. Outstanding academics at a top institution with "
                "relevant practical experience. Minor note: motivation could be more "
                "vision-driven, but this doesn't outweigh the strong overall profile."
            ),
            "report": (
                "All evaluators recommend ACCEPT (0.84-0.92). Academically among the "
                "strongest candidates. Slight concern about depth of entrepreneurial "
                "motivation compared to peers, but overall a clear admit."
            ),
        },
        "documents": [
            "application_summary",
            "motivation_letter",
            "recommendation_letter",
            "transcript",
            "cv",
            "gre_results",
        ],
    },
    {
        "candidate_id": "johnson_alex",
        "semester": "2025-26-spring",
        "school": "University of Toronto",
        "school_country": "Canada",
        "gpa": "3.2",
        "gpa_max": "4.0",
        "study_level": "Bachelor",
        "gender": "M",
        "summary": None,
        "status": "pending",
        "confidence": 0.15,
        "evaluations": [
            {
                "role": "Academic",
                "decision": "DISCUSS",
                "confidence": 0.20,
                "reasoning": (
                    "Only one document available for review — the application summary. "
                    "Cannot assess academic record, motivation, or recommendations "
                    "without additional materials. Evaluation cannot be completed."
                ),
                "scores": {},
                "document_references": [],
            }
        ],
        "moderator": {
            "final_decision": "PENDING",
            "reasoning": (
                "Insufficient documentation to evaluate this candidate. Only one "
                "document was available. Cannot produce a meaningful assessment."
            ),
            "report": (
                "Evaluation incomplete due to missing documents. Only the application "
                "summary was available — no transcript, motivation letter, or "
                "recommendations. Candidate should be contacted for missing materials."
            ),
        },
        "documents": ["application_summary"],
    },
    {
        "candidate_id": "williams_taylor",
        "semester": "2025-26-spring",
        "school": "Regional State College",
        "school_country": "United States",
        "gpa": "2.8",
        "gpa_max": "4.0",
        "study_level": "Bachelor",
        "gender": "F",
        "summary": (
            "Below-average GPA (2.8/4.0) from a non-ranked institution with limited "
            "relevant coursework. Motivation letter shows genuine enthusiasm but lacks "
            "the academic and technical preparation expected for the MTE program. "
            "Recommendation letters come from teaching staff rather than research faculty."
        ),
        "status": "reject",
        "confidence": 0.72,
        "evaluations": [
            {
                "role": "Academic",
                "decision": "REJECT",
                "confidence": 0.78,
                "reasoning": (
                    "GPA of 2.8/4.0 is below the competitive threshold. Institution "
                    "is not ranked and course offerings appear limited — no advanced "
                    "CS or mathematics courses on transcript. Academic preparation is "
                    "insufficient for a rigorous Master's program."
                ),
                "scores": {"academic": 3, "motivation": 5, "recommendation": 4, "experience": 3},
                "document_references": [
                    {
                        "doc_type": "transcript",
                        "note": "2.8/4.0 — no advanced CS or math courses beyond introductory level",
                    }
                ],
            },
            {
                "role": "Reference",
                "decision": "REJECT",
                "confidence": 0.65,
                "reasoning": (
                    "The candidate shows enthusiasm and genuine interest, which is "
                    "commendable. However, the gap between current preparation and "
                    "program requirements is too large. Recommendation letters are from "
                    "lecturers and don't speak to research potential or advanced skills. "
                    "Suggest exploring preparatory programs first."
                ),
                "scores": {"academic": 3, "motivation": 6, "recommendation": 4, "experience": 3},
                "document_references": [
                    {
                        "doc_type": "motivation_letter",
                        "note": "Genuine enthusiasm but unrealistic expectations of current preparation level",
                    },
                    {
                        "doc_type": "recommendation_letter",
                        "note": "From lecturers, not research faculty — describe 'hardworking student' without specifics",
                    },
                ],
            },
            {
                "role": "Motivation",
                "decision": "REJECT",
                "confidence": 0.75,
                "reasoning": (
                    "No evidence of technical skills beyond introductory programming "
                    "courses. No projects, no internships, no research experience. "
                    "The technical gap is too significant for the MTE program."
                ),
                "scores": {"academic": 3, "motivation": 5, "recommendation": 3, "experience": 2},
                "document_references": [
                    {
                        "doc_type": "cv",
                        "note": "Only retail and hospitality work experience — no technical roles",
                    }
                ],
            },
        ],
        "moderator": {
            "final_decision": "REJECT",
            "reasoning": (
                "Unanimous rejection. While the candidate shows enthusiasm, the "
                "academic and technical preparation is insufficient. The committee "
                "may consider suggesting alternative preparatory pathways."
            ),
            "report": (
                "All evaluators recommend REJECT. Academic and technical preparation "
                "do not meet minimum requirements. Candidate shows motivation but "
                "would benefit from additional preparation before applying to a "
                "program at this level."
            ),
        },
        "documents": [
            "application_summary",
            "motivation_letter",
            "recommendation_letter",
            "transcript",
            "cv",
        ],
    },
]

# Pre-built chat responses for demo purposes.
# Keys are lowercase keyword fragments that trigger the response.
MOCK_CHAT_RESPONSES: dict[str, str] = {
    "why": (
        "Based on the agent evaluations, the main factors behind the decision were: "
        "academic record strength, alignment of motivation with MTE program goals, "
        "and the quality of recommendation letters. I can go into more detail on "
        "any of these if you'd like."
    ),
    "recommend": (
        "The recommendation letters were assessed by all three agents. I can "
        "summarize the key points each letter raised. Would you like me to focus "
        "on a specific recommender?"
    ),
    "gpa": (
        "The candidate's GPA was evaluated in the context of their institution's "
        "grading scale and selectivity. The strict agent placed significant weight "
        "on this metric, while the holistic agent considered it alongside other factors."
    ),
    "motiv": (
        "The motivation letter was evaluated primarily by the holistic agent, who "
        "assessed alignment with MTE's entrepreneurial and technological focus. "
        "The key question was whether the candidate articulated a specific vision "
        "beyond generic career advancement."
    ),
    "compare": (
        "I don't have access to cohort-level comparison data in the current version. "
        "This capability is planned for a future update with the knowledge base "
        "integration. For now, I can only discuss this candidate's individual profile."
    ),
    "technical": (
        "The technical agent focused on coursework depth, practical projects, and "
        "evidence of hands-on engineering skills. Internships and research projects "
        "were weighted heavily in this assessment."
    ),
    "interview": (
        "Based on the evaluation, an interview could help clarify areas where the "
        "agents had lower confidence. I'd suggest focusing on the points flagged "
        "in the moderator's report."
    ),
}

DEFAULT_CHAT_RESPONSE = (
    "I can answer questions about this candidate based on their anonymized documents "
    "and agent evaluations. Could you be more specific about what aspect you'd like "
    "to explore? For example: academic record, motivation, recommendations, or "
    "technical skills."
)

NO_DATA_CHAT_RESPONSE = (
    "I don't have enough information about this candidate to provide a meaningful "
    "answer. The evaluation was incomplete due to missing documents. I'd recommend "
    "requesting the missing materials before making a decision."
)
